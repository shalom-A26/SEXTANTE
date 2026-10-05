"""Emisión del dataset SEXTANTE: archivos semanales para Hugging Face.

Une los dos stores canónicos (corpus grande SPE en parquet y corpus curado en
CSV, ambos en el esquema canónico de 17 columnas) y produce un único dataset
publicado en `data/`, particionado por semana de `fecha_captura`:

    data/semana-2026-W40.parquet      ← vacantes vistas por primera vez esa semana
    README.md                          ← dataset card (procedencia y ética)
    estado.json                        ← conteos de la corrida (no se publica)

Por qué semanal y no el layout anterior (`store/` + shards `train-*-of-*`):

  - Los archivos son **inmutables**. Cada fila se escribe en el archivo de la
    semana en que la vimos por primera vez y, como el store es append-only
    (`keep="first"`), esa fila nunca cambia. El único archivo que se reescribe es
    el de la semana en curso, que crece.
  - `huggingface_hub.upload_folder` omite los archivos cuyo contenido ya está en
    el repo ("already present upstream - skipping upload"), así que publicar sale
    barata: ~45 MB por corrida en vez de ~1,5 GB.
  - Desaparecen las dos copias del corpus (una en `store/`, otra en los shards) y
    los shards de generaciones anteriores que nunca se borraban.

La clave de partición es `fecha_captura` y **no** `fecha_publicacion`: una
vacante de marzo que el export entrega en octubre debe archivarse en el cajón de
octubre (cuando la vimos). Si se archivara en marzo habría que reabrir y reescribir
un archivo ya publicado cada vez que el export entregara histórico tardío.

La subida requiere la variable de entorno HF_TOKEN (token con permiso de escritura).

Uso:
    python -m src.extraccion.emitir_dataset                      # solo genera el directorio
    python -m src.extraccion.emitir_dataset --hf-upload --hf-repo pxtron/vacantes-colombia
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.extraccion.esquema import COLUMNAS_ESQUEMA

from . import base
from .portales.spe import RUTA_PARQUET_SPE, contar_filas

RUTA_EMITIDO = base.RUTA_DATOS / "emitido"
NOMBRE_DATASET = "vacantes-colombia"
REPO_HF_DEFECTO = "SEXTANTE/vacantes-colombia"

# Datos que deja `sync_hf --pull` para que la emisión sepa cuántas vacantes
# había publicadas antes de esta corrida (y así reportar el crecimiento real).
RUTA_BASE_PUBLICADO = base.RUTA_RAW / "_publicado.json"

# Layout semanal: data/semana-<año ISO>-W<semana>.parquet
PATRON_SEMANA = re.compile(r"^semana-(\d{4})-W(\d{2})\.parquet$")
PREFIJO_SEMANA = "semana-"
SUFIJO_SEMANA = ".parquet"
ARCHIVO_SIN_FECHA = "semana-sin-fecha.parquet"

# Layout anterior (hasta 2026-10-04), eliminado por la migración.
PATRON_SHARD_LEGACY = re.compile(r"^train-\d{5}-of-\d{5}\.parquet$")
PREFIJO_STORE_LEGACY = "store/"

# Columnas que se publican por archivo: el esquema canónico + `almacen`.
COLUMNAS_SALIDA = [*COLUMNAS_ESQUEMA, "almacen"]


# --------------------------------------------------------------------------- #
# Consolidación
# --------------------------------------------------------------------------- #
def consolidar(
    ruta_spe: Path = RUTA_PARQUET_SPE,
    ruta_curado: Path = base.RUTA_VACANTES,
) -> pd.DataFrame:
    """Une el corpus grande SPE con el corpus curado en un solo DataFrame."""
    partes = []
    if ruta_spe.exists():
        spe_df = pd.read_parquet(ruta_spe)
        spe_df["almacen"] = "spe"
        partes.append(spe_df)
    if ruta_curado.exists():
        curado = pd.read_csv(ruta_curado, dtype=str)
        for col in COLUMNAS_ESQUEMA:
            if col not in curado.columns:
                curado[col] = None
        curado = curado[COLUMNAS_ESQUEMA]
        curado["almacen"] = "curado"
        partes.append(curado)
    if not partes:
        raise SystemExit("ERROR: no hay datos en data/raw/ (ejecuta primero src.extraccion.corpus)")
    unido = pd.concat(partes, ignore_index=True)
    for col in ("salario_min", "salario_max"):
        unido[col] = pd.to_numeric(unido[col], errors="coerce")
    return unido


# --------------------------------------------------------------------------- #
# Particionado semanal
# --------------------------------------------------------------------------- #
def _nombre_semana(periodo: pd.Period) -> str:
    """Nombre del archivo de una semana ISO: 2026-W40 -> 'semana-2026-W40.parquet'."""
    return f"{PREFIJO_SEMANA}{periodo.year}-W{periodo.week:02d}{SUFIJO_SEMANA}"


def _periodos_semana(serie: pd.Series) -> pd.Series:
    """Periodos semanales ISO a partir de una serie de fechas.

    Se descarta la zona horaria a propósito (solo se usan año y semana), pero
    silenciado porque el aviso ensucia el log de cada corrida.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return serie.dt.to_period("W")


def _salida_estable(df: pd.DataFrame) -> pd.DataFrame:
    """Deja el DataFrame en una forma reproducible antes de escribirlo.

    Si el contenido lógico de una semana no cambia, el parquet escrito tiene los
    mismos bytes, y por eso `upload_folder` lo omite. Dos cosas lo garantizan:
    los tipos de columna no dependen de qué stores hubiera en la corrida, y las
    filas van ordenadas por `id_vacante`.
    """
    df = df.copy()
    for col in COLUMNAS_SALIDA:
        if col in ("salario_min", "salario_max"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        else:
            serie = df[col]
            df[col] = serie.astype(object).where(serie.notna(), None)
    return df.sort_values("id_vacante", kind="stable").reset_index(drop=True)


def particionar_por_semana(unido: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Reparte el corpus en archivos semanales por `fecha_captura`.

    Devuelve `{nombre_de_archivo: DataFrame}` ordenado por nombre. Las filas sin
    `fecha_captura` caen en `semana-sin-fecha.parquet` (no debería ocurrir: la
    columna se estampa en la captura, pero el bucket evita perder datos).
    """
    df = unido.reset_index(drop=True)
    captura = pd.to_datetime(df["fecha_captura"], errors="coerce", format="mixed", utc=True)
    periodos = _periodos_semana(captura)
    nombres = pd.Series(ARCHIVO_SIN_FECHA, index=df.index, dtype=object)
    validos = periodos.notna()
    if validos.any():
        nombres.loc[validos] = [_nombre_semana(p) for p in periodos[validos]]
    return {nombre: _salida_estable(parte) for nombre, parte in df.groupby(nombres)}


# --------------------------------------------------------------------------- #
# Emisión
# --------------------------------------------------------------------------- #
def _leer_base_publicado() -> dict:
    """Conteos publicados que dejó `sync_hf --pull` (vacío si no hubo pull)."""
    if not RUTA_BASE_PUBLICADO.exists():
        return {}
    try:
        return json.loads(RUTA_BASE_PUBLICADO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _construir_estado(unido: pd.DataFrame, semanas: dict[str, pd.DataFrame]) -> dict:
    """Conteos de la corrida, para el resumen del workflow y para diagnosticar."""
    por_almacen = unido.get("almacen", pd.Series(dtype=str)).value_counts()
    filas = int(len(unido))
    base_pub = _leer_base_publicado()
    publicadas = base_pub.get("filas")
    captura = pd.to_datetime(unido["fecha_captura"], errors="coerce", format="mixed", utc=True)
    semana_actual = _nombre_semana(_periodos_semana(pd.Series([pd.Timestamp.now(tz="UTC")])).iloc[0])
    estado = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "filas": filas,
        "filas_spe": int(por_almacen.get("spe", 0)),
        "filas_curado": int(por_almacen.get("curado", 0)),
        "archivos_semanales": len(semanas),
        "semana_en_curso": semana_actual,
        "filas_semana_en_curso": int(len(semanas.get(semana_actual, ()))),
        "captura_mas_reciente": str(captura.max()) if captura.notna().any() else None,
        "filas_publicadas_previamente": publicadas,
    }
    # Solo tiene sentido comparar si el pull restauró el corpus: sin él, las
    # "nuevas" serían el total y el número no informaría nada.
    estado["filas_nuevas"] = None if publicadas is None else filas - int(publicadas)
    return estado


def emitir_hf(unido: pd.DataFrame, repo_id: str, ruta_padre: Path = RUTA_EMITIDO) -> Path:
    """Genera el directorio del dataset (archivos semanales + dataset card + estado)."""
    dir_ds = ruta_padre / NOMBRE_DATASET
    data_dir = dir_ds / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    semanas = particionar_por_semana(unido)
    for nombre, parte in semanas.items():
        parte.to_parquet(data_dir / nombre, index=False)

    (dir_ds / "README.md").write_text(_dataset_card(unido, semanas), encoding="utf-8")
    estado = _construir_estado(unido, semanas)
    (dir_ds / "estado.json").write_text(
        json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    nuevas = estado["filas_nuevas"]
    detalle = "" if nuevas is None else f", nuevas: {nuevas:+,}"
    print(
        f"[hf] {len(unido):,} vacantes{detalle} en {len(semanas)} archivo(s) semanal(es) "
        f"-> {dir_ds} (repo {repo_id})"
    )
    return dir_ds


def _dataset_card(unido: pd.DataFrame, semanas: dict[str, pd.DataFrame]) -> str:
    por_almacen = unido.get("almacen", pd.Series(dtype=str)).value_counts()
    n_spe = int(por_almacen.get("spe", 0))
    n_curado = int(por_almacen.get("curado", 0))
    captura = pd.to_datetime(unido["fecha_captura"], errors="coerce", format="mixed", utc=True)
    cub = (unido.notna().mean() * 100).round(1).sort_values()
    cub_txt = "\n".join(f"  - {k}: {v}%" for k, v in cub.items() if v < 100)
    lineas = "\n".join(
        f"- `{nombre}`: {len(parte):,} vacantes"
        for nombre, parte in sorted(semanas.items(), reverse=True)
    )
    return f"""---
license: other
---
# {NOMBRE_DATASET}

Dataset académico de vacantes laborales colombianas (proyecto SEXTANTE,
Universidad Tecnológica de Bolívar).

- **Registros**: {len(unido):,} (esquema canónico de 17 columnas + `almacen`).
- **Composición**: {n_spe:,} SPE + {n_curado:,} curado (El Empleo + LinkedIn).
- **Última captura**: {captura.max() if captura.notna().any() else "n/d"}.
- **Layout**: {len(semanas)} archivo(s) parquet semanal(es) bajo `data/`.

## Layout semanal

Cada vacante vive en el archivo de la **semana en que la vimos por primera
vez**, y las filas están congeladas: una vacante que reaparece en un export
posterior no se reescribe. De ahí se siguen dos propiedades:

- Los archivos de semanas ya cerradas son inmutables, así que publicarlos es
  barato: solo se sube el de la semana en curso.
- `fecha_captura` es la **primera** observación, no la última. Con ella se puede
  medir permanencia de la vacante (`fecha_publicacion` → `fecha_captura`).

> Antes del 2026-10-04 el corpus se acumulaba con la última versión observada de
> cada vacante. Para esas filas heredadas `fecha_captura` es la última
> observación; a partir de esa fecha es la primera.

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

{", ".join(list(unido.columns) if "almacen" in unido.columns else COLUMNAS_ESQUEMA)}

## Avisos

- Versión privada para uso académico. No redistribuir sin revisar los
  términos de cada portal de origen (LinkedIn, El Empleo, SPE).
- No contiene datos personales de candidatos; solo información pública de
  ofertas de empleo.

## Cobertura parcial de campos

{cub_txt or "  (cobertura 100% en todas las columnas)"}

## Archivos

{lineas}
"""


# --------------------------------------------------------------------------- #
# Publicación
# --------------------------------------------------------------------------- #
def _rutas_obsoletas(repo_id: str, api) -> list[str]:
    """Rutas del layout anterior que la migración debe eliminar."""
    info = api.repo_info(repo_id, repo_type="dataset")
    return [
        s.rfilename
        for s in info.siblings
        if s.rfilename.startswith(PREFIJO_STORE_LEGACY)
        or PATRON_SHARD_LEGACY.match(Path(s.rfilename).name)
    ]


def _store_restaurado(ruta_spe: Path = RUTA_PARQUET_SPE, ruta_curado: Path = base.RUTA_VACANTES) -> bool:
    """¿Se restauró el corpus acumulado antes de esta corrida?

    Red de seguridad de la migración. Sin `sync_hf --pull` los stores locales
    están casi vacíos, la emisión publicaría un dataset diminuto y borrar el
    layout anterior destruiría el histórico. La comparación es de filas contra
    lo que `sync_hf` dejó registrado en `data/raw/_publicado.json`: si ese archivo
    no está, no se restaura nada y por tanto no se borra nada.
    """
    base_pub = _leer_base_publicado()
    if not base_pub:
        return False
    esperadas = base_pub.get("filas_spe")
    if esperadas is None:
        # No había store del SPE en el repo (migración de un corpus solo curado).
        return ruta_curado.exists() or not base_pub.get("filas_curado")
    # `contar_filas` y no `pd.read_parquet`: el lector de Arrow queda
    # vivo hasta el teardown y puede abortar con exit code 134.
    return ruta_spe.exists() and contar_filas(ruta_spe) >= int(esperadas)


def subir_hf(dir_ds: Path, repo_id: str, ruta_spe: Path = RUTA_PARQUET_SPE) -> None:
    """Sube el directorio del dataset y migra el layout si hace falta."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("ERROR: define HF_TOKEN (huggingface.co/settings/tokens) para --hf-upload")
    from huggingface_hub import HfApi

    api = HfApi()
    if not api.repo_exists(repo_id, repo_type="dataset"):
        api.create_repo(repo_id, repo_type="dataset", private=True)

    # Solo el dataset: `estado.json` es estado operativo de la corrida, no dato.
    api.upload_folder(
        folder_path=str(dir_ds),
        repo_id=repo_id,
        repo_type="dataset",
        allow_patterns=["data/*", "*.md"],
    )

    obsoletas = _rutas_obsoletas(repo_id, api)
    if obsoletas:
        if not _store_restaurado(ruta_spe):
            print(
                "[hf] layout anterior conservado: no consta que `sync_hf --pull` restaurara "
                "el corpus acumulado. Reintenta la corrida antes de migrar."
            )
        else:
            for ruta in obsoletas:
                try:
                    api.delete_file(ruta, repo_id=repo_id, repo_type="dataset")
                    print(f"[hf] eliminado (layout anterior): {ruta}")
                except Exception as exc:  # noqa: BLE001
                    print(f"[hf] no se pudo eliminar '{ruta}': {exc}")

    print(f"[hf] publicado en https://huggingface.co/datasets/{repo_id} (privado)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emite el dataset SEXTANTE a Hugging Face")
    parser.add_argument("--hf-upload", action="store_true", help="Subir a Hugging Face (requiere HF_TOKEN)")
    parser.add_argument("--hf-repo", default=REPO_HF_DEFECTO, help=f"Repo destino (default: {REPO_HF_DEFECTO})")
    args = parser.parse_args()

    unido = consolidar()
    dir_ds = emitir_hf(unido, args.hf_repo)
    if args.hf_upload:
        subir_hf(dir_ds, args.hf_repo)


if __name__ == "__main__":
    main()