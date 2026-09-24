import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.procesamiento.habilidades import cargar_catalogo_esco, normalizar_texto


class HabilidadesTest(unittest.TestCase):
    def test_normalizacion_unicode(self):
        self.assertEqual(normalizar_texto("Análisis con C#"), "analisis con c#")

    def test_catalogo_marca_alias_ambiguo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "skills_es.csv"
            pd.DataFrame({
                "conceptUri": ["uri/a", "uri/b"],
                "preferredLabel": ["análisis de datos", "gestión de datos"],
                "altLabels": ["datos", "datos"],
            }).to_csv(ruta, index=False)
            catalogo = cargar_catalogo_esco(tmp)
            ambiguos = catalogo[catalogo.termino.eq("datos")]
            self.assertTrue(ambiguos["ambiguo"].all())


if __name__ == "__main__":
    unittest.main()
