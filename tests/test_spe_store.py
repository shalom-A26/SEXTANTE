import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

import pandas as pd
import requests
from requests.exceptions import SSLError

from src.extraccion.portales import spe


class ContarFilasTest(unittest.TestCase):
    """`contar_filas` reemplaza a `pd.read_parquet` para contar filas del store.

    No es solo una optimisation: `pd.read_parquet` levanta el escáner
    thread-pooled de Arrow, y si su lector sobrevive hasta el apagado del
    intérprete el proceso aborta con SIGABRT y exit code 134 (Arrow #34314).
    """

    def _store(self, tmp: str, ids: list[str]) -> Path:
        ruta = Path(tmp) / "vacantes_spe.parquet"
        pd.DataFrame({"id_vacante": ids, "descripcion": ["x"] * len(ids)}).to_parquet(ruta, index=False)
        return ruta

    def test_cuenta_las_filas_del_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(spe.contar_filas(self._store(tmp, ["a", "b", "c"])), 3)

    def test_store_vacio_cuenta_cero(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(spe.contar_filas(self._store(tmp, [])), 0)

    def test_coincide_con_el_lector_de_pandas(self):
        """El conteo por metadata tiene que dar lo mismo que leía el lector."""
        with tempfile.TemporaryDirectory() as tmp:
            ruta = self._store(tmp, ["a", "b"])
            self.assertEqual(
                spe.contar_filas(ruta),
                len(pd.read_parquet(ruta, columns=["id_vacante"])),
            )

    def test_archivo_inexistente_falla(self):
        """Se usa solo cuando el archivo existe; que no lo oculte un default."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                spe.contar_filas(Path(tmp) / "no_existe.parquet")


if __name__ == "__main__":
    unittest.main()

class VerificarSslTest(unittest.TestCase):
    """La cadena CA del SPE está incompleta: la validación falla siempre.

    Antes, cada petición repetía el handshake verificado y fallido antes de
    reintentar sin verificar (100-132 avisos por corrida). Ahora el primer
    fallo decide por el resto de la corrida.
    """

    def setUp(self):
        self.antes = spe._VERIFICAR_SSL
        spe._VERIFICAR_SSL = True

    def tearDown(self):
        spe._VERIFICAR_SSL = self.antes

    def _mock_spe(self, falla_si_verifica):
        """Un solo mock que decide según el kwarg `verify` de cada llamada."""
        modos = []

        def _req(method, url, **kw):
            verify = kw.get("verify", True)
            modos.append(verify)
            if verify and falla_si_verifica:
                raise SSLError("cadena CA incompleta")
            return requests.Response()

        return mock.patch.object(spe.requests, "request", side_effect=_req), modos

    def test_tras_un_sslerror_deja_de_reintentar_con_verificacion(self):
        parche, modos = self._mock_spe(falla_si_verifica=True)
        with parche:
            for _ in range(3):
                spe._request("GET", "https://ejemplo.invalid/x")

        # 3 peticiones: solo la primera debe pagar el intento verificado.
        self.assertEqual(modos, [True, False, False, False])

    def test_advertencia_de_ssl_se_emite_una_sola_vez(self):
        parche, _ = self._mock_spe(falla_si_verifica=True)
        with parche, warnings.catch_warnings(record=True) as vistos:
            warnings.simplefilter("always")
            for _ in range(4):
                spe._request("GET", "https://ejemplo.invalid/x")

        avisos = [w for w in vistos if "SSL" in str(w.message)]
        self.assertEqual(len(avisos), 1, f"esperado 1 aviso, hubo {len(avisos)}")

    def test_si_ssl_funciona_no_se_desactiva_nada(self):
        """Con la cadena bien, nunca se debe caer a verify=False."""
        parche, modos = self._mock_spe(falla_si_verifica=False)
        with parche:
            for _ in range(3):
                spe._request("GET", "https://ejemplo.invalid/x")

        self.assertEqual(modos, [True, True, True])
        self.assertTrue(spe._VERIFICAR_SSL, "una cadena válida no debe desactivar la verificación")

    def test_el_flag_vuelve_a_verificar_en_la_corrida_siguiente(self):
        """El flag es por proceso: una cadena que se arregla se reintenta."""
        parche, _ = self._mock_spe(falla_si_verifica=True)
        with parche:
            spe._request("GET", "https://ejemplo.invalid/x")
        self.assertFalse(spe._VERIFICAR_SSL)

        # Siguiente "corrida" = proceso nuevo: el flag arranca en True.
        spe._VERIFICAR_SSL = True
        parche2, modos = self._mock_spe(falla_si_verifica=False)
        with parche2:
            spe._request("GET", "https://ejemplo.invalid/x")
        self.assertEqual(modos, [True])
