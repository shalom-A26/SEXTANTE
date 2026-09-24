"""Acceso reproducible al dataset analítico de SEXTANTE en Hugging Face.

Este módulo es deliberadamente independiente del pipeline de extracción. Solo
descarga los shards publicados y los consulta en modo lectura.
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


@dataclass(frozen=True)
class ProcedenciaDatos:
    repo_id: str
    revision_solicitada: str
    revision_resuelta: str
    fecha_acceso_utc: str
    archivos: tuple[str, ...]
    filas: int

    def como_dict(self) -> dict:
        return asdict(self)


def descargar_dataset_hf(
    repo_id: str = REPO_HF_DEFECTO,
    revision: str = "main",
    token: str | None = None,
) -> tuple[list[Path], str]:
    """Descarga/carga desde caché los shards publicados de Hugging Face."""
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
            "Configura HF_TOKEN o ejecuta `hf auth login`; no se usará otro corpus "
            "silenciosamente."
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
    """Carga todos los shards HF y devuelve datos junto con su procedencia."""
    archivos, revision_resuelta = descargar_dataset_hf(repo_id, revision, token)
    partes = [pd.read_parquet(ruta, columns=columnas) for ruta in archivos]
    df = pd.concat(partes, ignore_index=True)
    meta = ProcedenciaDatos(
        repo_id=repo_id,
        revision_solicitada=revision,
        revision_resuelta=revision_resuelta,
        fecha_acceso_utc=datetime.now(timezone.utc).isoformat(),
        archivos=tuple(str(p) for p in archivos),
        filas=len(df),
    )
    return df, meta


def iterar_vacantes_hf(
    repo_id: str = REPO_HF_DEFECTO,
    revision: str = "main",
    columnas: list[str] | None = None,
    token: str | None = None,
):
    """Entrega un DataFrame por shard para procesamiento textual acotado en RAM."""
    archivos, revision_resuelta = descargar_dataset_hf(repo_id, revision, token)
    for ruta in archivos:
        yield pd.read_parquet(ruta, columns=columnas), ruta, revision_resuelta


def consultar_duckdb(
    sql: str,
    repo_id: str = REPO_HF_DEFECTO,
    revision: str = "main",
    token: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Ejecuta SQL DuckDB directamente sobre los parquet cacheados."""
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("Falta duckdb; instala requirements.txt") from exc
    archivos, revision_resuelta = descargar_dataset_hf(repo_id, revision, token)
    rutas = [str(p) for p in archivos]
    con = duckdb.connect(":memory:")
    # DuckDB no acepta parámetros preparados dentro de CREATE VIEW. Las rutas
    # proceden del snapshot resuelto, pero aun así se escapan comillas simples.
    lista_sql = "[" + ",".join("'" + p.replace("'", "''") + "'" for p in rutas) + "]"
    con.execute(f"CREATE VIEW vacantes AS SELECT * FROM read_parquet({lista_sql})")
    resultado = con.execute(sql).fetch_df()
    con.close()
    return resultado, {
        "repo_id": repo_id,
        "revision_solicitada": revision,
        "revision_resuelta": revision_resuelta,
        "archivos": rutas,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga y verifica el dataset HF de SEXTANTE")
    parser.add_argument("--repo", default=REPO_HF_DEFECTO)
    parser.add_argument("--revision", default="main")
    args = parser.parse_args()
    df, meta = cargar_vacantes_hf(args.repo, args.revision, columnas=["id_vacante", "portal"])
    print(f"{len(df):,} filas | {df['portal'].nunique()} portal(es)")
    print(meta.como_dict())


if __name__ == "__main__":
    main()
