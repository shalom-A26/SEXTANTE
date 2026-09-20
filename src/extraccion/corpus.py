"""Orquestador: extrae vacantes de las fuentes disponibles y las guarda en data/raw/.

Uso:
    python -m src.extraccion.corpus --fuentes linkedin elempleo
    python -m src.extraccion.corpus --fuentes spe
    python -m src.extraccion.corpus --todo

LinkedIn y El Empleo guardan en data/raw/vacantes.csv con deduplicación por url.
El SPE (export oficial total) guarda su propio store canónico parquet en
data/raw/spe/vacantes_spe.parquet con deduplicación por CODIGO_VACANTE.
"""

from __future__ import annotations

import argparse

import pandas as pd

from src.extraccion.esquema import normalizar
from src.extraccion import base
from .portales import spe
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


def recolectar_spe(csv: str | None = None) -> pd.DataFrame:
    """Export oficial total del SPE. Si `csv` no se da, descarga el export completo."""
    if csv:
        print(f"  [spe] usando CSV existente: {csv}")
        origen = spe.RUTA_SPE / csv
    else:
        print(f"  [spe] descargando export total desde {spe.API_SPE} ...")
        origen = spe.descargar_export_csv(spe.RUTA_CSV_SPE)
    print(f"  [spe] convirtiendo {origen} al esquema canónico ...")
    return spe.exportar_a_canonico(origen)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recolecta vacantes y las guarda en data/raw/")
    parser.add_argument(
        "--fuentes",
        nargs="+",
        choices=["linkedin", "elempleo", "spe"],
        default=["linkedin", "elempleo"],
    )
    parser.add_argument("--todo", action="store_true", help="Ejecutar todas las fuentes")
    parser.add_argument("--linkedin-por-busqueda", type=int, default=25)
    parser.add_argument("--elempleo-max-detalles", type=int, default=120)
    parser.add_argument(
        "--spe-csv",
        help="Nombre del CSV del SPE ya descargado en data/raw/spe/ "
        "(evita re-descargar el export total)",
    )
    args = parser.parse_args()

    fuentes = ["linkedin", "elempleo", "spe"] if args.todo else args.fuentes

    for fuente in fuentes:
        print(f"== {fuente.upper()} ==")
        try:
            if fuente == "linkedin":
                df = recolectar_linkedin(args.linkedin_por_busqueda)
            elif fuente == "elempleo":
                df = recolectar_elempleo(args.elempleo_max_detalles)
            else:
                df = recolectar_spe(args.spe_csv)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] fuente '{fuente}': {exc}")
            continue
        base.resumen_fuente(fuente, df)
        if len(df):
            if fuente == "spe":
                total = spe.guardar_parquet(df)
                print(f"  -> {total} registros en {spe.RUTA_PARQUET_SPE}")
            else:
                agregadas = base.guardar_lotes(df)
                print(f"  -> {agregadas} nuevas en {base.RUTA_VACANTES}")


if __name__ == "__main__":
    main()