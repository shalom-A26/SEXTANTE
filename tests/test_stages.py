"""Stages 4-6: clustering comparison, supervised models, graph, validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from sextante_analysis.demo import run_demo, synthetic_corpus
from sextante_analysis.graph import segment_graph, segment_skill_profiles, transition_routes
from sextante_analysis.supervised import salary_target
from sextante_analysis.taxonomy import matcher_from_mentions
from sextante_analysis.validation import evaluate_reviews, export_review_samples, wilson_interval


class DemoRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.run_dir = run_demo(cls.temp.name, rows=240)
        cls.manifest = json.loads((cls.run_dir / "manifest.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_writes_every_stage_artifact(self):
        names = {path.name for path in self.run_dir.iterdir()}
        for artifact in ("postings.parquet", "tfidf_vectorizer.joblib", "salary_model.joblib",
                         "salary_estimates.parquet", "supervised_metrics.json",
                         "clustering_comparison.json", "segment_projection_tsne.parquet",
                         "segment_skills.parquet", "skill_graph_nodes.parquet",
                         "skill_graph_edges.parquet", "segment_transitions.parquet"):
            self.assertIn(artifact, names)
        self.assertEqual(self.manifest["source"]["repo"], "synthetic-demo")

    def test_postings_are_row_aligned_with_matrix(self):
        from scipy import sparse

        matrix = sparse.load_npz(self.run_dir / "tfidf_matrix.npz")
        postings = pd.read_parquet(self.run_dir / "postings.parquet")
        self.assertEqual(matrix.shape[0], len(postings))
        self.assertNotIn("description", postings.columns)

    def test_supervised_models_beat_naive_baselines(self):
        supervised = self.manifest["results"]["supervised"]
        self.assertLess(supervised["regression"]["mae_cop"],
                        supervised["regression"]["baseline_median_mae_cop"])
        self.assertGreater(supervised["classification"]["accuracy"],
                           supervised["classification"]["baseline_majority_accuracy"])

    def test_comparison_reports_three_methods(self):
        methods = self.manifest["results"]["clustering_comparison"]
        self.assertEqual(set(methods), {"kmeans", "hierarchical_ward", "dbscan"})

    def test_graph_has_communities_and_routes(self):
        graph = self.manifest["results"]["graph"]
        self.assertGreater(graph["skill_edges"], 0)
        self.assertGreater(graph["skill_communities"], 0)
        self.assertGreater(graph["transition_routes"], 0)

    def test_review_export_and_evaluation(self):
        files = export_review_samples(self.run_dir, Path(self.temp.name) / "review")
        self.assertGreaterEqual(len(files), 2)  # demo has no duplicate pairs
        sample = pd.read_csv(files[0], dtype=str)
        sample.loc[:9, "is_correct"] = ["sí"] * 8 + ["no"] * 2
        sample.to_csv(files[0], index=False)
        report = evaluate_reviews(Path(self.temp.name) / "review")
        first = report[files[0].stem.removeprefix("review_")]
        self.assertEqual(first["reviewed"], 10)
        self.assertAlmostEqual(first["precision"], 0.8)


class StageUnitTests(unittest.TestCase):
    def test_salary_target_drops_implausible_values(self):
        frame = pd.DataFrame({"salary_min": [2e6, 10, None], "salary_max": [4e6, 20, None]})
        target = salary_target(frame)
        self.assertEqual(target.iloc[0], 3e6)
        self.assertTrue(target.iloc[1:].isna().all())

    def test_segment_profiles_and_routes(self):
        mentions = pd.DataFrame({
            "vacancy_id": ["a", "b", "c", "c"], "source": ["spe"] * 4,
            "esco_uri": ["u1", "u1", "u1", "u2"], "skill_label": ["x", "x", "x", "y"],
        })
        segments = pd.DataFrame({"vacancy_id": ["a", "b", "c"], "source": ["spe"] * 3,
                                 "cluster_id": [0, 1, 2]})
        profiles = segment_skill_profiles(mentions, segments)
        self.assertEqual(float(profiles[profiles["cluster_id"] == 0]["share"].iloc[0]), 1.0)
        routes = transition_routes(segment_graph(profiles, [0, 1, 2]))
        self.assertTrue(((routes["from_segment"] == 0) & (routes["to_segment"] == 2)).any())

    def test_matcher_from_mentions_reads_seen_aliases(self):
        mentions = pd.DataFrame({"esco_uri": ["u1"], "skill_label": ["SQL"],
                                 "matched_text": ["consultas sql"]})
        found = matcher_from_mentions(mentions).match("Experto en consultas SQL y Python")
        self.assertEqual([item["esco_uri"] for item in found], ["u1"])

    def test_curated_synonyms_resolve_to_loaded_esco_labels(self):
        from sextante_analysis.taxonomy import load_esco_csv

        with tempfile.TemporaryDirectory() as temp:
            esco = Path(temp) / "skills.csv"
            esco.write_text(
                "conceptUri,conceptType,preferredLabel,altLabels\n"
                "u:sheet,KnowledgeSkillCompetence,utilizar software de hojas de cálculo,\n"
                "u:service,KnowledgeSkillCompetence,servicio al cliente,\n",
                encoding="utf-8",
            )
            matcher = load_esco_csv(esco)
            found = {m["esco_uri"] for m in matcher.match("Excel avanzado y atención al cliente")}
            self.assertEqual(found, {"u:sheet", "u:service"})
            # Synonyms whose target label is absent are skipped, not invented.
            self.assertGreater(matcher.synonyms_added, 0)
            plain = load_esco_csv(esco, synonyms=None)
            self.assertEqual(plain.match("Excel avanzado"), [])

    def test_tfidf_sample_fit_transforms_every_text(self):
        from sextante_analysis.features import fit_tfidf

        roles = ["analista python sql", "contador nomina excel", "vendedor clientes crm"]
        texts = [f"{roles[i % 3]} {['bogota', 'cali'][i % 2]}" for i in range(40)]
        full_vectorizer, full = fit_tfidf(texts, max_features=100)
        sample_vectorizer, sampled = fit_tfidf(texts, max_features=100, fit_sample=10)
        self.assertEqual(sampled.shape[0], 40)
        self.assertIn("python", sample_vectorizer.vocabulary_)
        self.assertEqual(full.shape[0], sampled.shape[0])

    def test_repairs_double_encoded_text_in_place(self):
        from sextante_analysis.cleaning import repair_frame, repair_mojibake

        broken = "Técnico en gestión".encode("utf-8").decode("cp1252")
        self.assertEqual(repair_mojibake(broken), "Técnico en gestión")
        self.assertEqual(repair_mojibake("Técnico ya correcto"), "Técnico ya correcto")
        frame = pd.DataFrame({"title": [broken, "Auxiliar"], "description": ["ok", None]})
        self.assertEqual(repair_frame(frame), 1)
        self.assertEqual(frame.loc[0, "title"], "Técnico en gestión")

    def test_blocklist_drops_ambiguous_aliases(self):
        from sextante_analysis.taxonomy import load_esco_csv

        with tempfile.TemporaryDirectory() as temp:
            esco = Path(temp) / "skills.csv"
            esco.write_text(
                "conceptUri,conceptType,preferredLabel,altLabels\n"
                "u:log,KnowledgeSkillCompetence,logística,transporte\n"
                "u:fin,KnowledgeSkillCompetence,finés,fines\n",
                encoding="utf-8",
            )
            text = "Auxilio de transporte para fines de contratación en logística"
            found = {m["esco_uri"] for m in load_esco_csv(esco).match(text)}
            self.assertEqual(found, {"u:log"})
            loose = load_esco_csv(esco, blocklist=None).match(text)
            self.assertEqual({m["esco_uri"] for m in loose}, {"u:log", "u:fin"})

    def test_clean_title_strips_noise(self):
        from sextante_api.insights import clean_title

        self.assertEqual(
            clean_title("Asesor call center con o sin experiencia"), "Asesor call center"
        )
        self.assertEqual(clean_title("AUXILIAR CONTABLE SENIOR - Bogotá"), "Auxiliar contable")

    def test_wilson_interval_bounds(self):
        low, high = wilson_interval(8, 10)
        self.assertTrue(0 < low < 0.8 < high < 1)

    def test_synthetic_corpus_matches_schema(self):
        from pipeline.schema import COLUMNS

        self.assertEqual(list(synthetic_corpus(16).columns), COLUMNS)


if __name__ == "__main__":
    unittest.main()
