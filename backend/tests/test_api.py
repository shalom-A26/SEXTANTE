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
        from sextante.analytics.demo import run_demo
        from sextante.api.main import create_app

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
        self.assertIn("classification", body["salaries"]["models"])

    def test_dashboard_graph_rankings_communities_and_metrics(self):
        graph = self.client.get("/api/dashboard").json()["graph"]
        node = graph["nodes"][0]
        self.assertIsInstance(node["degree"], int)
        self.assertIsInstance(node["weighted_degree"], float)

        transversal = graph["rankings"]["transversal"]
        self.assertTrue(0 < len(transversal) <= 10)
        self.assertEqual(set(transversal[0]), {"esco_uri", "skill_label", "postings", "degree",
                                               "weighted_degree", "community"})
        degrees = [(r["degree"], r["weighted_degree"]) for r in transversal]
        self.assertEqual(degrees, sorted(degrees, reverse=True))
        bridges = graph["rankings"]["bridges"]
        self.assertLessEqual(len(bridges), 10)
        for row in bridges:
            self.assertEqual(set(row), {"esco_uri", "skill_label", "postings", "degree",
                                        "betweenness", "community"})
        scores = [r["betweenness"] for r in bridges]
        self.assertEqual(scores, sorted(scores, reverse=True))

        communities = graph["communities"]
        self.assertTrue(communities)
        self.assertNotIn(-1, [c["community"] for c in communities])
        sizes = [c["size"] for c in communities]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        self.assertTrue(all(1 <= len(c["top_skills"]) <= 3 for c in communities))

        metrics = graph["metrics"]
        nodes, edges = metrics["skill_nodes"], metrics["skill_edges"]
        self.assertAlmostEqual(metrics["density"], 2 * edges / (nodes * (nodes - 1)))
        self.assertAlmostEqual(metrics["average_degree"], 2 * edges / nodes)
        self.assertTrue(0.0 <= metrics["average_clustering"] <= 1.0)

    def test_graph_without_edges_has_empty_lists_and_null_metrics(self):
        from unittest import mock

        import pandas as pd

        from sextante.api.insights import _graph_communities, _graph_metrics, _graph_rankings

        run = mock.Mock(graph_metrics={}, skill_nodes=pd.DataFrame(), skill_edges=pd.DataFrame())
        metrics = _graph_metrics(run)
        self.assertEqual((metrics["density"], metrics["average_degree"],
                          metrics["average_clustering"]), (None, None, None))
        self.assertEqual(_graph_rankings(run.skill_nodes), {"transversal": [], "bridges": []})
        self.assertEqual(_graph_communities(run.skill_nodes), [])

    def test_cv_text_match_returns_links_and_advice(self):
        body = self.client.post("/api/cv/match", data={"text": CV, "limit": "5"}).json()
        self.assertIn("contabilidad", body["cv_skills"])
        self.assertEqual(len(body["matches"]), 5)
        first = body["matches"][0]
        self.assertTrue(first["url"].startswith("https://"))
        self.assertTrue(0 <= first["match"] <= 100)
        self.assertTrue(body["niches"])
        from sextante.analytics.supervised import BANDS

        self.assertIn(body["salary_estimate"]["salary_band"], BANDS)

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


@unittest.skipIf(TestClient is None, "requires requirements-api.txt")
class ResolveRunDirTests(unittest.TestCase):
    def test_hf_repo_wins_over_local_demo_run(self):
        import os
        from pathlib import Path
        from unittest import mock

        from sextante.analytics.demo import run_demo
        from sextante.api import data

        with tempfile.TemporaryDirectory() as temp:
            run_demo(temp, rows=120)
            env = {"SEXTANTE_RUNS_ROOT": temp, "SEXTANTE_HF_REPO": "org/repo"}
            with mock.patch.dict(os.environ, env), \
                    mock.patch.object(data, "_download_latest",
                                      return_value=Path("hf-run")) as download:
                os.environ.pop("SEXTANTE_RUN_DIR", None)
                self.assertEqual(data.resolve_run_dir(), Path("hf-run"))
            download.assert_called_once_with("org/repo", Path(temp))


@unittest.skipIf(TestClient is None, "requires requirements-api.txt")
class LoadOnceTests(unittest.TestCase):
    def test_concurrent_requests_load_the_run_once(self):
        import threading
        import time
        from unittest import mock

        from sextante.analytics.demo import run_demo
        from sextante.api import main

        calls = []
        real = main.load_run

        def slow_load(path):
            calls.append(path)
            time.sleep(0.3)
            return real(path)

        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(main, "load_run", slow_load):
            client = TestClient(main.create_app(run_demo(temp, rows=120)))
            threads = [threading.Thread(target=client.get, args=("/api/dashboard",))
                       for _ in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(len(calls), 1)


@unittest.skipIf(TestClient is None, "requires requirements-api.txt")
class ServingBundleTests(unittest.TestCase):
    def test_bundle_keeps_corpus_figures_and_matches(self):
        from sextante.analytics.demo import run_demo
        from sextante.api.main import create_app
        from sextante.api.serving import build_bundle

        with tempfile.TemporaryDirectory() as temp:
            run_dir = run_demo(temp, rows=240)
            full = TestClient(create_app(run_dir)).get("/api/dashboard").json()
            client = TestClient(create_app(build_bundle(run_dir, rows=60)))
            self.assertEqual(client.get("/api/health").json()["postings"], 60)
            served = client.get("/api/dashboard").json()
            self.assertEqual(served["overview"], full["overview"])
            # The bundle has no skill edges: the graph block (clustering included)
            # comes from the dashboard precomputed over the full run.
            self.assertEqual(served["graph"], full["graph"])
            self.assertIsNotNone(served["graph"]["metrics"]["average_clustering"])
            body = client.post("/api/cv/match", data={"text": CV, "limit": "5"}).json()
            self.assertIn("contabilidad", body["cv_skills"])
            self.assertTrue(body["matches"])
            sizes = {s["id"]: s["postings"] for s in full["segments"]}
            self.assertEqual(body["current_segment"]["postings"],
                             sizes[body["current_segment"]["segment"]])


if __name__ == "__main__":
    unittest.main()
