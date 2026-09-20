"""Orquestador: extrae vacantes de las fuentes disponibles y las guarda en data/raw/.

Uso:
    python -m src.extraccion.corpus --fuentes linkedin elempleo
    python -m src.extraccion.corpus --todo

Cada fuente emite DataFrames con el esquema canónico (src/extraccion/esquema.py)
y guarda en data/raw/vacantes.csv con deduplicación por url.
"""

from __future__ import annotations

import argparse

import pandas as pd

from src.extraccion.esquema import normalizar
from src.extraccion import base
from .portales.elempleo import PAGINAS_LISTADO, scrape_el_empleo
from .portales.linkedin_jobspy import scrape_linkedin

BUSQUEDAS_LINKEDIN = [
    "analista",
    "ingeniero",
    "desarrollador",
    "auxiliar administrativo",
    "vendedor",
    "enfermero",
    "contador",
    "docente",
    "operario",
    "asesor comercial",
]


def recolectar_linkedin(resultados_por_busqueda: int = 25) -> pd.DataFrame:
    df = pd.DataFrame()
    for termino in BUSQUEDAS_LINKEDIN:
        print(f"  [linkedin] búsqueda '{termino}' ...", flush=True)
        df = pd.concat([df, scrape_linkedin(termino, resultados=resultados_por_busqueda)])
    return normalizar(df)


def recolectar_elempleo(max_detalles: int = 120) -> pd.DataFrame:
    print(f"  [elempleo] hasta {max_detalles} detalles desde {len(PAGINAS_LISTADO)} listados")
    return scrape_el_empleo(max_detalles=max_detalles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recolecta vacantes y las guarda en data/raw/")
    parser.add_argument(
        "--fuentes", nargs="+", choices=["linkedin", "elempleo"], default=["linkedin", "elempleo"]
    )
    parser.add_argument("--todo", action="store_true", help="Ejecutar todas las fuentes")
    parser.add_argument("--linkedin-por-busqueda", type=int, default=25)
    parser.add_argument("--elempleo-max-detalles", type=int, default=120)
    args = parser.parse_args()

    fuentes = ["linkedin", "elempleo"] if args.todo else args.fuentes

    for fuente in fuentes:
        print(f"== {fuente.upper()} ==")
        try:
            if fuente == "linkedin":
                df = recolectar_linkedin(args.linkedin_por_busqueda)
            else:
                df = recolectar_elempleo(args.elempleo_max_detalles)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] fuente '{fuente}': {exc}")
            continue
        base.resumen_fuente(fuente, df)
        if len(df):
            agregadas = base.guardar_lotes(df)
            print(f"  -> {agregadas} nuevas en {base.RUTA_VACANTES}")


if __name__ == "__main__":
    main()