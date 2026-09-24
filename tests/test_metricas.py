import unittest

import pandas as pd

from src.analisis.metricas import categorizar_modalidad, preparar_vacantes, resumen_concentracion


class MetricasTest(unittest.TestCase):
    def test_modalidad_nula_no_es_presencial(self):
        self.assertEqual(categorizar_modalidad(None), "Desconocida")
        self.assertEqual(categorizar_modalidad("Teletrabajo"), "Remota/teletrabajo")
        self.assertEqual(categorizar_modalidad("híbrido"), "Híbrida")

    def test_variables_derivadas(self):
        df = pd.DataFrame({
            "id_vacante": ["1", "2"], "portal": ["spe", "linkedin"],
            "titulo": ["12345 Analista de Datos", "Analista de Datos"],
            "empresa": ["A", "B"], "ciudad": ["Bogotá", "Bogotá"],
            "departamento": ["Bogotá", "Bogotá"],
            "fecha_publicacion": ["2026-01-01", "mal"], "fecha_captura": ["2026-01-02"] * 2,
            "descripcion": ["Python", "SQL"], "salario_texto": ["$1 - $2", "USD 100 - 200 (yearly)"],
            "salario_min": [1_000_000, 100], "salario_max": [2_000_000, 200],
            "tipo_contrato": ["Fijo", "Fijo"], "modalidad": [None, "Remoto"],
            "nivel_educativo": ["Universitario", None], "experiencia_texto": ["2 años", "999 meses"],
        })
        out = preparar_vacantes(df)
        self.assertEqual(out.loc[0, "titulo_normalizado"], "analista de datos")
        self.assertEqual(out.loc[0, "experiencia_meses"], 24)
        self.assertTrue(pd.isna(out.loc[1, "experiencia_meses"]))
        self.assertTrue(out.loc[0, "salario_comparable"])
        self.assertFalse(out.loc[1, "salario_comparable"])

    def test_hhi(self):
        df = pd.DataFrame({"departamento": ["A", "A", "B", "B"]})
        self.assertAlmostEqual(resumen_concentracion(df, "departamento")["hhi"], 0.5)


if __name__ == "__main__":
    unittest.main()
