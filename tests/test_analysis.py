"""Unit and offline integration coverage for the analytics package."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

import pandas as pd

from pipeline.schema import COLUMNS
from sextante_analysis.artifacts import publish_run, write_manifest
from sextante_analysis.config import AnalysisConfig
from sextante_analysis.corpus import load_corpus
from sextante_analysis.duplicates import find_duplicate_candidates
from sextante_analysis.eda import summarize
from sextante_analysis.features import run_models
from sextante_analysis.run import run_analysis
from sextante_analysis.taxonomy import extract_skills, load_esco_csv


def synthetic_postings(count: int = 18) -> pd.DataFrame:
    roles = [
        ("Analista de datos", "Python SQL análisis de datos y tableros de indicadores."),
        ("Agente de servicio", "Atención al cliente comunicación y resolución de casos."),
        ("Técnico de mantenimiento", "Mantenimiento preventivo seguridad eléctrica y reparación."),
    ]
    rows = []
    for index in range(count):
        title, description = roles[index % len(roles)]
        rows.append({
            "vacancy_id": f"demo-{index:03d}",
            "source": "spe" if index % 2 else "linkedin",
            "url": f"https://example.org/jobs/{index}",
            "title": title,
            "company": "Empresa de demostración",
            "city": "Bogotá",
            "department": "Cundinamarca",
            "published_at": "2026-10-01",
            "description": f"Buscamos profesional para el equipo. {description} " * 4,
            "salary_text": None,
            "salary_min": 2_500_000 + (index % 3) * 200_000,
            "salary_max": 4_000_000 + (index % 3) * 200_000,
            "contract_type": "Término indefinido",
            "work_modality": "Presencial",
            "education_level": "Universitario",
            "experience_text": "Un año de experiencia",
            "captured_at": "2026-10-08 12:00:00",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def write_synthetic_esco(path: Path) -> Path:
    path.write_text(
        "conceptUri,conceptType,preferredLabel,altLabels\n"
        "https://example.org/esco/python,Skill/competence,Python,programación en Python\n"
        "https://example.org/esco/sql,Skill/competence,SQL,consultas SQL\n"
        "https://example.org/esco/customer-service,Skill/competence,atención al cliente,"
        "servicio al cliente\n"
        "https://example.org/esco/occupation,Occupation,Analista de datos,\n",
        encoding="utf-8",
    )
    return path


class AnalysisConfigTests(unittest.TestCase):
    def test_rejects_invalid_parameters(self):
        taxonomy = Path("skills.csv")
        with self.assertRaisesRegex(ValueError, "limit"):
            AnalysisConfig(esco_csv=taxonomy, limit=2)
        with self.assertRaisesRegex(ValueError, "duplicate_threshold"):
            AnalysisConfig(esco_csv=taxonomy, duplicate_threshold=0)
        with self.assertRaisesRegex(ValueError, "topic_count"):
            AnalysisConfig(esco_csv=taxonomy, topic_count=1)
        with self.assertRaisesRegex(ValueError, "cluster_count"):
            AnalysisConfig(esco_csv=taxonomy, cluster_count=1)

    def test_normalizes_paths(self):
        config = AnalysisConfig(esco_csv="skills.csv", output_root="artifacts")
        self.assertEqual(config.esco_csv, Path("skills.csv"))
        self.assertEqual(config.output_root, Path("artifacts"))


class EscoMatcherTests(unittest.TestCase):
    def test_matches_preferred_and_alternative_labels_and_ignores_occupations(self):
        with tempfile.TemporaryDirectory() as temp:
            matcher = load_esco_csv(write_synthetic_esco(Path(temp) / "esco.csv"))
            matches = matcher.match(
                "Experiencia en PROGRAMACIÓN EN Python, SQL y Analista de datos."
            )
        matched_uris = {match["esco_uri"] for match in matches}
        self.assertEqual(matched_uris, {
            "https://example.org/esco/python",
            "https://example.org/esco/sql",
        })
        self.assertEqual(matcher.concepts, 3)

    def test_extracts_one_row_per_concept_without_copying_description(self):
        with tempfile.TemporaryDirectory() as temp:
            matcher = load_esco_csv(write_synthetic_esco(Path(temp) / "esco.csv"))
            mentions = extract_skills(synthetic_postings(3), matcher)
        self.assertIn("vacancy_id", mentions.columns)
        self.assertNotIn("description", mentions.columns)
        self.assertGreater(len(mentions), 0)

    def test_rejects_csv_without_required_headers(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.csv"
            path.write_text("label\nPython\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "conceptUri"):
                load_esco_csv(path)


class DuplicateCandidateTests(unittest.TestCase):
    def test_identical_postings_are_candidates_and_never_removed(self):
        frame = synthetic_postings(3)
        frame.loc[1, "description"] = frame.loc[0, "description"]
        candidates = find_duplicate_candidates(frame, threshold=0.90)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates.iloc[0]["similarity"], 1.0)
        self.assertEqual(len(frame), 3)

    def test_rejects_invalid_similarity_threshold(self):
        with self.assertRaisesRegex(ValueError, "threshold"):
            find_duplicate_candidates(synthetic_postings(3), threshold=1.1)


class EdaTests(unittest.TestCase):
    def test_summarizes_empty_corpus(self):
        self.assertEqual(summarize(pd.DataFrame())["rows"], 0)

    def test_reports_coverage_and_salary_quantiles(self):
        summary = summarize(synthetic_postings(6))
        self.assertEqual(summary["rows"], 6)
        self.assertEqual(summary["description"]["nonempty_rows"], 6)
        self.assertIn("median_cop", summary["salary_min"])


class FeatureModelTests(unittest.TestCase):
    def test_writes_topics_segments_projection_and_tfidf(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = run_models(
                synthetic_postings(), temp, topic_count=2, cluster_count=2, max_features=200
            )
            output = Path(temp)
            expected = {
                "topics.csv", "topic_assignments.parquet", "occupational_segments.parquet",
                "segment_profiles.csv", "segment_projection.parquet", "tfidf_matrix.npz",
                "tfidf_vocabulary.json", "tfidf_idf.npy",
            }
            self.assertTrue(expected.issubset({path.name for path in output.iterdir()}))
            self.assertEqual(summary["cluster_count"], 2)
            self.assertEqual(len(pd.read_parquet(output / "occupational_segments.parquet")), 18)


class CorpusReaderTests(unittest.TestCase):
    def test_loads_one_pinned_revision_and_caps_each_dataset(self):
        hub = ModuleType("huggingface_hub")
        hub.HfApi = lambda: SimpleNamespace(
            repo_info=lambda *args, **kwargs: SimpleNamespace(
                sha="revision-12345678",
                siblings=[
                    SimpleNamespace(rfilename="data/jobspy/day-1.parquet"),
                    SimpleNamespace(rfilename="data/jobspy/day-2.parquet"),
                    SimpleNamespace(rfilename="data/spe/week-1.parquet"),
                    SimpleNamespace(rfilename="README.md"),
                ],
            )
        )
        hub.hf_hub_download = lambda **kwargs: kwargs["filename"]
        rows = synthetic_postings(1)
        with mock.patch.dict(sys.modules, {"huggingface_hub": hub}), mock.patch(
            "pandas.read_parquet", return_value=rows
        ) as read_parquet:
            frame, source = load_corpus(repo="owner/dataset", limit=1)
        self.assertEqual(len(frame), 2)
        self.assertEqual(source["revision"], "revision-12345678")
        self.assertEqual(read_parquet.call_count, 2)


class ArtifactTests(unittest.TestCase):
    def test_manifest_hashes_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            (run_dir / "results.txt").write_text("ready", encoding="utf-8")
            manifest_path = write_manifest(run_dir, {"run_id": "run-1"})
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifacts"]["results.txt"]["bytes"], 5)
        self.assertEqual(len(manifest["artifacts"]["results.txt"]["sha256"]), 64)

    def test_latest_pointer_upload_follows_complete_run_upload(self):
        calls = []
        fake_api = SimpleNamespace(
            upload_folder=lambda **kwargs: calls.append("run"),
            upload_file=lambda **kwargs: calls.append("latest"),
        )
        hub = ModuleType("huggingface_hub")
        hub.HfApi = lambda **kwargs: fake_api
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            sys.modules, {"huggingface_hub": hub}
        ):
            Path(temp, "manifest.json").write_text("{}", encoding="utf-8")
            publish_run(Path(temp), "owner/dataset", "run-1", "token")
        self.assertEqual(calls, ["run", "latest"])

    def test_does_not_move_latest_when_run_upload_fails(self):
        calls = []

        def fail_upload(**kwargs):
            calls.append("run")
            raise RuntimeError("upload failed")

        fake_api = SimpleNamespace(
            upload_folder=fail_upload,
            upload_file=lambda **kwargs: calls.append("latest"),
        )
        hub = ModuleType("huggingface_hub")
        hub.HfApi = lambda **kwargs: fake_api
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            sys.modules, {"huggingface_hub": hub}
        ):
            Path(temp, "manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "upload failed"):
                publish_run(Path(temp), "owner/dataset", "run-1", "token")
        self.assertEqual(calls, ["run"])


class OfflineRunTests(unittest.TestCase):
    def test_creates_a_complete_run_from_synthetic_corpus(self):
        frame = synthetic_postings()
        source = {
            "repo": "synthetic/demo", "revision": "fixture-v1", "files": [],
            "rows": len(frame), "sample_limit_per_dataset": None,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            esco = write_synthetic_esco(root / "esco.csv")
            config = AnalysisConfig(
                esco_csv=esco,
                output_root=root / "runs",
                topic_count=2,
                cluster_count=2,
            )
            with mock.patch("sextante_analysis.run.load_corpus", return_value=(frame, source)):
                run_dir = run_analysis(config)
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("skill_mentions.parquet", manifest["artifacts"])
            self.assertIn("duplicate_candidates.parquet", manifest["artifacts"])
            self.assertTrue((run_dir / "segment_profiles.csv").is_file())
            self.assertEqual(list((root / "runs").iterdir()), [run_dir])


if __name__ == "__main__":
    unittest.main()
