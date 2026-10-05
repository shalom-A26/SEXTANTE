import os
from unittest import mock
import tempfile
import unittest
from pathlib import Path

from src.extraccion import base


class CargarEntornoLocalTest(unittest.TestCase):
    """El token de HF vive en `.env` (gitignored), no exportado.

    Sin esto, `capturar_6h.sh` corría el `--pull` sin token y recibía un 401
    que se leía como "el repo no existe".
    """

    def _escribir_env(self, tmp: str, contenido: str) -> Path:
        ruta = Path(tmp) / ".env"
        ruta.write_text(contenido, encoding="utf-8")
        return Path(tmp)

    def test_carga_el_token_desde_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = self._escribir_env(tmp, "HF_TOKEN=hf_secreto\n")
            with mock.patch.dict(os.environ, {}, clear=True):
                base.cargar_entorno_local(raiz)
                self.assertEqual(os.environ["HF_TOKEN"], "hf_secreto")

    def test_no_pisa_lo_ya_exportado(self):
        """`HF_TOKEN=... python -m ...` en la linea de comandos manda."""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = self._escribir_env(tmp, "HF_TOKEN=hf_del_env\n")
            with mock.patch.dict(os.environ, {"HF_TOKEN": "hf_exportado"}, clear=True):
                base.cargar_entorno_local(raiz)
                self.assertEqual(os.environ["HF_TOKEN"], "hf_exportado")

    def test_ignora_comentarios_lineas_vacias_y_espacios(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = self._escribir_env(
                tmp, '# comentario\n\n  HF_TOKEN = "hf_con_espacios"  \nSIN_IGUAL\n'
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                base.cargar_entorno_local(raiz)
                self.assertEqual(os.environ["HF_TOKEN"], "hf_con_espacios")

    def test_sin_archivo_no_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {}, clear=True):
                base.cargar_entorno_local(Path(tmp))  # no debe lanzar

    def test_sin_permiso_de_lectura_no_revienta(self):
        """Un `.env` ilegible no debe tumbar la captura."""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / ".env").write_text("HF_TOKEN=x\n", encoding="utf-8")
            (raiz / ".env").chmod(0o000)
            try:
                with mock.patch.dict(os.environ, {}, clear=True):
                    base.cargar_entorno_local(raiz)  # no debe lanzar
            finally:
                (raiz / ".env").chmod(0o600)

    def test_no_imprime_el_token(self):
        """El valor no debe aparecer en stdout/stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = self._escribir_env(tmp, "HF_TOKEN=hf_no_imprimir\n")
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch("builtins.print") as p:
                    base.cargar_entorno_local(raiz)
                self.assertFalse(p.called, "cargar_entorno_local no debe imprimir")


if __name__ == "__main__":
    unittest.main()