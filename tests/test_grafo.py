import unittest

import pandas as pd

from src.grafos.construir_grafo import construir_tablas_grafo


def _relaciones(filas: list[tuple[str, str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(filas, columns=["id_vacante", "termino_id", "termino"])
    df["titulo"] = df["id_vacante"].map({"1": "Analista de datos", "2": "Analista de datos"})
    df["frecuencia_termino"] = 3
    return df


class GrafoTest(unittest.TestCase):
    def test_peso_cuenta_vacantes_distintas(self):
        vacantes = pd.DataFrame({
            "id_vacante": ["1", "2", "3"],
            "titulo": ["Analista de datos", "Analista de datos", "Científico de datos"],
        })
        relaciones = _relaciones([
            ("1", "term_a", "python"),
            ("1", "term_a", "python"),
            ("2", "term_a", "python"),
            ("2", "term_b", "sql"),
            ("3", "term_a", "python"),
        ])
        nodos, aristas, audit = construir_tablas_grafo(vacantes, relaciones, 1, 1)
        self.assertEqual(len(nodos[nodos.tipo.eq("ocupacion")]), 2)
        self.assertEqual(len(nodos[nodos.tipo.eq("habilidad")]), 2)
        self.assertEqual(len(aristas), 3)
        analista = aristas[aristas.source.eq(nodos[nodos.nombre.eq("Analista de datos")].node_id.iloc[0])]
        self.assertEqual(analista[analista.target.eq("term_a")]["peso"].iloc[0], 2)
        self.assertEqual(aristas["peso"].max(), 2)
        self.assertEqual(len(audit), 4)
        self.assertTrue(
            nodos["node_id"].isin(set(aristas["source"]) | set(aristas["target"])).all()
        )

    def test_ocupaciones_sin_arista_no_pasan_al_grafo(self):
        vacantes = pd.DataFrame({
            "id_vacante": ["1", "2"],
            "titulo": ["Analista de datos", "Ingeniero civil"],
        })
        relaciones = _relaciones([("1", "term_a", "python")])
        relaciones["titulo"] = ["Analista de datos"]
        nodos, aristas, _ = construir_tablas_grafo(vacantes, relaciones, 1, 1)
        self.assertEqual(set(nodos[nodos.tipo.eq("ocupacion")]["nombre"]), {"Analista de datos"})
        self.assertEqual(len(aristas), 1)


if __name__ == "__main__":
    unittest.main()
