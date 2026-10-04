import hashlib
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.extraccion import sync_hf
from src.extraccion import emitir_dataset as ed
from src.extraccion.esquema import COLUMNAS_ESQUEMA
from src.extraccion.portales.spe import guardar_parquet

# Fechas en dos semanas distintas: los archivos semanales solo son inmutables si
# el round-trip no mueve filas de un archivo a otro.
CAPTURA_A = "2026-09-30 06:00:00"   # semana ISO 2026-W40
CAPTURA_B = "2026-10-05 06:00:00"   # semana ISO 2026-W41


def _filas_spe() -> list[dict]:
    base = {
        "portal": "spe",
        "empresa": "Empresa SA",
        "ciudad": "Bogotá",
        "departamento": "Cundinamarca",
        "fecha_publicacion": "2026-09-01",
        "descripcion": "Se requiere experiencia en datos y en python.",
        "salario_texto": "$2.000.000 - $3.000.000",
        "salario_min": 2_000_000,
        "salario_max": 3_000_000,
        "tipo_contrato": "Término indefinido",
        "modalidad": None,
        "nivel_educativo": "Universitario",
        "experiencia_texto": "24 meses",
    }
    filas = [
        {**base, "id_vacante": "spe-1", "url": "https://spe.co/1", "titulo": "Analista", "fecha_captura": CAPTURA_A},
        {**base, "id_vacante": "spe-2", "url": "https://spe.co/2", "titulo": "Ingeniero", "fecha_captura": CAPTURA_B},
        # Sin descripción y sin modalidad: los nulos también deben sobrevivir.
        {**base, "id_vacante": "spe-3", "url": "https://spe.co/3", "titulo": "Auxiliar",
         "descripcion": None, "modalidad": None, "fecha_captura": CAPTURA_A},
    ]
    return filas


def _filas_curado() -> list[dict]:
    return [{
        "id_vacante": "elempleo-1",
        "portal": "elempleo",
        "url": "https://elempleo.co/1",
        "titulo": "Contador",
        "empresa": "Co SAS",
        "ciudad": "Medellín",
        "departamento": "Antioquia",
        "fecha_publicacion": "2026-09-20",
        "descripcion": "Se requiere contador con experiencia.",
        "salario_texto": None,
        "salario_min": None,
        "salario_max": None,
        "tipo_contrato": "Contrato de trabajo",
        "modalidad": "Teletrabajo",
        "nivel_educativo": "Universitario",
        "experiencia_texto": "12 meses",
        "fecha_captura": CAPTURA_B,
    }]


def _escribir_stores(ruta_spe: Path, ruta_curado: Path) -> None:
    guardar_parquet(pd.DataFrame(_filas_spe()), ruta_spe)
    ruta_curado.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(_filas_curado())[COLUMNAS_ESQUEMA].to_csv(ruta_curado, index=False)


def _hashes(data_dir: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(data_dir.glob("*.parquet"))
    }


class RestaurarStoresTest(unittest.TestCase):
    def test_reparte_por_almacen_en_el_archivo_correcto(self):
        publicado = pd.concat(
            [pd.DataFrame(_filas_spe()), pd.DataFrame(_filas_curado())],
            ignore_index=True,
        ).assign(almacen=["spe", "spe", "spe", "curado"])

        with tempfile.TemporaryDirectory() as tmp:
            spe = Path(tmp) / "spe" / "vacantes_spe.parquet"
            curado = Path(tmp) / "vacantes.csv"
            conteos = sync_hf.restaurar_stores(publicado, spe, curado)

            spe_df = pd.read_parquet(spe)
            curado_df = pd.read_csv(curado, dtype=str)

        self.assertEqual(conteos["filas_spe"], 3)
        self.assertEqual(conteos["filas_curado"], 1)
        self.assertNotIn("almacen", spe_df.columns)
        self.assertEqual(list(spe_df.columns), COLUMNAS_ESQUEMA)
        self.assertEqual(list(curado_df["id_vacante"]), ["elempleo-1"])

    def test_sin_columna_almacen_falla_con_mensaje(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                sync_hf.restaurar_stores(
                    pd.DataFrame(_filas_spe()),
                    Path(tmp) / "spe.parquet",
                    Path(tmp) / "vacantes.csv",
                )


class RoundTripTest(unittest.TestCase):
    """Publicar -> restaurar -> republicar debe dar el mismo dataset, byte a byte.

    Es la garantía de que los archivos semanales son inmutables: si el round-trip
    cambiara un solo byte de una semana ya publicada, `upload_folder` la volvería
    a subir en cada corrida y el consumo de Hugging Face volvería a crecer.
    """

    def test_republicar_despues_de_restaurar_no_cambia_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            spe, curado = raiz / "raw" / "spe" / "vacantes_spe.parquet", raiz / "raw" / "vacantes.csv"
            _escribir_stores(spe, curado)

            # 1) Primera emisión.
            dir_ds = ed.emitir_hf(ed.consolidar(spe, curado), "pxtron/test", raiz / "emitido1")
            antes = _hashes(dir_ds / "data")
            self.assertEqual(
                sorted(antes), ["semana-2026-W40.parquet", "semana-2026-W41.parquet"]
            )

            # 2) Lo que hace `sync_hf --pull`: recomponer los stores desde lo publicado.
            spe.unlink()
            curado.unlink()
            publicado = pd.concat(
                [pd.read_parquet(p) for p in sorted((dir_ds / "data").glob("*.parquet"))],
                ignore_index=True,
            )
            sync_hf.restaurar_stores(publicado, spe, curado)

            # 3) Segunda emisión, sin capturar nada nuevo.
            dir_ds2 = ed.emitir_hf(ed.consolidar(spe, curado), "pxtron/test", raiz / "emitido2")
            despues = _hashes(dir_ds2 / "data")

            ids_1 = set(pd.read_parquet(dir_ds / "data" / "semana-2026-W40.parquet")["id_vacante"])
            ids_2 = set(pd.read_parquet(dir_ds2 / "data" / "semana-2026-W40.parquet")["id_vacante"])

        self.assertEqual(antes, despues, "el round-trip alteró los archivos ya publicados")
        self.assertEqual(ids_1, ids_2)

    def test_capturar_nuevo_solo_cambia_el_archivo_de_la_semana_en_curso(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            spe, curado = raiz / "raw" / "spe" / "vacantes_spe.parquet", raiz / "raw" / "vacantes.csv"
            _escribir_stores(spe, curado)

            dir_ds = ed.emitir_hf(ed.consolidar(spe, curado), "pxtron/test", raiz / "emitido1")
            antes = _hashes(dir_ds / "data")

            # Llega una vacante nueva de la semana en curso (W41).
            nueva = {**_filas_spe()[0], "id_vacante": "spe-99", "titulo": "Nuevo",
                      "fecha_captura": CAPTURA_B}
            nuevas = guardar_parquet(pd.DataFrame([nueva]), spe)
            self.assertEqual(nuevas, 1)

            dir_ds2 = ed.emitir_hf(ed.consolidar(spe, curado), "pxtron/test", raiz / "emitido2")
            despues = _hashes(dir_ds2 / "data")

        self.assertEqual(antes["semana-2026-W40.parquet"], despues["semana-2026-W40.parquet"])
        self.assertNotEqual(antes["semana-2026-W41.parquet"], despues["semana-2026-W41.parquet"])


class CongelamientoTest(unittest.TestCase):
    def test_reobservar_una_vacante_no_reescribe_el_store(self):
        """`keep="first"`: la descripción se congela con la primera observación."""
        with tempfile.TemporaryDirectory() as tmp:
            spe = Path(tmp) / "vacantes_spe.parquet"
            guardar_parquet(pd.DataFrame(_filas_spe()), spe)

            otra = {**_filas_spe()[0], "descripcion": "TEXTO EDITADO DESPUES", "fecha_captura": CAPTURA_B}
            nuevas = guardar_parquet(pd.DataFrame([otra]), spe)
            df = pd.read_parquet(spe)

        self.assertEqual(nuevas, 0, "una vacante ya vista no debe contar como nueva")
        self.assertEqual(len(df), 3)
        self.assertEqual(
            df.loc[df["id_vacante"].eq("spe-1"), "descripcion"].iloc[0],
            "Se requiere experiencia en datos y en python.",
        )
        self.assertEqual(
            df.loc[df["id_vacante"].eq("spe-1"), "fecha_captura"].iloc[0], CAPTURA_A
        )


if __name__ == "__main__":
    unittest.main()