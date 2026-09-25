"""Construcción reproducible del grafo bipartito cargo–término.

Usa el vocabulario endógeno de :mod:`src.procesamiento.habilidades` (sin
taxonomía externa) y los shards publicados en Hugging Face. Dos pasadas:

1. muestrea descripciones para estimar el vocabulario y cuenta el soporte de
   cada ocupación;
2. extrae relaciones sobre las vacantes cuya ocupación alcanza el soporte
   mínimo y delega la construcción de nodos/aristas en
   :func:`construir_tablas_grafo`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analisis.datos_hf import REPO_HF_DEFECTO, iterar_vacantes_hf
from src.analisis.metricas import normalizar_titulo
from src.procesamiento.habilidades import construir_vocabulario, extraer_relaciones

RUTA_GRAFOS = Path("data/procesados/grafos")
COLUMNAS_VACANTE = ["id_vacante", "titulo"]
COLUMNAS_AUDITORIA = [
    "id_vacante", "ocupacion_id", "termino_id", "termino", "frecuencia_termino",
]


def _id_ocupacion(titulo_normalizado: str) -> str:
    digest = hashlib.sha1(titulo_normalizado.encode("utf-8")).hexdigest()[:16]
    return f"occ_{digest}"


def construir_tablas_grafo(
    vacantes: pd.DataFrame,
    relaciones: pd.DataFrame,
    minimo_ocupacion: int = 5,
    minimo_arista: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Nodos, aristas y auditoría del grafo cargo–término.

    ``vacantes`` aporta ``id_vacante`` y ``titulo``; ``relaciones`` las filas
    vacante–término producidas por :func:`extraer_relaciones`.
    """
    base_todas = vacantes[COLUMNAS_VACANTE].drop_duplicates("id_vacante").copy()
    base_todas["ocupacion_clave"] = base_todas["titulo"].map(normalizar_titulo)
    base_todas = base_todas.dropna(subset=["ocupacion_clave"])
    base_todas["ocupacion_id"] = base_todas["ocupacion_clave"].map(_id_ocupacion)
    frecuentes = base_todas["ocupacion_clave"].value_counts()
    frecuentes = frecuentes[frecuentes >= minimo_ocupacion]
    base = base_todas[base_todas["ocupacion_clave"].isin(frecuentes.index)]

    nombres = (
        base.groupby("ocupacion_clave")["titulo"]
        .agg(lambda s: s.value_counts().index[0])
        .rename("nombre")
    )
    ocupaciones = frecuentes.rename("frecuencia").to_frame().join(nombres).reset_index()
    ocupaciones["node_id"] = ocupaciones["ocupacion_clave"].map(_id_ocupacion)
    nodos_occ = ocupaciones.assign(tipo="ocupacion")[["node_id", "nombre", "tipo", "frecuencia"]]

    rel_todas = relaciones.merge(base[["id_vacante", "ocupacion_id"]], on="id_vacante", how="inner")
    rel = rel_todas.drop_duplicates(["id_vacante", "ocupacion_id", "termino_id"]).copy()
    aristas = (
        rel.groupby(["ocupacion_id", "termino_id"])
        .agg(peso=("id_vacante", "nunique"), termino_nombre=("termino", "first"))
        .reset_index()
    )
    aristas = aristas[aristas["peso"] >= minimo_arista].copy()
    aristas["source"] = aristas["ocupacion_id"]
    aristas["target"] = aristas["termino_id"]
    frec_occ = frecuentes.rename("frecuencia_ocupacion").rename_axis("ocupacion_clave").reset_index()
    frec_occ["source"] = frec_occ["ocupacion_clave"].map(_id_ocupacion)
    aristas = aristas.merge(frec_occ[["source", "frecuencia_ocupacion"]], on="source")
    aristas["proporcion_ocupacion"] = aristas["peso"] / aristas["frecuencia_ocupacion"]

    # Las tablas representan el grafo efectivo: no conservar ocupaciones que
    # quedaron aisladas tras aplicar el soporte mínimo de arista.
    nodos_occ = nodos_occ[nodos_occ["node_id"].isin(aristas["source"])]

    terminos = (
        rel_todas[rel_todas["termino_id"].isin(aristas["target"])]
        .groupby("termino_id")
        .agg(nombre=("termino", "first"), frecuencia=("id_vacante", "nunique"))
        .reset_index()
        .rename(columns={"termino_id": "node_id"})
    )
    nodos_termino = terminos.assign(tipo="habilidad")[["node_id", "nombre", "tipo", "frecuencia"]]
    nodos = pd.concat([nodos_occ, nodos_termino], ignore_index=True)
    salida_aristas = (
        aristas[["source", "target", "peso", "proporcion_ocupacion"]]
        .sort_values(["source", "peso"], ascending=[True, False])
        .reset_index(drop=True)
    )
    auditoria = rel_todas[
        ["id_vacante", "ocupacion_id", "termino_id", "termino", "frecuencia_termino"]
    ].drop_duplicates()
    return nodos, salida_aristas, auditoria


def _muestrear(
    partes: list[pd.DataFrame], semilla: int, maximo: int
) -> pd.DataFrame:
    """Muestreo por reservorio: muestra reproducible sin cargar todo en RAM."""
    rng = random.Random(semilla)
    reservorio: list[tuple] = []
    vistos = 0
    for parte in partes:
        for fila in parte[COLUMNAS_VACANTE + ["descripcion"]].itertuples(index=False, name=None):
            vistos += 1
            if len(reservorio) < maximo:
                reservorio.append(fila)
                continue
            j = rng.randrange(vistos)
            if j < maximo:
                reservorio[j] = fila
    return pd.DataFrame(reservorio, columns=COLUMNAS_VACANTE + ["descripcion"])


def generar_desde_hf(
    repo_id: str,
    revision: str,
    salida: Path = RUTA_GRAFOS,
    minimo_ocupacion: int = 5,
    minimo_arista: int = 3,
    maximo_vocabulario: int = 60_000,
    semilla: int = 42,
    maximo_terminos: int = 6000,
) -> None:
    # Pasada 1: soporte de ocupaciones + muestra para el vocabulario.
    soporte: Counter = Counter()
    muestra: list[tuple] = []
    rng = random.Random(semilla)
    vistos = 0
    revision_resuelta = revision
    for parte, _ruta, revision_resuelta in iterar_vacantes_hf(
        repo_id, revision, ["id_vacante", "titulo", "descripcion"]
    ):
        for fila in parte.itertuples(index=False, name=None):
            vistos += 1
            soporte[normalizar_titulo(fila[1])] += 1
            if len(muestra) < maximo_vocabulario:
                muestra.append(fila)
            else:
                j = rng.randrange(vistos)
                if j < maximo_vocabulario:
                    muestra[j] = fila
        print(f"[grafo] pasada 1: {vistos:,} vacantes vistas")

    muestra_df = pd.DataFrame(muestra, columns=COLUMNAS_VACANTE + ["descripcion"])
    vocabulario = construir_vocabulario(muestra_df, maximo_terminos=maximo_terminos)
    print(f"[grafo] vocabulario endógeno: {len(vocabulario):,} términos")

    cualificadas = {o for o, n in soporte.items() if o is not None and n >= minimo_ocupacion}
    vacantes_partes: list[pd.DataFrame] = []
    relaciones_partes: list[pd.DataFrame] = []
    for parte, ruta, revision_resuelta in iterar_vacantes_hf(
        repo_id, revision, ["id_vacante", "titulo", "descripcion"]
    ):
        ocupacion = parte["titulo"].map(normalizar_titulo)
        sub = parte[ocupacion.isin(cualificadas)]
        if sub.empty:
            continue
        relaciones_partes.append(extraer_relaciones(sub, vocabulario))
        vacantes_partes.append(sub[COLUMNAS_VACANTE])
        print(f"[grafo] pasada 2 {ruta.name}: {len(sub):,} vacantes cualificadas")

    vacantes = pd.concat(vacantes_partes, ignore_index=True).drop_duplicates("id_vacante")
    relaciones = pd.concat(relaciones_partes, ignore_index=True)
    nodos, aristas, auditoria = construir_tablas_grafo(
        vacantes, relaciones, minimo_ocupacion, minimo_arista
    )
    salida.mkdir(parents=True, exist_ok=True)
    nodos.to_csv(salida / "nodos.csv", index=False)
    aristas.to_csv(salida / "aristas.csv", index=False)
    auditoria.to_parquet(salida / "vacante_habilidad.parquet", index=False)
    vocabulario.to_csv(salida / "vocabulario.csv", index=False)
    manifiesto = {
        "repo_id": repo_id,
        "revision_solicitada": revision,
        "revision_resuelta": revision_resuelta,
        "origen_vocabulario": "endogeno-hf",
        "muestra_vocabulario": len(muestra_df),
        "terminos_vocabulario": len(vocabulario),
        "minimo_ocupacion": minimo_ocupacion,
        "minimo_arista": minimo_arista,
        "semilla": semilla,
        "vacantes_cualificadas": len(vacantes),
        "relaciones_vacante_termino": len(auditoria),
        "nodos": len(nodos),
        "aristas": len(aristas),
        "generado_utc": datetime.now(timezone.utc).isoformat(),
    }
    (salida / "manifiesto.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifiesto, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera el grafo cargo–término desde Hugging Face (vocabulario endógeno)"
    )
    parser.add_argument("--repo", default=REPO_HF_DEFECTO)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--salida", type=Path, default=RUTA_GRAFOS)
    parser.add_argument("--minimo-ocupacion", type=int, default=5)
    parser.add_argument("--minimo-arista", type=int, default=3)
    parser.add_argument("--maximo-vocabulario", type=int, default=60_000)
    parser.add_argument("--maximo-terminos", type=int, default=6000)
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()
    generar_desde_hf(
        args.repo,
        args.revision,
        args.salida,
        args.minimo_ocupacion,
        args.minimo_arista,
        args.maximo_vocabulario,
        args.semilla,
        args.maximo_terminos,
    )


if __name__ == "__main__":
    main()
