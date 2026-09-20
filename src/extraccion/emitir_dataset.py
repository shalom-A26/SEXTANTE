"""Emisión del dataset SEXTANTE: DuckDB local + dataset para Hugging Face.

Consolida los dos stores (corpus grande SPE en parquet y corpus curado en CSV,
ambos en el esquema canónico de 17 columnas) y produce:

  1. DuckDB local: data/duckdb/sextante.duckdb, tabla `vacantes` (todas las
     fuentes con el campo `almacen` = 'spe' | 'curado').
  2. Directorio listo para publicar como dataset de Hugging Face:
     data/emitido/vacantes-colombia/ con shards parquet + dataset card (README)
     que documenta procedencia y criterios éticos.

El subida a Hugging Face usa el mecanismo oficial del hub (huggingface_hub):
requiere la variable de entorno HF_TOKEN (token con permiso de escritura).

Uso:
    python -m src.extraccion.emitir_dataset                 # DuckDB + dir HF
    python -m src.extraccion.emitir_dataset --solo-duckdb
    python -m src.extraccion.emitir_dataset --solo-hf
    python -m src.extraccion.emitir_dataset --hf-upload --hf-repo UI/vacantes-colombia
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

from src.extraccion.esquema import COLUMNAS_ESQUEMA

from . import base
from .portales.spe import RUTA_PARQUET_SPE

RUTA_EMITIDO = base.RUTA_DATOS / "emitido"
RUTA_DUCKDB = base.RUTA_DATOS / "duckdb" / "sextante.duckdb"
NOMBRE_DATASET = "vacantes-colombia"
REPO_HF_DEFECTO = "SEXTANTE/vacantes-colombia"
FILAS_POR_SHARD = 60_000

# Coinciden con las columnas del esquema canónico + metadato de almacen.
COLUMNAS_SALIDA = COLUMNAS_ESQUEMA


def consolidar() -> pd.DataFrame:
    """Une el corpus grande SPE con el corpus curado en un solo DataFrame."""
    partes = []
    if RUTA_PARQUET_SPE.exists():
        spe_df = pd.read_parquet(RUTA_PARQUET_SPE)
        spe_df["almacen"] = "spe"
        partes.append(spe_df)
    if base.RUTA_VACANTES.exists():
        curado = pd.read_csv(base.RUTA_VACANTES, dtype=str)
        for col in COLUMNAS_SALIDA:
            if col not in curado.columns:
                curado[col] = None
        curado = curado[COLUMNAS_SALIDA]
        curado["almacen"] = "curado"
        partes.append(curado)
    if not partes:
        raise SystemExit("ERROR: no hay datos en data/raw/ (ejecuta primero src.extraccion.corpus)")
    unido = pd.concat(partes, ignore_index=True)
    for col in ("salario_min", "salario_max"):
        unido[col] = pd.to_numeric(unido[col], errors="coerce")
    return unido


def emitir_duckdb(unido: pd.DataFrame) -> Path:
    import duckdb

    RUTA_DUCKDB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(RUTA_DUCKDB))
    con.register("tmp_vacantes", unido)
    con.execute("CREATE OR REPLACE TABLE vacantes AS SELECT * FROM tmp_vacantes")
    n = con.execute("SELECT COUNT(*) FROM vacantes").fetchone()[0]
    con.close()
    print(f"[duckdb] {n} vacantes -> {RUTA_DUCKDB}")
    return RUTA_DUCKDB


def emitir_hf(unido: pd.DataFrame, repo_id: str) -> Path:
    """Genera el directorio del dataset (shards parquet + dataset card)."""
    dir_ds = RUTA_EMITIDO / NOMBRE_DATASET
    data_dir = dir_ds / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    n_shards = max(1, -(-len(unido) // FILAS_POR_SHARD))
    for i in range(n_shards):
        shard = unido.iloc[i * FILAS_POR_SHARD : (i + 1) * FILAS_POR_SHARD]
        shard.to_parquet(
            data_dir / f"train-{i:05d}-of-{n_shards:05d}.parquet",
            index=False,
        )

    card = _dataset_card(unido, n_shards)
    (dir_ds / "README.md").write_text(card, encoding="utf-8")
    print(f"[hf] {len(unido)} vacantes en {n_shards} shard(s) -> {dir_ds} (repo {repo_id})")
    return dir_ds


def _dataset_card(unido: pd.DataFrame, n_shards: int) -> str:
    count = len(unido)
    por_almacen = unido.get("almacen", pd.Series(dtype=str)).value_counts()
    n_spe = int(por_almacen.get("spe", 0))
    n_curado = int(por_almacen.get("curado", 0))
    fecha_captura = unido["fecha_captura"].dropna().max()
    cub = (unido.notna().mean() * 100).round(1).sort_values()
    cub_txt = "\n".join(f"  - {k}: {v}%" for k, v in cub.items() if v < 100)
    return f"""---
license: other
---
# {NOMBRE_DATASET}

Dataset académico de vacantes laborales colombianas (proyecto SEXTANTE,
Universidad Tecnológica de Bolívar).

- **Registros**: {count:,} (esquema canónico de 17 columnas).
- **Composición**: {n_spe:,} SPE + {n_curado:,} curado (El Empleo + LinkedIn).
- **Última captura**: {fecha_captura}.
- **Shards**: {n_shards} parquet bajo `data/`.

## Procedencia de los datos

1. **SPE (fuente maestra)** — export oficial del buscador de vacantes del
   Servicio Público de Empleo (`buscadordeempleo.gov.co`, API `/backbue/v1`,
   job asíncrono de export masivo). Vacantes únicas por `CODIGO_VACANTE`;
   históricas 2021→hoy, cobertura ~100% en descripción, nivel educativo,
   departamento, contrato, salario y experiencia.
2. **El Empleo y LinkedIn** — corpus curado, extraído con scraping ético
   (robots.txt, throttling, User-Agent identificable).

Los criterios éticos completos están en `docs/viabilidad_fuentes.md`
(`docs/viabilidad_fuentes.en.md` en inglés).

## Columnas

{", ".join(unido.columns if "almacen" in unido.columns else COLUMNAS_SALIDA)}

## Avisos

- Versión privada para uso académico. No redistribuir sin revisar los
  términos de cada portal de origen (LinkedIn, El Empleo, SPE).
- No contiene datos personales de candidatos; solo información pública de
  ofertas de empleo.

## Cobertura parcial de campos

{cub_txt or "  (cobertura 100% en todas las columnas)"}
"""


def subir_hf(dir_ds: Path, repo_id: str) -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("ERROR: define HF_TOKEN (huggingface.co/settings/tokens) para --hf-upload")
    from huggingface_hub import HfApi

    api = HfApi()
    if not api.repo_exists(repo_id, repo_type="dataset"):
        api.create_repo(repo_id, repo_type="dataset", private=True)
    api.upload_folder(folder_path=str(dir_ds), repo_id=repo_id, repo_type="dataset")
    print(f"[hf] publicado en https://huggingface.co/datasets/{repo_id} (privado)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emite el dataset SEXTANTE a DuckDB y Hugging Face")
    parser.add_argument("--solo-duckdb", action="store_true", help="Solo actualizar DuckDB local")
    parser.add_argument("--solo-hf", action="store_true", help="Solo generar el directorio del dataset HF")
    parser.add_argument("--hf-upload", action="store_true", help="Subir a Hugging Face (requiere HF_TOKEN)")
    parser.add_argument("--hf-repo", default=REPO_HF_DEFECTO, help=f"Repo destino (default: {REPO_HF_DEFECTO})")
    args = parser.parse_args()

    if args.solo_duckdb:
        emitir_duckdb(consolidar())
        return
    if args.solo_hf:
        dir_ds = emitir_hf(consolidar(), args.hf_repo)
        if args.hf_upload:
            subir_hf(dir_ds, args.hf_repo)
        return

    unido = consolidar()
    emitir_duckdb(unido)
    dir_ds = emitir_hf(unido, args.hf_repo)
    if args.hf_upload:
        subir_hf(dir_ds, args.hf_repo)


if __name__ == "__main__":
    main()