"""Extracción inicial y auditable de habilidades basada en ESCO.

La versión inicial detecta menciones explícitas; no infiere habilidades que no
aparezcan en el texto y está diseñada para poder sustituirse por NLP contextual.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


def normalizar_texto(valor: object) -> str:
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9+#.]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _buscar_columna(columnas: list[str], candidatos: tuple[str, ...]) -> str:
    mapa = {re.sub(r"[^a-z]", "", c.lower()): c for c in columnas}
    for candidato in candidatos:
        clave = re.sub(r"[^a-z]", "", candidato.lower())
        if clave in mapa:
            return mapa[clave]
    raise ValueError(f"No se encontró ninguna columna {candidatos}; disponibles: {columnas}")


def localizar_skills_csv(directorio: str | Path) -> Path:
    ruta = Path(directorio)
    candidatos = sorted(ruta.glob("skills_es*.csv")) + sorted(ruta.glob("skills*.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"No se encontró skills_es.csv en {ruta}. Descarga el paquete CSV oficial "
            "ESCO en español y extráelo en ese directorio."
        )
    return candidatos[0]


def cargar_catalogo_esco(directorio: str | Path, version: str = "1.2.1") -> pd.DataFrame:
    """Lee conceptos ESCO y genera un vocabulario de etiquetas auditables."""
    ruta = localizar_skills_csv(directorio)
    bruto = pd.read_csv(ruta, dtype=str)
    uri = _buscar_columna(list(bruto), ("conceptUri", "concept URI", "uri"))
    preferida = _buscar_columna(list(bruto), ("preferredLabel", "preferred label", "concept PT"))
    alt = next((c for c in bruto if re.sub(r"[^a-z]", "", c.lower()) in {"altlabels", "alternativelabels", "nonpreferredterms"}), None)

    filas: list[dict] = []
    for _, row in bruto.iterrows():
        concepto = str(row[uri]).strip()
        nombre = str(row[preferida]).strip()
        etiquetas = [(nombre, True)]
        if alt and pd.notna(row[alt]):
            for etiqueta in re.split(r"\r?\n|;|\|", str(row[alt])):
                if etiqueta.strip():
                    etiquetas.append((etiqueta.strip(), False))
        for etiqueta, es_preferida in etiquetas:
            termino = normalizar_texto(etiqueta)
            if len(termino) < 3:
                continue
            filas.append({
                "esco_uri": concepto,
                "skill_nombre": nombre,
                "termino": termino,
                "etiqueta_original": etiqueta,
                "es_preferida": es_preferida,
                "version_esco": version,
            })
    vocab = pd.DataFrame(filas).drop_duplicates(["esco_uri", "termino"])
    amb = vocab.groupby("termino")["esco_uri"].nunique()
    vocab["ambiguo"] = vocab["termino"].map(amb).gt(1)
    return vocab.reset_index(drop=True)


@dataclass
class ExtractorESCO:
    catalogo: pd.DataFrame

    def __post_init__(self) -> None:
        try:
            import ahocorasick
        except ImportError as exc:
            raise RuntimeError("Falta pyahocorasick; instala requirements.txt") from exc

        # Alias ambiguos se excluyen: escoger uno arbitrariamente crearía falsos enlaces.
        vocab = self.catalogo.loc[~self.catalogo["ambiguo"]].copy()
        self._por_termino = {r.termino: r for r in vocab.itertuples(index=False)}
        automata = ahocorasick.Automaton()
        for termino in self._por_termino:
            automata.add_word(termino, termino)
        automata.make_automaton()
        self._automata = automata

    @staticmethod
    def _limites(texto: str, inicio: int, fin: int) -> bool:
        anterior = texto[inicio - 1] if inicio else " "
        siguiente = texto[fin + 1] if fin + 1 < len(texto) else " "
        return not anterior.isalnum() and not siguiente.isalnum()

    def extraer(self, texto: object) -> list[dict]:
        normalizado = normalizar_texto(texto)
        candidatos: list[tuple[int, int, str]] = []
        for fin, termino in self._automata.iter(normalizado):
            inicio = fin - len(termino) + 1
            if self._limites(normalizado, inicio, fin):
                candidatos.append((inicio, fin, termino))
        # Longest-match: si dos etiquetas se solapan, conserva la más específica.
        candidatos.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
        ocupados: list[tuple[int, int]] = []
        seleccionados: dict[str, dict] = {}
        for inicio, fin, termino in candidatos:
            if any(not (fin < a or inicio > b) for a, b in ocupados):
                continue
            row = self._por_termino[termino]
            seleccionados.setdefault(row.esco_uri, {
                "esco_uri": row.esco_uri,
                "skill_nombre": row.skill_nombre,
                "termino_detectado": termino,
                "version_esco": row.version_esco,
            })
            ocupados.append((inicio, fin))
        return list(seleccionados.values())


def extraer_habilidades_dataframe(
    df: pd.DataFrame,
    extractor: ExtractorESCO,
    columna_texto: str = "descripcion",
) -> pd.DataFrame:
    requeridas = {"id_vacante", "titulo", columna_texto}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas para extraer habilidades: {sorted(faltantes)}")
    filas: list[dict] = []
    for row in df[["id_vacante", "titulo", columna_texto]].itertuples(index=False, name=None):
        id_vacante, titulo, texto = row
        for hallazgo in extractor.extraer(texto):
            filas.append({"id_vacante": id_vacante, "titulo": titulo, **hallazgo})
    columnas = ["id_vacante", "titulo", "esco_uri", "skill_nombre", "termino_detectado", "version_esco"]
    return pd.DataFrame(filas, columns=columnas).drop_duplicates(["id_vacante", "esco_uri"])
