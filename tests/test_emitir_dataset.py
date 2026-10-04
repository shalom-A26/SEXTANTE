import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.extraccion import emitir_dataset as ed
from src.extraccion.esquema import COLUMNAS_ESQUEMA


def _fila(id_: str, captura: str, almacen: str = "spe", **extra) -> dict:
    fila = {
        "id_vacante": id_,
        "portal": "spe" if almacen == "spe" else "elempleo",
        "url": f"https://ejemplo.co/{id_}",
        "titulo": f"Vacante {id_}",
        "empresa": "Empresa SA",
        "ciudad": "Bogotá",
        "departamento": "Cundinamarca",
        "fecha_publicacion": "2026-09-01",
        "descripcion": "Se requiere experiencia en datos.",
        "salario_texto": "$2.000.000 - $3.000.000",
        "salario_min": 2_000_000,
        "salario_max": 3_000_000,
        "tipo_contrato": "Término indefinido",
        "modalidad": None,
        "nivel_educativo": "Universitario",
        "experiencia_texto": "24 meses",
        "fecha_captura": captura,
        "almacen": almacen,
    }
    fila.update(extra)
    return fila


class BasePublicadoTemporal:
    """Redirige `RUTA_BASE_PUBLICADO` a un temporal.

    Sin esto los tests escriben y borran el `data/raw/_publicado.json` real, que
    es estado de la corrida de producción.
    """

    def _aislar_base_publicado(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        original = ed.RUTA_BASE_PUBLICADO
        ed.RUTA_BASE_PUBLICADO = Path(tmp.name) / "_publicado.json"
        self.addCleanup(setattr, ed, "RUTA_BASE_PUBLICADO", original)
        return ed.RUTA_BASE_PUBLICADO


class ParticionSemanalTest(unittest.TestCase):
    def test_agrupa_por_semana_de_captura(self):
        filas = [
            _fila("a", "2026-09-30 06:00:00"),
            _fila("b", "2026-10-01 06:00:00"),  # misma semana ISO que la anterior
            _fila("c", "2026-10-05 06:00:00"),  # semana siguiente
        ]
        semanas = ed.particionar_por_semana(pd.DataFrame(filas))
        self.assertEqual(sorted(semanas), ["semana-2026-W40.parquet", "semana-2026-W41.parquet"])
        self.assertEqual(len(semanas["semana-2026-W40.parquet"]), 2)
        self.assertEqual(list(semanas["semana-2026-W40.parquet"]["id_vacante"]), ["a", "b"])

    def test_filas_sin_fecha_no_se_pierden(self):
        filas = [_fila("a", None), _fila("b", "2026-10-05 06:00:00")]
        filas[0]["fecha_captura"] = None
        semanas = ed.particionar_por_semana(pd.DataFrame(filas))
        self.assertIn(ed.ARCHIVO_SIN_FECHA, semanas)
        self.assertEqual(len(semanas[ed.ARCHIVO_SIN_FECHA]), 1)

    def test_escritura_es_determinista_si_el_contenido_no_cambia(self):
        """Si los bytes cambian, upload_folder los vuelve a subir: se pierde el ahorro."""
        df = pd.DataFrame([
            _fila("a", "2026-10-01 06:00:00"),
            _fila("b", "2026-10-01 06:00:00"),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            primera = ed.particionar_por_semana(df)["semana-2026-W40.parquet"]
            segunda = ed.particionar_por_semana(df.sample(frac=1, random_state=7))["semana-2026-W40.parquet"]
            ruta = Path(tmp) / "x.parquet"
            primera.to_parquet(ruta, index=False)
            h1 = hashlib.sha256(ruta.read_bytes()).hexdigest()
            ruta.unlink()
            segunda.to_parquet(ruta, index=False)
            h2 = hashlib.sha256(ruta.read_bytes()).hexdigest()
        self.assertEqual(h1, h2)

    def test_orden_interno_por_id_vacante(self):
        df = pd.DataFrame([
            _fila("z", "2026-10-01 06:00:00"),
            _fila("a", "2026-10-01 06:00:00"),
        ])
        parte = ed.particionar_por_semana(df)["semana-2026-W40.parquet"]
        self.assertEqual(list(parte["id_vacante"]), ["a", "z"])


class ConsolidarTest(unittest.TestCase):
    def test_une_los_dos_stores_con_columna_almacen(self):
        with tempfile.TemporaryDirectory() as tmp:
            spe = Path(tmp) / "spe.parquet"
            curado = Path(tmp) / "vacantes.csv"
            pd.DataFrame([_fila("a", "2026-10-01 06:00:00")]).drop(columns=["almacen"]).to_parquet(
                spe, index=False
            )
            pd.DataFrame([_fila("b", "2026-10-01 06:00:00", almacen="curado")]).drop(
                columns=["almacen"]
            ).to_csv(curado, index=False)

            unido = ed.consolidar(spe, curado)

        self.assertEqual(sorted(unido["almacen"]), ["curado", "spe"])
        self.assertEqual(len(unido), 2)

    def test_sin_datos_falla_con_mensaje(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                ed.consolidar(Path(tmp) / "no.parquet", Path(tmp) / "no.csv")


class EstadoTest(BasePublicadoTemporal, unittest.TestCase):
    def _emitir(self, filas: list[dict], base_publicado: dict | None) -> dict:
        base_pub = self._aislar_base_publicado()
        if base_publicado is None:
            base_pub.unlink(missing_ok=True)
        else:
            base_pub.write_text(json.dumps(base_publicado), encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            dir_ds = ed.emitir_hf(pd.DataFrame(filas), "pxtron/test", Path(tmp))
            return json.loads((dir_ds / "estado.json").read_text("utf-8"))

    def test_reporta_cuantas_filas_son_nuevas(self):
        filas = [_fila("a", "2026-10-01 06:00:00"), _fila("b", "2026-10-01 06:00:00")]
        estado = self._emitir(filas, {"filas": 1})
        self.assertEqual(estado["filas"], 2)
        self.assertEqual(estado["filas_nuevas"], 1)

    def test_sin_crecimiento_queda_registrado(self):
        """La señal que delata una fuente caída: el corpus no creció."""
        filas = [_fila("a", "2026-10-01 06:00:00")]
        estado = self._emitir(filas, {"filas": 1})
        self.assertEqual(estado["filas_nuevas"], 0)

    def test_sin_pull_no_se_inventa_un_crecimiento(self):
        filas = [_fila("a", "2026-10-01 06:00:00")]
        estado = self._emitir(filas, None)
        self.assertIsNone(estado["filas_nuevas"])


class EmitirHFTest(unittest.TestCase):
    def test_escribe_archivos_semanales_y_card(self):
        filas = [
            _fila("a", "2026-09-30 06:00:00"),
            _fila("b", "2026-10-05 06:00:00"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            dir_ds = ed.emitir_hf(pd.DataFrame(filas), "pxtron/test", Path(tmp))
            data = sorted(p.name for p in (dir_ds / "data").glob("*.parquet"))
            card = (dir_ds / "README.md").read_text("utf-8")
            self.assertEqual(data, ["semana-2026-W40.parquet", "semana-2026-W41.parquet"])
            self.assertIn("Layout semanal", card)
            self.assertNotIn("store/", card)
            # Todo parquet publicado debe llevar el esquema canónico completo.
            leido = pd.read_parquet(dir_ds / "data" / data[0])
            self.assertEqual(list(leido.columns), COLUMNAS_ESQUEMA + ["almacen"])


if __name__ == "__main__":
    unittest.main()