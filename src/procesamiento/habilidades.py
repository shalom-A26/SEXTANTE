"""Extracción endógena de vocabulario de habilidades desde las propias vacantes.

Fase actual del proyecto: **sin taxonomía externa** (ESCO queda como fase
futura). El vocabulario se construye a partir de las descripciones publicadas
en Hugging Face y se evalúa por su señal respecto a las ocupaciones observadas,
de modo que el resultado es auditable y reproducible: cada término conserva su
frecuencia documental y su cobertura ocupacional.

Dos pasadas, ambas sobre texto normalizado:

1. :func:`construir_vocabulario` — cuenta n-gramas por documento, filtra por
   frecuencia y calidad, elimina redundancia (un término contenido en otro con
   frecuencia casi idéntica es prescindible) y puntúa por señal ocupacional.
2. :func:`extraer_relaciones` — autómata de Aho-Corasick sobre el vocabulario
   para recuperar, vacante por vacante, qué términos aparecen en su descripción.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Iterable

import pandas as pd

from src.analisis.metricas import normalizar_titulo, reparar_mojibake

# Palabras funcionales ES/EN que no aportan como términos de demanda. Se aplican
# antes de formar n-gramas: "atención al cliente" -> ["atencion", "cliente"].
STOPWORDS = frozenset("""
de del la el los las un una unas unos y o u en con por para sin sobre entre
que que se su sus al lo le les es son era ser esta estan este estos esta estas
como mas muy ya no si pero ni pues porque cuando donde como cual cuales
nuestro nuestra nuestros nuestras tu tu tus yo nos me te le les
a ante bajo cerca contra desde durante excepto hasta mediante segun tras via
todo toda todos todas mismo misma otros otra otro
the and for with you your our from this that are was will can may should
""".split())

PATRON_NUMERO = re.compile(r"\d+[.,]\d|\d{3,}")
COLUMNAS_VOCABULARIO = ["termino", "frecuencia", "ocupaciones", "senal", "ngrama"]


def normalizar_texto(valor: object) -> str:
    """Normaliza un texto para búsqueda de términos: sin mojibake ni acentos."""
    if valor is None:
        return ""
    if not isinstance(valor, str):
        if pd.isna(valor) is True:
            return ""
        valor = str(valor)
    texto = reparar_mojibake(valor)
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9+#.]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    # Los puntos de borde ("servicio.") ensucian el límite de palabra; los
    # internos ("p.m.", "1.750.905") se conservan y se descartan después.
    return " ".join(palabra.strip(".") for palabra in texto.split()).strip()


def _tokens(texto: str) -> list[str]:
    return [p for p in texto.split() if p not in STOPWORDS and len(p) >= 2]


def texto_preparado(valor: object) -> str:
    """Texto listo para detectar términos: normalizado y sin palabras vacías.

    Tanto la construcción del vocabulario como la extracción usan esta misma
    cadena, de modo que los n-gramas formados tras quitar palabras vacías
    ("atención al cliente" -> "atencion cliente") se buscan tal cual.
    """
    return " ".join(_tokens(normalizar_texto(valor)))


def id_termino(termino: str) -> str:
    """Identificador estable de un término del vocabulario."""
    import hashlib

    digest = hashlib.sha1(termino.encode("utf-8")).hexdigest()[:16]
    return f"term_{digest}"


def contar_ngramas(textos: Iterable[object], n_min: int = 1, n_max: int = 3) -> Counter:
    """Frecuencia documental de los n-gramas de contenido de cada descripción."""
    conteo: Counter = Counter()
    for texto in textos:
        palabras = _tokens(normalizar_texto(texto))
        if not palabras:
            continue
        vistos: set[str] = set()
        for n in range(n_min, n_max + 1):
            for i in range(len(palabras) - n + 1):
                vistos.add(" ".join(palabras[i : i + n]))
        conteo.update(vistos)
    return conteo


def _aptitudes(termino: str, frecuencia: int, total: int, minimo: int, maxima_proporcion: float) -> bool:
    if frecuencia < minimo or frecuencia > maxima_proporcion * total:
        return False
    if sum(c.isalpha() for c in termino) < 4:
        return False
    return not PATRON_NUMERO.search(termino)


def _limites(texto: str, inicio: int, fin: int) -> bool:
    anterior = texto[inicio - 1] if inicio else " "
    siguiente = texto[fin + 1] if fin + 1 < len(texto) else " "
    return not anterior.isalnum() and not siguiente.isalnum()


def _es_subcadena(corta: list[str], larga: list[str]) -> bool:
    n = len(corta)
    return any(larga[i : i + n] == corta for i in range(len(larga) - n + 1))


def construir_vocabulario(
    df: pd.DataFrame,
    columna_texto: str = "descripcion",
    columna_titulo: str = "titulo",
    columna_id: str = "id_vacante",
    n_min: int = 1,
    n_max: int = 3,
    minimo_vacantes: int = 30,
    proporcion_maxima: float = 0.12,
    maximo_terminos: int = 6000,
    umbral_redundancia: float = 0.9,
    minimo_ocupaciones_docs: int = 10,
    piso_ocupaciones_senal: int = 3,
) -> pd.DataFrame:
    """Construye el vocabulario endógeno de términos (candidatos a habilidades).

    Selecciona n-gramas presentes entre ``minimo_vacantes`` y
    ``proporcion_maxima`` de los documentos, descarta los demasiado genéricos o
    numéricos, elimina redundancias y ordena por señal ocupacional
    ``frecuencia * log(K / ocupaciones)`` (K = ocupaciones con soporte mínimo;
    las coberturas por debajo de ``piso_ocupaciones_senal`` puntúan como si
    fueran ese piso, para no premiar plantillas de un solo empleador).

    El ``df`` puede ser una muestra: los umbrales se expresan en número de
    vacantes y la muestra debe ser representativa para que la señal sea útil.
    """
    requeridas = {columna_id, columna_texto, columna_titulo}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas para construir el vocabulario: {sorted(faltantes)}")

    conteo = contar_ngramas(df[columna_texto], n_min=n_min, n_max=n_max)
    total = int(df[columna_texto].notna().sum())
    if not total:
        return pd.DataFrame(columns=COLUMNAS_VOCABULARIO)

    candidatos = {
        t: c
        for t, c in conteo.items()
        if _aptitudes(t, c, total, minimo_vacantes, proporcion_maxima)
    }
    if not candidatos:
        return pd.DataFrame(columns=COLUMNAS_VOCABULARIO)

    base = pd.DataFrame({"termino": list(candidatos), "frecuencia": list(candidatos.values())})
    relaciones = extraer_relaciones(df, base, columna_texto, columna_id, columna_titulo)

    # Cobertura ocupacional: cuántas ocupaciones (con soporte mínimo) mencionan
    # el término. Sirve para castigar la plantilla repetida de las fuentes. El
    # mapa evita renormalizar el título en cada fila de relaciones.
    mapa_ocupacion = {t: normalizar_titulo(t) for t in df[columna_titulo].dropna().unique()}
    soporte_ocupacion = df[columna_titulo].map(mapa_ocupacion).value_counts()
    validas = set(soporte_ocupacion[soporte_ocupacion >= minimo_ocupaciones_docs].index)
    K = len(validas)
    if not K:
        return pd.DataFrame(columns=COLUMNAS_VOCABULARIO)

    con_ocupacion = relaciones[relaciones[columna_titulo].map(mapa_ocupacion).isin(validas)]
    cobertura = con_ocupacion.groupby("termino")[columna_id].nunique().rename("ocupaciones")
    vocab = base.merge(cobertura, on="termino", how="left")
    vocab["ocupaciones"] = vocab["ocupaciones"].fillna(0).astype(int)
    vocab = vocab[vocab["ocupaciones"] > 0].copy()
    efectivas = vocab["ocupaciones"].clip(lower=piso_ocupaciones_senal)
    vocab["senal"] = vocab["frecuencia"] * (K / efectivas).map(math.log)

    # Redundancia: si un n-grama corto aparece dentro de otro más largo con una
    # frecuencia casi idéntica, aporta la misma información una sola vez.
    frecuencia = dict(zip(vocab["termino"], vocab["frecuencia"]))
    por_raiz: dict[str, list[str]] = defaultdict(list)
    for termino in vocab["termino"]:
        por_raiz[termino.split()[0]].append(termino)
    tokens = {t: t.split() for t in vocab["termino"]}
    redundantes = {
        t
        for t in frecuencia
        for otro in por_raiz[t.split()[0]]
        if len(tokens[otro]) > len(tokens[t])
        and _es_subcadena(tokens[t], tokens[otro])
        and frecuencia[otro] >= umbral_redundancia * frecuencia[t]
    }
    vocab = vocab[~vocab["termino"].isin(redundantes)].copy()

    vocab["ngrama"] = vocab["termino"].map(lambda t: len(tokens[t]))
    vocab = vocab.sort_values("senal", ascending=False, kind="stable").head(maximo_terminos)
    return vocab.reset_index(drop=True)[["termino", "frecuencia", "ocupaciones", "senal", "ngrama"]]


def extraer_relaciones(
    df: pd.DataFrame,
    vocabulario: pd.DataFrame,
    columna_texto: str = "descripcion",
    columna_id: str = "id_vacante",
    columna_titulo: str = "titulo",
) -> pd.DataFrame:
    """Relación vacante–término para los términos del vocabulario.

    Devuelve una fila por coincidencia, con límites de palabra respetados
    ("python" no se detecta dentro de "micropython").
    """
    columnas = [columna_id, columna_titulo, "termino_id", "termino", "frecuencia_termino"]
    terminos = vocabulario["termino"].tolist() if len(vocabulario) else []
    if not terminos:
        return pd.DataFrame(columns=columnas)

    try:
        import ahocorasick
    except ImportError as exc:
        raise RuntimeError(
            "Falta pyahocorasick; instala requirements-notebooks.txt "
            "(el pipeline de captura no lo necesita)"
        ) from exc

    automata = ahocorasick.Automaton()
    for termino in terminos:
        automata.add_word(termino, termino)
    automata.make_automaton()

    filas: list[tuple[object, object, str]] = []
    for id_vacante, titulo, texto in df[[columna_id, columna_titulo, columna_texto]].itertuples(
        index=False, name=None
    ):
        normalizado = texto_preparado(texto)
        if not normalizado:
            continue
        hallazgos: set[str] = set()
        for fin, termino in automata.iter(normalizado):
            inicio = fin - len(termino) + 1
            if _limites(normalizado, inicio, fin):
                hallazgos.add(termino)
        filas.extend((id_vacante, titulo, termino) for termino in sorted(hallazgos))

    salida = pd.DataFrame(filas, columns=[columna_id, columna_titulo, "termino"])
    if salida.empty:
        return pd.DataFrame(columns=columnas)
    salida["termino_id"] = salida["termino"].map(id_termino)
    salida = salida.merge(
        vocabulario[["termino", "frecuencia"]].rename(columns={"frecuencia": "frecuencia_termino"}),
        on="termino",
        how="left",
    )
    return salida[[columna_id, columna_titulo, "termino_id", "termino", "frecuencia_termino"]]
