"""Sincronización del corpus con Hugging Face (la memoria persistente del pipeline).

Hugging Face es el "disco duro" de la captura: en cada corrida del workflow de
GitHub Actions se baja el corpus acumulado, se le agregan las vacantes nuevas y
se vuelve a subir. El runner es efímero, así que sin este paso no hay acumulación.

`--pull` restaura los dos stores canónicos locales a partir de lo publicado:

  - layout actual: los archivos semanales `data/semana-*.parquet` se recomponen
    en `data/raw/spe/vacantes_spe.parquet` (SPE) y `data/raw/vacantes.csv`
    (corpus curado), según la columna `almacen`;
  - layout anterior (`store/…`): se baja cada archivo tal cual, para que un
    dataset viejo siga restaurándose durante la migración.

Además deja `data/raw/_publicado.json` con los conteos publicados: es lo que
permite a `emitir_dataset` reportar cuántas vacantes son realmente nuevas (y no
el total, que siempre "parece crecer").

Uso:
    HF_TOKEN=hf_xxx python -m src.extraccion.sync_hf --pull --repo pxtron/vacantes-colombia
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.extraccion import base
from src.extraccion.esquema import COLUMNAS_ESQUEMA
from src.extraccion.emitir_dataset import (
    PATRON_SEMANA,
    RUTA_BASE_PUBLICADO,
)
from src.extraccion.portales.spe import contar_filas

REPO_HF_DEFECTO = "pxtron/vacantes-colombia"

RUTA_SPE = base.RUTA_RAW / "spe" / "vacantes_spe.parquet"

# Layout anterior a 2026-10-04: ruta publicada -> store canónico local.
ARCHIVOS_ESTADO_LEGACY = {
    "store/vacantes_spe.parquet": RUTA_SPE,
    "store/vacantes_curado.csv": base.RUTA_VACANTES,
}


def _token(token: str | None) -> str | None:
    return token or os.environ.get("HF_TOKEN")


def _listar_semanales(repo_id: str, token: str | None) -> list[str]:
    """Rutas `data/semana-*.parquet` del repo, en orden cronológico."""
    from huggingface_hub import HfApi

    api = HfApi()
    info = api.repo_info(repo_id, repo_type="dataset", token=token)
    return sorted(
        s.rfilename
        for s in info.siblings
        if PATRON_SEMANA.match(Path(s.rfilename).name)
    )


def _leer_semanales(repo_id: str, rutas: list[str], token: str | None) -> pd.DataFrame:
    from huggingface_hub import hf_hub_download

    partes = []
    for ruta in rutas:
        cache = hf_hub_download(repo_id, ruta, repo_type="dataset", token=token)
        partes.append(pd.read_parquet(cache))
    return pd.concat(partes, ignore_index=True)


def restaurar_stores(
    publicado: pd.DataFrame,
    ruta_spe: Path = RUTA_SPE,
    ruta_curado: Path = base.RUTA_VACANTES,
) -> dict[str, int]:
    """Reparte lo publicado entre los dos stores canónicos locales.

    Invierte a la inversa de `emitir_dataset.consolidar`: las filas `spe` van al
    parquet y las `curado` al CSV, cada uno con las 17 columnas del esquema y
    sin la columna `almacen`.
    """
    conteos: dict[str, int] = {"filas": int(len(publicado))}
    if not len(publicado):
        return conteos
    if "almacen" not in publicado.columns:
        raise SystemExit(
            "ERROR: los archivos publicados no traen la columna 'almacen'; "
            "no se puede recomponer el corpus. Revisa el layout del repo."
        )

    base.crear_estructura_datos()

    spe = publicado[publicado["almacen"].eq("spe")].drop(columns=["almacen"])
    if len(spe):
        spe = spe[COLUMNAS_ESQUEMA].reset_index(drop=True)
        ruta_spe.parent.mkdir(parents=True, exist_ok=True)
        spe.to_parquet(ruta_spe, index=False)
        conteos["filas_spe"] = len(spe)

    curado = publicado[publicado["almacen"].eq("curado")].drop(columns=["almacen"])
    if len(curado):
        curado = curado[COLUMNAS_ESQUEMA].reset_index(drop=True)
        ruta_curado.parent.mkdir(parents=True, exist_ok=True)
        curado.to_csv(ruta_curado, index=False)
        conteos["filas_curado"] = len(curado)

    return conteos


def _escribir_base(conteos: dict[str, int], repo_id: str, revision: str) -> None:
    RUTA_BASE_PUBLICADO.parent.mkdir(parents=True, exist_ok=True)
    RUTA_BASE_PUBLICADO.write_text(
        json.dumps(
            {
                **conteos,
                "repo_id": repo_id,
                "revision": revision,
                "escrito_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def descargar_estado(
    repo_id: str = REPO_HF_DEFECTO,
    token: str | None = None,
    ruta_spe: Path = RUTA_SPE,
    ruta_curado: Path = base.RUTA_VACANTES,
) -> dict[str, int]:
    """Restaura el corpus acumulado desde HF a los stores locales.

    Devuelve los conteos restaurados. En la primera corrida el repo está vacío y
    no hay nada que restaurar (se convierte en seed de la captura).
    """
    token = _token(token)
    try:
        rutas = _listar_semanales(repo_id, token)
    except Exception as exc:  # noqa: BLE001
        print(f"  [sync_hf] no se pudo listar {repo_id} ({type(exc).__name__}): {exc}")
        return {"filas": 0}

    if rutas:
        publicado = _leer_semanales(repo_id, rutas, token)
        print(f"  [sync_hf] {len(rutas)} archivo(s) semanal(es) -> recomponiendo stores")
        conteos = restaurar_stores(publicado, ruta_spe, ruta_curado)
        print(f"  [sync_hf] restaurado: {conteos.get('filas_spe', 0):,} SPE + {conteos.get('filas_curado', 0):,} curado")
        conteos["archivos"] = len(rutas)
    else:
        conteos = _restaurar_legacy(repo_id, token, ruta_spe, ruta_curado)

    _escribir_base(conteos, repo_id, "main")
    return conteos


def _restaurar_legacy(
    repo_id: str,
    token: str | None,
    ruta_spe: Path,
    ruta_curado: Path,
) -> dict[str, int]:
    """Restaura el layout anterior (`store/`), para datasets aún no migrados."""
    import shutil

    from huggingface_hub import hf_hub_download

    conteos = {"filas": 0}
    for ruta, destino in ARCHIVOS_ESTADO_LEGACY.items():
        try:
            cache = hf_hub_download(repo_id, ruta, repo_type="dataset", token=token)
        except Exception as exc:  # noqa: BLE001
            print(f"  [sync_hf] '{ruta}' no disponible en HF ({type(exc).__name__})")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cache, destino)
        os.chmod(destino, 0o644)
        print(f"  [sync_hf] restaurado (layout anterior): {ruta} -> {destino}")

    if ruta_spe.exists():
        # `contar_filas` y no `pd.read_parquet`: ver `spe.contar_filas` (exit 134).
        conteos["filas_spe"] = contar_filas(ruta_spe)
    if ruta_curado.exists():
        conteos["filas_curado"] = len(pd.read_csv(ruta_curado, dtype=str))
    conteos["filas"] = conteos.get("filas_spe", 0) + conteos.get("filas_curado", 0)
    return conteos


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura el corpus acumulado desde Hugging Face")
    parser.add_argument("--pull", action="store_true", help="Descargar el corpus publicado a data/raw/")
    parser.add_argument("--repo", default=REPO_HF_DEFECTO, help=f"Dataset de HF (default: {REPO_HF_DEFECTO})")
    args = parser.parse_args()

    if args.pull:
        conteos = descargar_estado(args.repo)
        print(
            f"[sync_hf] {conteos.get('filas', 0):,} vacantes restauradas desde {args.repo} "
            f"({conteos.get('archivos', 0)} archivo(s) semanal(es))"
        )
    else:
        parser.error("indica --pull")


if __name__ == "__main__":
    main()