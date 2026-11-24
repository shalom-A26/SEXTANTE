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
        cls.run_dir = run_demo(cls.temp.name, rows=240)
        cls.client = TestClient(create_app(cls.run_dir))

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

    def test_dashboard_skill_insights_shape_order_and_bounds(self):
        from sextante.api import skill_cooccurrence as sc
        from sextante.api import skill_insights as si
        from sextante.api.data import load_run

        body = self.client.get("/api/dashboard").json()
        insights = body["skill_insights"]
        self.assertEqual(set(insights), {"table", "core", "pivots", "pairs", "salary", "niche"})

        table = insights["table"]
        self.assertTrue(0 < len(table) <= si.TABLE_SIZE)
        self.assertEqual(set(table[0]), {
            "esco_uri", "skill_label", "postings", "share", "degree", "weighted_degree",
            "betweenness", "pagerank", "community", "top_segment", "top_segment_share", "kind"})
        postings = [row["postings"] for row in table]
        self.assertEqual(postings, sorted(postings, reverse=True))
        segment_ids = {s["id"] for s in body["segments"]}
        for row in table:
            self.assertIn(row["kind"], {"transversal", "especializada", "intermedia"})
            self.assertIn(row["top_segment"], segment_ids)
            self.assertTrue(0 < row["top_segment_share"] <= 1)
            if row["kind"] == "especializada":
                self.assertGreaterEqual(row["top_segment_share"],
                                        si.SPECIALIZED_MIN_SEGMENT_SHARE)

        core = insights["core"]
        self.assertTrue(0 < len(core) <= si.CORE_SIZE)
        self.assertEqual(set(core[0]), {"esco_uri", "skill_label", "postings", "pagerank",
                                        "degree"})
        ranks = [row["pagerank"] for row in core]
        self.assertEqual(ranks, sorted(ranks, reverse=True))

        pivots = insights["pivots"]
        self.assertTrue(pivots)
        links = {(p["from_segment"], p["to_segment"]) for p in pivots}
        self.assertEqual(links, {(b, a) for a, b in links})  # both directions
        for pivot in pivots:
            self.assertEqual(set(pivot), {"from_segment", "to_segment", "similarity", "shared",
                                          "missing"})
            self.assertLessEqual(len(pivot["shared"]), si.PIVOT_LIST_SIZE)
            self.assertLessEqual(len(pivot["missing"]), si.PIVOT_LIST_SIZE)
            self.assertFalse(set(pivot["shared"]) & set(pivot["missing"]))

        self.assertLessEqual(len(insights["pairs"]), sc.PAIRS_SIZE)
        self.assertTrue(all(p["together"] >= sc.PAIR_MIN_TOGETHER for p in insights["pairs"]))

        salary = insights["salary"]
        self.assertEqual(set(salary), {"overall_high_share", "top", "bottom", "boosts"})
        # Same "$2M o más" definition as the salary panels (bands from $2M up), over the
        # deduplicated postings the skill figures use.
        self.assertEqual(si.BAND_EDGES[si.HIGH_SALARY_BAND - 1], si.HIGH_SALARY_FLOOR)
        run = load_run(self.run_dir)
        incidence = sc.skill_incidence(run)
        bands = si.salary_band(run.postings.iloc[incidence.unique]).dropna().astype(int)
        self.assertAlmostEqual(salary["overall_high_share"],
                               float((bands >= si.HIGH_SALARY_BAND).mean()))
        self.assertLessEqual(len(salary["top"]), si.SALARY_LIST_SIZE)
        self.assertLessEqual(len(salary["bottom"]), si.SALARY_LIST_SIZE)
        self.assertLessEqual(len(salary["boosts"]), si.BOOST_SIZE)
        self.assertLessEqual(len(insights["niche"]), si.NICHE_SIZE)

    def test_skill_insights_with_relaxed_thresholds(self):
        import math
        from unittest import mock

        from sextante.api import skill_cooccurrence as sc
        from sextante.api import skill_insights as si
        from sextante.api.data import load_run

        run = load_run(self.run_dir)
        incidence = sc.skill_incidence(run)
        column = {label: index for index, label in enumerate(incidence.labels)}
        relaxed = {"SALARY_MIN_POSTINGS": 5, "BOOST_ANCHOR_MIN_POSTINGS": 5,
                   "BOOST_MIN_COMBO": 3, "BOOST_MIN_GAIN": 0.0,
                   "NICHE_MIN_POSTINGS": 1, "NICHE_MIN_SEGMENT_SHARE": 0.3}
        with mock.patch.multiple(si, **relaxed), \
                mock.patch.multiple(sc, PAIR_MIN_TOGETHER=2, PAIR_MIN_MARGINAL=1):
            insights = si.skill_insights(run, incidence)
            pairs = insights["pairs"]
            self.assertTrue(pairs)
            npmi = [incidence.npmi[column[p["a"]], column[p["b"]]] for p in pairs]
            self.assertEqual(npmi, sorted(npmi, reverse=True))  # ranked by NPMI
            for pair in pairs:
                self.assertEqual(set(pair), {"a", "b", "together", "lift", "pmi"})
                self.assertAlmostEqual(pair["pmi"], math.log2(pair["lift"]))

            salary = insights["salary"]
            self.assertTrue(salary["top"])
            top = [row["high_share"] for row in salary["top"]]
            bottom = [row["high_share"] for row in salary["bottom"]]
            self.assertEqual(top, sorted(top, reverse=True))
            self.assertEqual(bottom, sorted(bottom))
            self.assertFalse({r["skill_label"] for r in salary["top"]}
                             & {r["skill_label"] for r in salary["bottom"]})
            for row in salary["top"] + salary["bottom"]:
                self.assertGreaterEqual(row["postings_with_salary"], 5)
                self.assertAlmostEqual(row["lift"],
                                       row["high_share"] / salary["overall_high_share"])
            for boost in salary["boosts"]:
                self.assertNotEqual(boost["anchor"], boost["complement"])
                self.assertLess(boost["anchor_high_share"], salary["overall_high_share"])
                self.assertGreaterEqual(boost["combo_high_share"], boost["anchor_high_share"])
                self.assertLessEqual(boost["combo_postings"], boost["anchor_postings"])
            for niche in insights["niche"]:
                self.assertEqual(set(niche), {"skill_label", "postings", "degree",
                                              "top_segment", "top_segment_share", "partner",
                                              "partner_lift"})
                self.assertGreaterEqual(niche["top_segment_share"], 0.3)

    def test_skill_kind_rule(self):
        from sextante.api.skill_insights import skill_kind

        # (top-segment share, breadth = segments with lift >= 1, number of segments)
        self.assertEqual(skill_kind(0.3, 4, 10), "transversal")   # 4 >= 0.40 * 10
        self.assertEqual(skill_kind(0.59, 9, 10), "transversal")
        self.assertEqual(skill_kind(0.7, 9, 10), "especializada")
        self.assertEqual(skill_kind(0.3, 3, 10), "intermedia")
        # spread out but above its corpus share in few segments (e.g. payroll): not transversal
        self.assertEqual(skill_kind(0.35, 2, 16), "intermedia")
        self.assertEqual(skill_kind(0.5, 0, 0), "intermedia")
        self.assertEqual(skill_kind(None, 10, 10), "intermedia")

    def test_dashboard_community_validation(self):
        from unittest import mock

        from sextante.api import skill_cooccurrence as sc
        from sextante.api import skill_insights as si
        from sextante.api.data import load_run

        body = self.client.get("/api/dashboard").json()
        validation = body["community_validation"]
        self.assertEqual(set(validation), {"pmi_edges", "pmi_communities", "pmi_modularity",
                                           "communities", "segments"})
        if not validation["pmi_edges"]:  # the demo is smaller than the production support
            self.assertEqual((validation["communities"], validation["pmi_modularity"]),
                             ([], None))
        run = load_run(self.run_dir)
        # The demo's vocabulary is tiny, so nearly every skill is above the generic share.
        with mock.patch.multiple(sc, PMI_MIN_TOGETHER=2, GENERIC_MIN_SHARE=1.01):
            validation = si.community_validation(run, sc.skill_incidence(run))
        self.assertGreater(validation["pmi_edges"], 0)
        communities = validation["communities"]
        self.assertEqual(len(communities), validation["pmi_communities"])
        sizes = [c["size"] for c in communities]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        self.assertTrue(all(1 <= len(c["top_skills"]) <= 3 for c in communities))
        self.assertTrue(-0.5 <= validation["pmi_modularity"] <= 1.0)
        ids = {c["community"] for c in communities}
        self.assertEqual([s["segment"] for s in validation["segments"]],
                         [s["id"] for s in body["segments"]])
        for segment in validation["segments"]:
            if segment["dominant_community"] is None:
                self.assertEqual(segment["communities_used"], 0)
                continue
            self.assertIn(segment["dominant_community"], ids)
            self.assertTrue(0 < segment["dominant_share"] <= 1)
            self.assertGreaterEqual(segment["communities_used"], 1)

    def test_dashboard_topics_are_profiled(self):
        body = self.client.get("/api/dashboard").json()
        topics = body["topics"]
        self.assertTrue(topics)
        self.assertEqual(sum(t["postings"] for t in topics), body["overview"]["postings"])
        self.assertAlmostEqual(sum(t["share"] for t in topics), 1.0)
        for topic in topics:
            self.assertIn("terms", topic)
            self.assertLessEqual(len(topic["top_titles"]), 3)
            self.assertLessEqual(len(topic["top_segments"]), 2)
            self.assertLessEqual(len(topic["top_skills"]), 4)
            shares = [s["share"] for s in topic["top_segments"]]
            self.assertEqual(shares, sorted(shares, reverse=True))

    def test_skill_insights_empty_run(self):
        from pathlib import Path
        from types import SimpleNamespace

        import pandas as pd

        from sextante.api import skill_cooccurrence as sc
        from sextante.api import skill_insights as si

        run = SimpleNamespace(
            postings=pd.DataFrame(columns=["vacancy_id", "source", "title", "cluster_id",
                                           "salary_min", "salary_max"]),
            posting_skills=[], segment_ids=[], skill_nodes=pd.DataFrame(),
            segment_skills=pd.DataFrame(), transitions=pd.DataFrame(),
            run_dir=Path(self.temp.name) / "missing-run")
        incidence = sc.skill_incidence(run)
        self.assertIsNone(incidence)
        self.assertEqual(si.skill_insights(run, incidence), {
            "table": [], "core": [], "pivots": [], "pairs": [],
            "salary": {"overall_high_share": None, "top": [], "bottom": [], "boosts": []},
            "niche": []})
        self.assertEqual(si.community_validation(run, incidence), {
            "pmi_edges": 0, "pmi_communities": 0, "pmi_modularity": None,
            "communities": [], "segments": []})
        self.assertEqual(si.topic_profiles(run, [], incidence, pd.Series(dtype=str)), [])
        topics = [{"topic_id": 0, "terms": "a | b"}]  # no assignments file: unchanged
        self.assertEqual(si.topic_profiles(run, topics, incidence, pd.Series(dtype=str)), topics)

    def test_topic_titles_must_read_as_job_titles(self):
        from sextante.api.skill_insights import topic_title_ok

        for title in ("Auxiliar contable", "Técnico electricista", "Firma contrato al día 3"):
            self.assertTrue(topic_title_ok(title), title)  # the last one needs semantics
        for title in ("$hno codigo vacante$obrero", "{cargo}", "AB", "", "  ",
                      "12345-678 / 9", "A1 B2 C3 D4", "Ing. 2024-11-24"):
            self.assertFalse(topic_title_ok(title), title)

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
def _toy_run(groups, labels, matcher=None):
    """Tiny run from (copies, skill URIs, segment) groups; every posting has its own title."""
    from collections import Counter
    from types import SimpleNamespace

    import pandas as pd

    rows, posting_skills = [], []
    for copies, skills, segment in groups:
        for _ in range(copies):
            rows.append({"vacancy_id": f"toy-{len(rows)}", "source": "toy",
                         "title": f"Vacante {len(rows)}", "company": "", "cluster_id": segment,
                         "salary_min": None, "salary_max": None})
            posting_skills.append(frozenset(skills))
    counts = Counter(uri for skills in posting_skills for uri in skills)
    nodes = pd.DataFrame({
        "esco_uri": list(labels), "skill_label": list(labels.values()),
        "postings": [counts[uri] for uri in labels], "degree": 1, "weighted_degree": 1.0,
        "pagerank": [counts[uri] / 100 for uri in labels], "betweenness": 0.0, "community": 0})
    return SimpleNamespace(
        postings=pd.DataFrame(rows), posting_skills=posting_skills, skill_nodes=nodes,
        segment_ids=sorted({segment for *_, segment in groups}), transitions=pd.DataFrame(),
        segment_skills=pd.DataFrame(), matcher=matcher)


@unittest.skipIf(TestClient is None, "requires requirements-api.txt")
class SkillCooccurrenceTests(unittest.TestCase):
    def test_skills_with_the_same_normalized_label_are_merged(self):
        from sextante.api import skill_cooccurrence as sc

        labels = {"u1": "Gestionar contratos", "u2": "gestionar  contratos",
                  "u3": "Derecho mercantil"}
        run = _toy_run([(1, {"u1"}, 0), (1, {"u2"}, 0), (1, {"u1", "u2", "u3"}, 0)], labels)
        incidence = sc.skill_incidence(run)
        self.assertEqual(len(incidence.uris), 2)
        merged = incidence.column_of["u1"]
        self.assertEqual(incidence.column_of["u2"], merged)
        self.assertEqual(incidence.uris[merged], "u1")
        self.assertEqual(incidence.counts[merged], 3)  # a posting with both counts once
        self.assertEqual(incidence.unique_counts[merged], 3)

    def test_near_identical_postings_are_collapsed(self):
        import pandas as pd
        from scipy import sparse

        from sextante.api import skill_cooccurrence as sc

        postings = pd.DataFrame({
            "title": ["Analista", "analista ", "Contador", "Vendedor", "Vendedor", "Vendedor"],
            "company": ["A", "B", "A", "C", "D", "C"]})
        sets = [[0, 1, 2], [0, 1, 2], [0, 1, 2], [3, 4], [3, 4], [3, 4]]
        rows = [row for row, skills in enumerate(sets) for _ in skills]
        cols = [col for skills in sets for col in skills]
        matrix = sparse.csr_matrix(([1.0] * len(rows), (rows, cols)), shape=(6, 5))
        # same title + skills (row 1); same company + >= 3 skills (row 2); exact copy (row 5);
        # row 4 has another company and too few skills to be collapsed by skills alone.
        self.assertEqual(sc.unique_postings(postings, matrix).tolist(), [0, 3, 4])

        labels = {"a": "Python", "b": "SQL", "c": "Git", "d": "Excel"}
        groups = [(1, {"a", "b", "c"}, 0), (1, {"d"}, 0)]
        run = _toy_run(groups, labels)
        run.postings = pd.concat([run.postings] + [run.postings.iloc[[0]]] * 4,
                                 ignore_index=True)  # one template reposted four times
        run.posting_skills = run.posting_skills + [run.posting_skills[0]] * 4
        incidence = sc.skill_incidence(run)
        a, b = incidence.column_of["a"], incidence.column_of["b"]
        self.assertEqual(incidence.counts[a], 5)  # demand as published
        self.assertEqual(incidence.together[a, b], 1)  # associations on deduped postings
        self.assertEqual(incidence.unique_total, 2)

    def test_large_identical_skill_sets_collapse_as_templates(self):
        import pandas as pd
        from scipy import sparse

        from sextante.api import skill_cooccurrence as sc

        # Every posting has its own title and company.
        postings = pd.DataFrame({"title": [f"Cargo {i}" for i in range(7)],
                                 "company": [f"Empresa {i}" for i in range(7)]})
        sets = [[0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2], [0, 1, 2],
                [0, 1, 2, 3, 4], [0, 1, 2, 4]]
        rows = [row for row, skills in enumerate(sets) for _ in skills]
        cols = [col for skills in sets for col in skills]
        matrix = sparse.csr_matrix(([1.0] * len(rows), (rows, cols)), shape=(7, 5))
        matrix.sort_indices()
        self.assertEqual(sc.TEMPLATE_MIN_SKILLS, 4)
        # The 4-skill set reposted under other titles and companies is one template (rows 1,
        # 2); the 3-skill copy (row 4) still needs the same title or company to collapse.
        self.assertEqual(sc.unique_postings(postings, matrix).tolist(), [0, 3, 4, 5, 6])

    def test_pairs_rank_by_npmi_and_skip_synonyms(self):
        from unittest import mock

        import pandas as pd

        from sextante.analytics.taxonomy import matcher_from_mentions
        from sextante.api import skill_cooccurrence as sc

        labels = {"d1": "dermatología", "d2": "dermatología y venereología", "c1": "CSS",
                  "c2": "lenguajes de la hoja de estilo", "p": "Python", "s": "SQL",
                  "v": "ventas", "n": "negociación", "x": "Docker", "y": "Linux", "e": "Excel"}
        matcher = matcher_from_mentions(pd.DataFrame({
            "esco_uri": ["c1", "c2"], "skill_label": [labels["c1"], labels["c2"]],
            "matched_text": ["css", "css"]}))  # one phrase matched both concepts
        run = _toy_run([
            (5, {"d1", "d2"}, 0), (5, {"c1", "c2"}, 0), (4, {"p", "s"}, 0), (2, {"p"}, 0),
            (2, {"s"}, 0), (3, {"v", "n"}, 0), (3, {"v"}, 0), (3, {"n"}, 0),
            (2, {"x", "y"}, 0), (4, {"y"}, 0), (10, {"e"}, 0)], labels, matcher)
        incidence = sc.skill_incidence(run)
        with mock.patch.multiple(sc, PAIR_MIN_TOGETHER=1, PAIR_MIN_MARGINAL=1):
            pairs = sc.pairs(incidence)
        # Docker + Linux has the higher PMI, Python + SQL the higher NPMI.
        self.assertGreater(pairs[1]["pmi"], pairs[0]["pmi"])
        self.assertEqual([{p["a"], p["b"]} for p in pairs],
                         [{"Python", "SQL"}, {"Docker", "Linux"}, {"ventas", "negociación"}])
        with mock.patch.multiple(sc, PAIR_MIN_TOGETHER=1, PAIR_MIN_MARGINAL=7):
            self.assertEqual(sc.pairs(incidence), [])  # marginal support

    def test_sparse_pmi_graph_finds_skill_families(self):
        from unittest import mock

        from sextante.api import skill_cooccurrence as sc
        from sextante.api import skill_insights as si

        labels = {uri: uri.upper() for uri in ("a1", "a2", "a3", "b1", "b2", "b3", "solo")}
        run = _toy_run([(10, {"a1", "a2", "a3"}, 0), (10, {"b1", "b2", "b3"}, 1),
                        (2, {"a1", "b1"}, 0), (3, {"solo"}, 1)], labels)
        incidence = sc.skill_incidence(run)
        # 25 postings: a1 and b1 are in 12 (0.48), a2, a3, b2, b3 in 10 (0.40).
        with mock.patch.multiple(sc, PMI_MIN_TOGETHER=2, PMI_TOP_K=2, GENERIC_MIN_SHARE=0.5):
            validation = si.community_validation(run, incidence)
        self.assertEqual(validation["pmi_edges"], 6)  # the weak a1–b1 link is dropped
        self.assertEqual([set(c["top_skills"]) for c in validation["communities"]],
                         [{"A1", "A2", "A3"}, {"B1", "B2", "B3"}])  # "solo" has no edge
        self.assertAlmostEqual(validation["pmi_modularity"], 0.5)
        self.assertEqual([s["dominant_community"] for s in validation["segments"]], [0, 1])
        with mock.patch.multiple(sc, PMI_MIN_TOGETHER=2, PMI_TOP_K=1, GENERIC_MIN_SHARE=0.5):
            self.assertEqual(sc.pmi_graph(incidence).number_of_edges(), 4)  # top-k prunes
        # Generic skills (here a1 and b1, share >= 0.45) are removed before Louvain.
        with mock.patch.multiple(sc, PMI_MIN_TOGETHER=2, PMI_TOP_K=2, GENERIC_MIN_SHARE=0.45):
            self.assertEqual(sorted(sc.generic_columns(incidence).tolist()),
                             sorted([incidence.column_of["a1"], incidence.column_of["b1"]]))
            graph = sc.pmi_graph(incidence)
            validation = si.community_validation(run, incidence)
        self.assertEqual(set(graph.nodes), {"a2", "a3", "b2", "b3"})
        self.assertEqual(validation["pmi_edges"], 2)
        self.assertEqual([set(c["top_skills"]) for c in validation["communities"]],
                         [{"A2", "A3"}, {"B2", "B3"}])

    def test_pivots_share_and_gap_rules_skip_generic_skills(self):
        from unittest import mock

        import pandas as pd

        from sextante.api import skill_cooccurrence as sc
        from sextante.api import skill_insights as si

        labels = {"x": "Excel", "c": "contabilidad", "n": "nómina"}
        run = _toy_run([(6, {"x", "c"}, 0), (4, {"x"}, 0), (4, {"x", "c"}, 1),
                        (5, {"x", "n"}, 1), (1, {"x"}, 1), (20, set(), 2)], labels)
        transitions = pd.DataFrame({"from_segment": [0, 1], "to_segment": [1, 0],
                                    "steps": [1, 1], "direct_similarity": [0.5, 0.5]})
        incidence = sc.skill_incidence(run)
        # Shares (segments 0, 1; corpus of 40): Excel 1.0, 1.0 (0.5); contabilidad 0.6, 0.4
        # (0.25); nómina 0.0, 0.5 (0.125). Shared needs >= 0.05 in both (ranked by the smaller
        # share); missing needs lift >= 1.5 in the target and origin share <= half of it.
        plain = si.pivots(incidence, transitions, set())
        self.assertEqual([(p["from_segment"], p["shared"], p["missing"]) for p in plain],
                         [(0, ["Excel", "contabilidad"], ["nómina"]),
                          (1, ["Excel", "contabilidad"], [])])
        with mock.patch.multiple(sc, GENERIC_MIN_SHARE=0.3):
            generic = si.generic_skills(incidence)
        self.assertEqual(generic, {incidence.column_of["x"]})  # in half of all postings
        pivots = si.pivots(incidence, transitions, generic)
        self.assertEqual([(p["from_segment"], p["shared"], p["missing"]) for p in pivots],
                         [(0, ["contabilidad"], ["nómina"]), (1, ["contabilidad"], [])])
        # A skill clearly weaker in the origin is a gap, never also shared.
        with mock.patch.multiple(si, PIVOT_MISSING_MAX_RATIO=0.8):
            first = si.pivots(incidence, transitions, generic)[1]
        self.assertEqual((first["shared"], first["missing"]), ([], ["contabilidad"]))

        # Breadth kind rule: Excel is above its corpus share in 2 of 3 segments.
        nodes = si._merged_nodes(run.skill_nodes, incidence)
        kinds = si._kinds(nodes, si._focus(incidence), incidence)
        self.assertEqual({incidence.labels[column]: kind for column, kind in kinds.items()},
                         {"Excel": "transversal", "contabilidad": "especializada",
                          "nómina": "especializada"})

    def test_niche_partner_uses_its_own_support_floor(self):
        from unittest import mock

        from sextante.api import skill_cooccurrence as sc
        from sextante.api import skill_insights as si

        labels = {"neo": "neonatología", "ped": "pediatría", "aro": "aromaterapia",
                  "v": "ventas"}
        run = _toy_run([(30, {"neo", "ped"}, 0), (60, {"ped"}, 0), (25, {"neo", "aro"}, 0),
                        (100, {"v"}, 1)], labels)
        incidence = sc.skill_incidence(run)
        nodes = si._merged_nodes(run.skill_nodes, incidence)
        focus = si._focus(incidence)

        def partner(**floors):
            with mock.patch.multiple(si, NICHE_MIN_POSTINGS=1, **floors):
                rows = si._niche(nodes, incidence, focus)
            return next(r for r in rows if r["skill_label"] == "neonatología")

        # pediatría: 30 together, 90 postings. aromaterapia has the higher NPMI but only
        # 25 postings, below the partner floor of 50.
        row = partner()
        self.assertEqual(row["partner"], "pediatría")
        self.assertAlmostEqual(row["partner_lift"], 30 * 215 / (55 * 90))
        self.assertEqual(partner(NICHE_PARTNER_MIN_MARGINAL=20)["partner"], "aromaterapia")
        self.assertIsNone(partner(NICHE_PARTNER_MIN_TOGETHER=sc.PAIR_MIN_TOGETHER,
                                  NICHE_PARTNER_MIN_MARGINAL=sc.PAIR_MIN_MARGINAL)["partner"])


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
