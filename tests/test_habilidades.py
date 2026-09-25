import unittest

import pandas as pd

from src.procesamiento.habilidades import (
    construir_vocabulario,
    extraer_relaciones,
    normalizar_texto,
    texto_preparado,
)

COLUMNAS = ["id_vacante", "titulo", "descripcion"]

CONTENIDO = [
    "python con analitica",
    "reportes de python",
    "automatizacion con python",
    "modelos de python",
    "limpieza y python",
    "dashboards en python",
]


def _corpus(n: int = 12) -> pd.DataFrame:
    filas = []
    for i in range(n):
        if i < len(CONTENIDO):
            descripcion = CONTENIDO[i]
        else:
            descripcion = "atencion al cliente y trabajo en equipo"
        filas.append({
            "id_vacante": str(i),
            "titulo": "Analista de datos" if i % 2 == 0 else "Soporte técnico",
            "descripcion": descripcion,
        })
    return pd.DataFrame(filas, columns=COLUMNAS)


class HabilidadesTest(unittest.TestCase):
    def test_normalizacion_unicode(self):
        self.assertEqual(normalizar_texto("Análisis con C#"), "analisis con c#")

    def test_mojibake_reparado(self):
        self.assertEqual(normalizar_texto("confecciÃ³n"), "confeccion")

    def test_texto_preparado_quita_stopwords(self):
        texto = texto_preparado("Se requiere experiencia en python para el cargo")
        self.assertNotIn(" para ", f" {texto} ")
        self.assertIn("python", texto)

    def test_vocabulario_endogeno_detecta_termino_relevante(self):
        vocab = construir_vocabulario(
            _corpus(),
            minimo_vacantes=2,
            proporcion_maxima=0.95,
            minimo_ocupaciones_docs=2,
            maximo_terminos=50,
        )
        terminos = set(vocab["termino"])
        self.assertIn("python", terminos)
        self.assertLessEqual(len(vocab), 50)
        self.assertCountEqual(vocab.columns, ["termino", "frecuencia", "ocupaciones", "senal", "ngrama"])
        self.assertEqual(vocab["frecuencia"].max(), 6)

    def test_extraer_relaciones_respeta_limites_de_palabra(self):
        vocab = pd.DataFrame({
            "termino": ["python"],
            "frecuencia": [6],
            "ocupaciones": [2],
            "senal": [10.0],
            "ngrama": [1],
        })
        rel = extraer_relaciones(_corpus(), vocab)
        ids = set(rel["id_vacante"])
        self.assertEqual(ids, {str(i) for i in range(6)})
        self.assertTrue((rel["termino"] == "python").all())
        self.assertFalse(rel.duplicated(["id_vacante", "termino"]).any())


if __name__ == "__main__":
    unittest.main()
