"""Stage 8 API over a synthetic demo run (skipped without API deps)."""

from __future__ import annotations

import io
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - API deps are optional for capture-only setups
    TestClient = None

CV = ("Profesional contable con experiencia en contabilidad, facturación, nómina y "
      "Excel avanzado. Conocimientos de SQL y análisis de datos.")


@unittest.skipIf(TestClient is None, "requires requirements-api.txt")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sextante_analysis.demo import run_demo
        from sextante_api.main import create_app

        cls.temp = tempfile.TemporaryDirectory()
        cls.client = TestClient(create_app(run_demo(cls.temp.name, rows=240)))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_health_and_dashboard(self):
        self.assertEqual(self.client.get("/api/health").json()["postings"], 240)
        body = self.client.get("/api/dashboard").json()
        self.assertTrue(body["run"]["synthetic"])
        self.assertTrue(body["segments"])
        self.assertTrue(body["top_skills"])
        self.assertIn("regression", body["salaries"]["models"])

    def test_cv_text_match_returns_links_and_advice(self):
        body = self.client.post("/api/cv/match", data={"text": CV, "limit": "5"}).json()
        self.assertIn("contabilidad", body["cv_skills"])
        self.assertEqual(len(body["matches"]), 5)
        first = body["matches"][0]
        self.assertTrue(first["url"].startswith("https://"))
        self.assertTrue(0 <= first["match"] <= 100)
        self.assertTrue(body["niches"])
        self.assertIsNotNone(body["salary_estimate"])

    def test_cv_docx_upload(self):
        from docx import Document

        buffer = io.BytesIO()
        document = Document()
        document.add_paragraph(CV)
        document.save(buffer)
        response = self.client.post(
            "/api/cv/match", files={"file": ("cv.docx", buffer.getvalue())}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["matches"])

    def test_rejects_empty_or_unsupported_cv(self):
        self.assertEqual(self.client.post("/api/cv/match", data={"text": "corto"}).status_code,
                         422)
        response = self.client.post("/api/cv/match", files={"file": ("cv.exe", b"MZ" * 40)})
        self.assertEqual(response.status_code, 422)

    def test_segment_postings(self):
        segment = self.client.get("/api/dashboard").json()["segments"][0]["id"]
        body = self.client.get(f"/api/segments/{segment}/postings?limit=3").json()
        self.assertEqual(len(body["postings"]), 3)
        self.assertEqual(self.client.get("/api/segments/999/postings").status_code, 404)


if __name__ == "__main__":
    unittest.main()
