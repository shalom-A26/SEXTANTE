"""Sincronización del corpus con Hugging Face (la memoria persistente del pipeline).

Hugging Face actúa como el "disco duro" de la captura: en cada corrida del
workflow de GitHub Actions se baja el corpus acumulado desde un dataset de HF,
se le agregan las vacantes nuevas y se vuelve a subir (misma ruta, mismo repo).

Este módulo implementa el lado de descarga (`--pull`). La subida la hace
`emitir_dataset.py` junto con el dataset unificado (carpeta `store/`).

Uso:
    HF_TOKEN=hf_xxx python -m src.extraccion.sync_hf --pull --repo pxtron/vacantes-colombia
"""

from __future__ import annotations

import argparse
import shutil

from huggingface_hub import hf_hub_download

from src.extraccion import base

REPO_HF_DEFECTO = "pxtron/vacantes-colombia"

# Mapa: ruta dentro del dataset HF -> destino local (store canónico).
ARCHIVOS_ESTADO = {
    "store/vacantes_spe.parquet": base.RUTA_RAW / "spe" / "vacantes_spe.parquet",
    "store/vacantes_curado.csv": base.RUTA_VACANTES,
}


def descargar_estado(repo_id: str = REPO_HF_DEFECTO, token: str | None = None) -> int:
    """Baja el corpus acumulado desde HF a los stores locales (si existe).

    Devuelve cuántos archivos se restauraron. En la primera corrida el repo aún
    no tiene `store/` y no hay nada que descargar (se convierte en seed).
    """
    restaurados = 0
    for archivo, destino in ARCHIVOS_ESTADO.items():
        try:
            cache = hf_hub_download(repo_id, archivo, repo_type="dataset", token=token)
        except Exception as exc:  # noqa: BLE001  (repo o archivo inexistente aún)
            print(f"  [sync_hf] '{archivo}' no disponible en HF ({type(exc).__name__})")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cache, destino)
        print(f"  [sync_hf] restaurado: {archivo} -> {destino}")
        restaurados += 1
    return restaurados


def main() -> None:
    parser = argparse.ArgumentParser(description="Baja el corpus acumulado desde Hugging Face")
    parser.add_argument("--pull", action="store_true", help="Descargar el estado acumulado a data/raw/")
    parser.add_argument("--repo", default=REPO_HF_DEFECTO, help=f"Dataset de HF (default: {REPO_HF_DEFECTO})")
    args = parser.parse_args()

    if args.pull:
        n = descargar_estado(args.repo)
        print(f"[sync_hf] {n} archivo(s) restaurado(s) desde {args.repo}")


if __name__ == "__main__":
    main()