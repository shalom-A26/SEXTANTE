"""Acceso reproducible al dataset analítico de SEXTANTE en Hugging Face.

Este módulo es deliberadamente independiente del pipeline de extracción. Solo
descarga los shards publicados (parquet, actualizados por el pipeline cada 6 h)
y los consulta en modo lectura. Hugging Face es la única fuente analítica del
proyecto: no hay base local que la sustituya.

Los shards pueden acumular copias obsoletas cuando se re-emite el dataset, por
lo que toda carga deduplica por `id_vacante` y reporta cuántas filas se
conservaron.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_HF_DEFECTO = "pxtron/vacantes-colombia"
PATRON_SHARDS = "data/*.parquet"
CLAVE_DEDUPE = "id_vacante"


def cargar_entorno_local(raiz: Path | None = None) -> None:
    """Completa el entorno con un `.env` local si existe, sin imprimirlas.

    Guarda el token de Hugging Face (`HF_TOKEN`) fuera del control de versiones
    (`.env` está en `.gitignore`). Solo añade claves ausentes: lo que ya esté
    exportado tiene prioridad. Ningún valor se escribe en el log.
    """
    ruta = (raiz or Path(__file__).resolve().parents[2]) / ".env"
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def _deduplicar(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Conserva la primera aparición de cada `id_vacante` y devuelve el descarte."""
    if CLAVE_DEDUPE not in df.columns:
        return df, 0
    brutas = len(df)
    unicas = df.drop_duplicates(subset=CLAVE_DEDUPE, keep="first")
    return unicas, brutas - len(unicas)


@dataclass(frozen=True)
class ProcedenciaDatos:
    repo_id: str
    revision_solicitada: str
    revision_resuelta: str
    fecha_acceso_utc: str
    archivos: tuple[str, ...]
    filas: int
    filas_brutas: int
    duplicadas_evitadas: int

    def como_dict(self) -> dict:
        return asdict(self)


def descargar_dataset_hf(
    repo_id: str = REPO_HF_DEFECTO,
    revision: str = "main",
    token: str | None = None,
) -> tuple[list[Path], str]:
    """Descarga/carga desde caché los shards publicados de Hugging Face."""
    cargar_entorno_local()
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("Falta huggingface_hub; instala requirements.txt") from exc

    try:
        snapshot = Path(
            snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=revision,
                allow_patterns=[PATRON_SHARDS],
                token=token or os.environ.get("HF_TOKEN"),
            )
        )
    except Exception as exc:  # la librería usa varias clases según HTTP/cache
        raise RuntimeError(
            f"No fue posible acceder al dataset privado '{repo_id}'. "
            "Configura HF_TOKEN en `.env` o ejecuta `hf auth login`; no se usará "
            "otro corpus silenciosamente."
        ) from exc

    archivos = sorted((snapshot / "data").glob("*.parquet"))
    if not archivos:
        raise FileNotFoundError(f"El snapshot de {repo_id}@{revision} no contiene {PATRON_SHARDS}")
    revision_resuelta = snapshot.name if snapshot.parent.name == "snapshots" else revision
    return archivos, revision_resuelta


def cargar_vacantes_hf(
    repo_id: str = REPO_HF_DEFECTO,
    revision: str = "main",
    columnas: list[str] | None = None,
    token: str | None = None,
) -> tuple[pd.DataFrame, ProcedenciaDatos]:
    """Carga todos los shards HF (deduplicados) junto con su procedencia."""
    archivos, revision_resuelta = descargar_dataset_hf(repo_id, revision, token)
    partes = [pd.read_parquet(ruta, columns=columnas) for ruta in archivos]
    brutas = sum(len(p) for p in partes)
    df = pd.concat(partes, ignore_index=True)
    df, descartadas = _deduplicar(df)
    meta = ProcedenciaDatos(
        repo_id=repo_id,
        revision_solicitada=revision,
        revision_resuelta=revision_resuelta,
        fecha_acceso_utc=datetime.now(timezone.utc).isoformat(),
        archivos=tuple(str(p) for p in archivos),
        filas=len(df),
        filas_brutas=brutas,
        duplicadas_evitadas=descartadas,
    )
    return df, meta


def iterar_vacantes_hf(
    repo_id: str = REPO_HF_DEFECTO,
    revision: str = "main",
    columnas: list[str] | None = None,
    token: str | None = None,
):
    """Entrega un DataFrame por shard (deduplicado contra los ya vistos).

    Pensado para procesamiento textual acotado en RAM sobre los shards que el
    pipeline publica periódicamente.
    """
    archivos, revision_resuelta = descargar_dataset_hf(repo_id, revision, token)
    vistas: set = set()
    for ruta in archivos:
        parte, _ = _deduplicar(pd.read_parquet(ruta, columns=columnas))
        if CLAVE_DEDUPE in parte.columns:
            nuevas = parte[CLAVE_DEDUPE]
            parte = parte[~nuevas.isin(vistas)]
            vistas.update(nuevas)
        yield parte, ruta, revision_resuelta


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga y verifica el dataset HF de SEXTANTE")
    parser.add_argument("--repo", default=REPO_HF_DEFECTO)
    parser.add_argument("--revision", default="main")
    args = parser.parse_args()
    df, meta = cargar_vacantes_hf(args.repo, args.revision, columnas=["id_vacante", "portal"])
    print(f"{len(df):,} filas únicas de {meta.filas_brutas:,} brutas ({meta.duplicadas_evitadas:,} duplicadas)")
    print(f"{df['portal'].nunique()} portal(es)")
    print(meta.como_dict())


if __name__ == "__main__":
    main()
