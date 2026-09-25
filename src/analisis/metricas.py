"""Preparación y métricas reutilizables del mercado laboral colombiano."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import numpy as np
import pandas as pd

CAMPOS_CALIDAD = [
    "titulo", "empresa", "ciudad", "departamento", "fecha_publicacion",
    "descripcion", "salario_texto", "tipo_contrato", "modalidad",
    "nivel_educativo", "experiencia_texto",
]


def reparar_mojibake(texto: object) -> str:
    """Corrige textos UTF-8 leídos como Latin-1 (p. ej. ``confecciÃ³n``).

    Varios orígenes publican acentos doblemente codificados; se repara solo
    cuando aparecen los marcadores tÃ­picos (``Ã``/``Â``) y siempre de forma
    segura: si la reconstrucción falla, se devuelve el texto original.
    """
    if not isinstance(texto, str):
        return texto
    if "Ã" not in texto and "Â" not in texto:
        return texto
    try:
        return texto.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def _texto_limpio(serie: pd.Series) -> pd.Series:
    s = serie.astype("string").str.strip()
    s = s.map(reparar_mojibake)
    return s.mask(s.str.lower().isin({"", "nan", "none", "null", "n/a"}))


def normalizar_titulo(valor: object) -> str | None:
    if pd.isna(valor):
        return None
    texto = unicodedata.normalize("NFKC", str(valor)).lower().strip()
    texto = re.sub(r"^\s*\d{3,}\s*[-:|]?\s*", "", texto)
    texto = re.sub(r"[^\w+#./-]+", " ", texto, flags=re.UNICODE)
    texto = re.sub(r"\s+", " ", texto).strip(" -/.")
    return texto or None


def categorizar_modalidad(valor: object) -> str:
    if pd.isna(valor) or not str(valor).strip():
        return "Desconocida"
    v = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode().lower()
    if "hibrid" in v:
        return "Híbrida"
    if any(x in v for x in ("remot", "teletrab")):
        return "Remota/teletrabajo"
    if "presencial" in v or "on-site" in v or "onsite" in v:
        return "Presencial"
    return "Otra/No homologada"


def _meses_experiencia(valor: object) -> float:
    if pd.isna(valor):
        return np.nan
    numeros = re.findall(r"\d+(?:[.,]\d+)?", str(valor))
    if not numeros:
        return np.nan
    n = float(numeros[0].replace(",", "."))
    texto = str(valor).lower()
    if "añ" in texto or "ano" in texto:
        n *= 12
    return n if 0 <= n <= 480 else np.nan


def preparar_vacantes(df: pd.DataFrame) -> pd.DataFrame:
    """Crea variables analíticas sin modificar el DataFrame original."""
    out = df.copy()
    for col in out.select_dtypes(include=["object", "string"]).columns:
        out[col] = _texto_limpio(out[col])
    for col in ("fecha_publicacion", "fecha_captura"):
        if col in out:
            out[col] = pd.to_datetime(out[col], errors="coerce", utc=True)
    for col in ("salario_min", "salario_max"):
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    out["titulo_normalizado"] = out["titulo"].map(normalizar_titulo)
    out["modalidad_categoria"] = out["modalidad"].map(categorizar_modalidad)
    out["experiencia_meses"] = out["experiencia_texto"].map(_meses_experiencia)
    out["requiere_experiencia"] = out["experiencia_meses"].gt(0).where(out["experiencia_meses"].notna())
    out["experiencia_tramo"] = pd.cut(
        out["experiencia_meses"],
        bins=[-0.01, 0, 6, 12, 24, 36, 60, np.inf],
        labels=["Sin experiencia", "1–6 meses", "7–12 meses", "13–24 meses", "25–36 meses", "37–60 meses", "Más de 60 meses"],
    )

    rango_valido = (
        out["salario_min"].notna() & out["salario_max"].notna()
        & out["salario_min"].ge(0) & out["salario_max"].ge(out["salario_min"])
    )
    # SPE y El Empleo publican buckets/rangos mensuales. LinkedIn conserva el
    # intervalo original, por lo que solo se admite cuando el texto dice mes.
    fuente_mensual = out["portal"].isin(["spe", "elempleo"])
    texto_mes = out["salario_texto"].fillna("").str.lower().str.contains("month|mes")
    comparable = rango_valido & (fuente_mensual | texto_mes)
    out["salario_comparable"] = comparable
    out["salario_representativo"] = ((out["salario_min"] + out["salario_max"]) / 2).where(comparable)
    return out


def tabla_frecuencias(df: pd.DataFrame, columna: str, n: int | None = None) -> pd.DataFrame:
    vc = df[columna].fillna("Sin información").value_counts(dropna=False)
    if n:
        vc = vc.head(n)
    out = vc.rename("publicaciones").rename_axis(columna).reset_index()
    out["participacion_pct"] = out["publicaciones"].div(len(df)).mul(100)
    return out


def tabla_completitud(df: pd.DataFrame, campos: Iterable[str] = CAMPOS_CALIDAD) -> pd.DataFrame:
    filas = []
    for col in campos:
        if col not in df:
            continue
        valido = _texto_limpio(df[col]).notna() if not pd.api.types.is_datetime64_any_dtype(df[col]) else df[col].notna()
        filas.append({"campo": col, "no_nulos": int(valido.sum()), "cobertura_pct": valido.mean() * 100})
    return pd.DataFrame(filas).sort_values("cobertura_pct")


def completitud_por_grupo(df: pd.DataFrame, grupo: str = "portal", campos: Iterable[str] = CAMPOS_CALIDAD) -> pd.DataFrame:
    tablas = []
    for valor, parte in df.groupby(grupo, dropna=False):
        tabla = tabla_completitud(parte, campos)[["campo", "cobertura_pct"]]
        tabla[grupo] = valor
        tablas.append(tabla)
    return pd.concat(tablas, ignore_index=True).pivot(index="campo", columns=grupo, values="cobertura_pct") if tablas else pd.DataFrame()


def indice_hhi(serie: pd.Series) -> float:
    proporciones = serie.dropna().value_counts(normalize=True)
    return float((proporciones.pow(2)).sum()) if len(proporciones) else np.nan


def resumen_concentracion(df: pd.DataFrame, columna: str) -> dict:
    vc = df[columna].dropna().value_counts()
    total = int(vc.sum())
    return {
        "categoria": columna,
        "hhi": indice_hhi(df[columna]),
        "top_1_pct": float(vc.head(1).sum() / total * 100) if total else np.nan,
        "top_5_pct": float(vc.head(5).sum() / total * 100) if total else np.nan,
        "categorias": int(len(vc)),
    }


def diversidad_cargos_region(df: pd.DataFrame, minimo: int = 100) -> pd.DataFrame:
    """Entropía normalizada de títulos por departamento (0–1)."""
    filas = []
    base = df.dropna(subset=["departamento", "titulo_normalizado"])
    for departamento, grupo in base.groupby("departamento", observed=True):
        if len(grupo) < minimo:
            continue
        p = grupo["titulo_normalizado"].value_counts(normalize=True)
        entropia = float(-(p * np.log(p)).sum())
        maximo = np.log(len(p)) if len(p) > 1 else 1
        filas.append({
            "departamento": departamento, "publicaciones": len(grupo),
            "cargos_distintos": len(p), "diversidad_normalizada": entropia / maximo,
        })
    return pd.DataFrame(filas).sort_values("diversidad_normalizada", ascending=False) if filas else pd.DataFrame(columns=["departamento", "publicaciones", "cargos_distintos", "diversidad_normalizada"])


def resumen_salarios(df: pd.DataFrame) -> pd.Series:
    s = df.loc[df["salario_comparable"], "salario_representativo"].dropna()
    if s.empty:
        return pd.Series(dtype=float)
    q05, q95 = s.quantile([0.05, 0.95])
    recortada = s[s.between(q05, q95)]
    return pd.Series({
        "observaciones": len(s), "cobertura_pct": len(s) / len(df) * 100,
        "minimo_rango_observado": df.loc[df["salario_comparable"], "salario_min"].min(),
        "maximo_rango_observado": df.loc[df["salario_comparable"], "salario_max"].max(),
        "media_punto_medio": s.mean(), "mediana_punto_medio": s.median(),
        "media_recortada_5pct": recortada.mean(), "q1": s.quantile(.25),
        "q3": s.quantile(.75), "p10": s.quantile(.10), "p90": s.quantile(.90),
    })


def salarios_por_grupo(df: pd.DataFrame, columna: str, minimo: int = 30) -> pd.DataFrame:
    base = df.loc[df["salario_comparable"] & df[columna].notna()]
    out = base.groupby(columna, observed=True)["salario_representativo"].agg(observaciones="size", mediana="median", media="mean", q1=lambda s: s.quantile(.25), q3=lambda s: s.quantile(.75)).reset_index()
    return out[out["observaciones"] >= minimo].sort_values("mediana", ascending=False)


def serie_temporal_mensual(df: pd.DataFrame) -> pd.DataFrame:
    fechas = df["fecha_publicacion"].dropna()
    if fechas.empty:
        return pd.DataFrame(columns=["periodo", "publicaciones", "variacion_pct"])
    periodo = fechas.dt.tz_convert(None).dt.to_period("M")
    conteos = periodo.value_counts().sort_index()
    indice = pd.period_range(conteos.index.min(), conteos.index.max(), freq="M")
    out = conteos.reindex(indice, fill_value=0).rename("publicaciones").rename_axis("periodo").reset_index()
    out["variacion_pct"] = out["publicaciones"].pct_change().mul(100)
    out.loc[out["publicaciones"].shift(1).eq(0), "variacion_pct"] = np.nan
    # El primer y el último mes suelen estar truncados por inicio/corte del corpus.
    out["periodo_completo"] = True
    if len(out):
        out.loc[[out.index.min(), out.index.max()], "periodo_completo"] = False
    out["periodo"] = out["periodo"].astype(str)
    return out


def kpis_principales(df: pd.DataFrame) -> dict:
    return {
        "publicaciones": int(len(df)),
        "empresas_o_prestadores": int(df["empresa"].nunique(dropna=True)),
        "ciudades": int(df["ciudad"].nunique(dropna=True)),
        "departamentos": int(df["departamento"].nunique(dropna=True)),
        "teletrabajo_explicito_pct": float(df["modalidad_categoria"].eq("Remota/teletrabajo").mean() * 100),
        "salario_comparable_pct": float(df["salario_comparable"].mean() * 100),
    }
