import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline import env, store
from pipeline.schema import COLUMNS, normalize, validate


def _row(vacancy_id: str, url: str, captured_at: str, **extra) -> dict:
    row = {
        "vacancy_id": vacancy_id,
        "source": "spe",
        "url": url,
        "title": f"Job {vacancy_id}",
        "company": "Company SA",
        "city": "Bogotá",
        "department": "Cundinamarca",
        "published_at": "2026-09-01",
        "description": "Experience required.",
        "salary_text": "$2.000.000 - $3.000.000",
        "salary_min": 2_000_000,
        "salary_max": 3_000_000,
        "contract_type": "Término indefinido",
        "work_modality": None,
        "education_level": "Universitario",
        "experience_text": "24 meses",
        "captured_at": captured_at,
    }
    row.update(extra)
    return row


class AppendTest(unittest.TestCase):
    def _tmp_store(self) -> Path:
        return Path(tempfile.mkdtemp()) / "spe.parquet"

    def test_appends_only_new_rows(self):
        path = self._tmp_store()
        first = store.append("spe", pd.DataFrame([_row("a", "https://x.co/a", "2026-10-01 06:00:00")]), path=path)
        second = store.append("spe", pd.DataFrame([_row("b", "https://x.co/b", "2026-10-01 07:00:00")]), path=path)
        self.assertEqual(first, 1)
        self.assertEqual(second, 1)
        self.assertEqual(store.count_rows(path), 2)

    def test_reobserved_row_is_not_counted_or_rewritten(self):
        """keep='first': text and captured_at freeze on first observation."""
        path = self._tmp_store()
        store.append("spe", pd.DataFrame([_row("a", "https://x.co/a", "2026-10-01 06:00:00")]), path=path)
        edited = _row("a", "https://x.co/a", "2026-10-05 06:00:00", description="EDITED LATER")
        added = store.append("spe", pd.DataFrame([edited]), path=path)

        df = pd.read_parquet(path)
        self.assertEqual(added, 0)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["description"], "Experience required.")
        self.assertEqual(df.iloc[0]["captured_at"], "2026-10-01 06:00:00")

    def test_dedupe_key_is_url_for_jobspy_and_id_for_spe(self):
        """Two SPE rows sharing a URL are distinct; two jobspy rows are not."""
        spe_path = self._tmp_store()
        store.append("spe", pd.DataFrame([
            _row("spe-1", "https://provedor.co/oferta", "2026-10-01 06:00:00"),
            _row("spe-2", "https://provedor.co/oferta", "2026-10-01 06:00:00"),
        ]), path=spe_path)
        self.assertEqual(store.count_rows(spe_path), 2)

        jobspy_path = Path(tempfile.mkdtemp()) / "jobspy.parquet"
        store.append("jobspy", pd.DataFrame([
            _row("x1", "https://linkedin.com/jobs/view/1", "2026-10-01 06:00:00", source="linkedin"),
            _row("x2", "https://linkedin.com/jobs/view/1", "2026-10-01 06:00:00", source="linkedin"),
        ]), path=jobspy_path)
        self.assertEqual(store.count_rows(jobspy_path), 1)

    def test_batch_internal_duplicates_collapse(self):
        path = self._tmp_store()
        added = store.append("spe", pd.DataFrame([
            _row("a", "https://x.co/a", "2026-10-01 06:00:00"),
            _row("a", "https://x.co/a", "2026-10-01 07:00:00"),
        ]), path=path)
        self.assertEqual(added, 1)

    def test_empty_incoming_is_a_noop(self):
        path = self._tmp_store()
        self.assertEqual(store.append("spe", pd.DataFrame(), path=path), 0)
        self.assertFalse(path.exists())


class SchemaTest(unittest.TestCase):
    def test_normalize_adds_missing_and_drops_extra(self):
        df = normalize(pd.DataFrame([{"vacancy_id": "a", "almacen": "spe", "extra": 1}]))
        self.assertEqual(list(df.columns), COLUMNS)
        self.assertNotIn("almacen", df.columns)

    def test_validate_reports_missing(self):
        self.assertEqual(list(validate(pd.DataFrame())), COLUMNS)
        self.assertEqual(list(validate(pd.DataFrame(columns=COLUMNS))), [])


class CountRowsTest(unittest.TestCase):
    """count_rows reads the parquet footer, never pd.read_parquet.

    pd.read_parquet spins up Arrow's thread-pooled scanner; if its reader
    survives until interpreter shutdown the process aborts with exit 134
    (Arrow #34314) — it killed a production capture on 2026-10-05.
    """

    def test_counts_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.parquet"
            pd.DataFrame({"vacancy_id": ["a", "b", "c"]}).to_parquet(path, index=False)
            self.assertEqual(store.count_rows(path), 3)

    def test_matches_pandas_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.parquet"
            pd.DataFrame({"vacancy_id": ["a", "b"]}).to_parquet(path, index=False)
            self.assertEqual(store.count_rows(path), len(pd.read_parquet(path)))

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            store.count_rows(Path("/nonexistent/x.parquet"))


class CoerceTypesTest(unittest.TestCase):
    def test_salary_become_floats_and_nulls_become_none(self):
        df = pd.DataFrame([
            {"vacancy_id": "a", "salary_min": "2000000", "salary_max": None, "title": "x"},
        ])
        out = env.coerce_types(df)
        self.assertEqual(out["salary_min"].dtype, "float64")
        self.assertTrue(pd.isna(out["salary_max"]).all())
        self.assertIsNone(out.iloc[0]["captured_at"])

    def test_types_do_not_depend_on_input_order(self):
        rows = [
            {"vacancy_id": "b", "title": "2", "captured_at": "2026-10-01 06:00:00"},
            {"vacancy_id": "a", "title": "1", "captured_at": "2026-10-01 06:00:00"},
        ]
        dtypes_1 = env.coerce_types(pd.DataFrame(rows)).dtypes.tolist()
        dtypes_2 = env.coerce_types(pd.DataFrame(list(reversed(rows)))).dtypes.tolist()
        # Row order is emit._stable's job; here we only pin the types: if they
        # varied with which stores were present, parquet bytes would change and
        # Hugging Face would re-upload every file on every run.
        self.assertEqual(dtypes_1, dtypes_2)


if __name__ == "__main__":
    unittest.main()
