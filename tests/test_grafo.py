import unittest

import pandas as pd

from src.grafos.construir_grafo import construir_tablas_grafo


class GrafoTest(unittest.TestCase):
    def test_peso_cuenta_vacantes_distintas(self):
        vacantes = pd.DataFrame({
            "id_vacante": ["1", "2", "3"],
            "titulo": ["Analista de datos", "Analista de datos", "Científico de datos"],
        })
        relaciones = pd.DataFrame({
            "id_vacante": ["1", "1", "2", "3"],
            "titulo": ["Analista de datos"] * 2 + ["Analista de datos", "Científico de datos"],
            "esco_uri": ["uri/python", "uri/python", "uri/sql", "uri/python"],
            "skill_nombre": ["Python", "Python", "SQL", "Python"],
            "termino_detectado": ["python", "python", "sql", "python"],
            "version_esco": ["1.2.1"] * 4,
        })
        nodos, aristas, audit = construir_tablas_grafo(vacantes, relaciones, 1, 1)
        self.assertEqual(len(nodos[nodos.tipo.eq("ocupacion")]), 2)
        self.assertEqual(aristas["peso"].max(), 1)
        self.assertEqual(len(audit), 3)


if __name__ == "__main__":
    unittest.main()
