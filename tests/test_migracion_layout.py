import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.extraccion import emitir_dataset as ed

from test_emitir_dataset import BasePublicadoTemporal


class GuardaRedSeguridadTest(BasePublicadoTemporal, unittest.TestCase):
    """La migración borra el layout anterior, así que no puede quedar dormida."""

    def setUp(self):
        self._base = self._aislar_base_publicado()

    def _store(self, tmp: str, ids: list[str]) -> Path:
        ruta = Path(tmp) / "vacantes_spe.parquet"
        pd.DataFrame({"id_vacante": ids}).to_parquet(ruta, index=False)
        return ruta

    def _base_publicado(self, **contenido) -> None:
        self._base.write_text(json.dumps(contenido), encoding="utf-8")

    def test_con_pull_completo_permite_migrar(self):
        with tempfile.TemporaryDirectory() as tmp:
            spe = self._store(tmp, ["a", "b"])
            self._base_publicado(filas=10, filas_spe=2, filas_curado=8)
            self.assertTrue(ed._store_restaurado(spe))

    def test_sin_pull_no_permite_migrar(self):
        """El caso peligroso: stores vacíos, no hay base, no se borra nada."""
        with tempfile.TemporaryDirectory() as tmp:
            spe = self._store(tmp, [])
            self._base.unlink(missing_ok=True)
            self.assertFalse(ed._store_restaurado(spe))

    def test_store_incompleto_no_permite_migrar(self):
        with tempfile.TemporaryDirectory() as tmp:
            spe = self._store(tmp, ["a"])
            self._base_publicado(filas=10, filas_spe=2, filas_curado=8)
            self.assertFalse(ed._store_restaurado(spe))

    def test_store_crecido_si_permite_migrar(self):
        """Con vacantes nuevas, el store local supera al publicado: también vale."""
        with tempfile.TemporaryDirectory() as tmp:
            spe = self._store(tmp, ["a", "b", "c"])
            self._base_publicado(filas=10, filas_spe=2, filas_curado=8)
            self.assertTrue(ed._store_restaurado(spe))

    def test_base_corrupta_no_permite_migrar(self):
        with tempfile.TemporaryDirectory() as tmp:
            spe = self._store(tmp, ["a", "b"])
            self._base.write_text("{no es json", encoding="utf-8")
            self.assertFalse(ed._store_restaurado(spe))


if __name__ == "__main__":
    unittest.main()