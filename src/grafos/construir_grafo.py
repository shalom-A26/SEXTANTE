"""Construcción reproducible del grafo bipartito cargo–habilidad."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analisis.datos_hf import REPO_HF_DEFECTO, iterar_vacantes_hf
from src.analisis.metricas import normalizar_titulo
from src.procesamiento.habilidades import ExtractorESCO, cargar_catalogo_esco, extraer_habilidades_dataframe

RUTA_GRAFOS = Path("data/procesados/grafos")


def _id_ocupacion(titulo_normalizado: str) -> str:
    digest = hashlib.sha1(titulo_normalizado.encode("utf-8")).hexdigest()[:16]
    return f"occ_{digest}"


def _id_skill(uri: str) -> str:
    identificador = uri.rstrip("/").rsplit("/", 1)[-1]
    return f"skill_{identificador}"


def construir_tablas_grafo(
    vacantes: pd.DataFrame,
    relaciones: pd.DataFrame,
    minimo_ocupacion: int = 5,
    minimo_arista: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_todas = vacantes[["id_vacante", "titulo"]].drop_duplicates("id_vacante").copy()
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
    nodos_occ = ocupaciones.assign(tipo="ocupacion", esco_uri=pd.NA)[["node_id", "nombre", "tipo", "frecuencia", "esco_uri"]]

    rel_todas = relaciones.merge(base_todas[["id_vacante", "ocupacion_id"]], on="id_vacante", how="inner")
    rel = rel_todas[rel_todas["ocupacion_id"].isin(base["ocupacion_id"])].copy()
    rel = rel.drop_duplicates(["id_vacante", "ocupacion_id", "esco_uri"])
    aristas = rel.groupby(["ocupacion_id", "esco_uri"]).agg(peso=("id_vacante", "nunique"), skill_nombre=("skill_nombre", "first")).reset_index()
    aristas = aristas[aristas["peso"] >= minimo_arista].copy()
    aristas["source"] = aristas["ocupacion_id"]
    aristas["target"] = aristas["esco_uri"].map(_id_skill)
    frec_occ = frecuentes.rename_axis("ocupacion_clave").reset_index()
    frec_occ["source"] = frec_occ["ocupacion_clave"].map(_id_ocupacion)
    aristas = aristas.merge(frec_occ[["source", "count"]].rename(columns={"count": "frecuencia_ocupacion"}), on="source") if "count" in frec_occ else aristas.merge(frec_occ[["source", "frecuencia"]].rename(columns={"frecuencia": "frecuencia_ocupacion"}), on="source")
    aristas["proporcion_ocupacion"] = aristas["peso"] / aristas["frecuencia_ocupacion"]

    # Las tablas representan el grafo efectivo: no conservar ocupaciones que
    # quedaron aisladas después de aplicar el soporte mínimo de arista.
    nodos_occ = nodos_occ[nodos_occ["node_id"].isin(aristas["source"])]

    skills = rel_todas[rel_todas["esco_uri"].isin(aristas["esco_uri"])].groupby("esco_uri").agg(nombre=("skill_nombre", "first"), frecuencia=("id_vacante", "nunique")).reset_index()
    skills["node_id"] = skills["esco_uri"].map(_id_skill)
    nodos_skill = skills.assign(tipo="habilidad")[["node_id", "nombre", "tipo", "frecuencia", "esco_uri"]]
    nodos = pd.concat([nodos_occ, nodos_skill], ignore_index=True)
    salida_aristas = aristas[["source", "target", "peso", "proporcion_ocupacion"]].sort_values(["source", "peso"], ascending=[True, False])
    auditoria = rel_todas[["id_vacante", "ocupacion_id", "esco_uri", "skill_nombre", "termino_detectado", "version_esco"]].drop_duplicates()
    return nodos, salida_aristas, auditoria


def generar_desde_hf(
    repo_id: str,
    revision: str,
    esco_dir: Path,
    salida: Path = RUTA_GRAFOS,
    minimo_ocupacion: int = 5,
    minimo_arista: int = 3,
) -> None:
    catalogo = cargar_catalogo_esco(esco_dir)
    extractor = ExtractorESCO(catalogo)
    vacantes_partes, relaciones_partes = [], []
    revision_resuelta = revision
    shards = []
    for df, ruta, revision_resuelta in iterar_vacantes_hf(repo_id, revision, ["id_vacante", "titulo", "descripcion"]):
        shards.append(str(ruta))
        vacantes_partes.append(df[["id_vacante", "titulo"]])
        relaciones_partes.append(extraer_habilidades_dataframe(df, extractor))
        print(f"[grafo] {ruta.name}: {len(df):,} vacantes")
    vacantes = pd.concat(vacantes_partes, ignore_index=True)
    relaciones = pd.concat(relaciones_partes, ignore_index=True)
    nodos, aristas, auditoria = construir_tablas_grafo(vacantes, relaciones, minimo_ocupacion, minimo_arista)
    salida.mkdir(parents=True, exist_ok=True)
    nodos.to_csv(salida / "nodos.csv", index=False)
    aristas.to_csv(salida / "aristas.csv", index=False)
    auditoria.to_parquet(salida / "vacante_habilidad.parquet", index=False)
    manifiesto = {
        "repo_id": repo_id, "revision_solicitada": revision,
        "revision_resuelta": revision_resuelta, "shards": shards,
        "version_esco": str(catalogo["version_esco"].iloc[0]),
        "minimo_ocupacion": minimo_ocupacion, "minimo_arista": minimo_arista,
        "vacantes": len(vacantes), "relaciones_vacante_habilidad": len(auditoria),
        "nodos": len(nodos), "aristas": len(aristas),
        "generado_utc": datetime.now(timezone.utc).isoformat(),
    }
    (salida / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifiesto, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el grafo cargo–habilidad desde Hugging Face y ESCO")
    parser.add_argument("--repo", default=REPO_HF_DEFECTO)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--esco-dir", type=Path, default=Path("data/referencias/esco"))
    parser.add_argument("--salida", type=Path, default=RUTA_GRAFOS)
    parser.add_argument("--minimo-ocupacion", type=int, default=5)
    parser.add_argument("--minimo-arista", type=int, default=3)
    args = parser.parse_args()
    generar_desde_hf(args.repo, args.revision, args.esco_dir, args.salida, args.minimo_ocupacion, args.minimo_arista)


if __name__ == "__main__":
    main()
