import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline import emit, env, store, sync
from pipeline.schema import COLUMNS

# Two capture dates in different ISO weeks: files are only immutable if the
# round-trip never moves a row between files.
CAPTURE_A = "2026-09-30 06:00:00"   # ISO week 2026-W40
CAPTURE_B = "2026-10-05 06:00:00"   # ISO week 2026-W41


def _rows(dataset: str = "spe") -> list[dict]:
    source = "spe" if dataset == "spe" else "linkedin"
    base = {
        "source": source,
        "company": "Company SA",
        "city": "Bogotá",
        "department": "Cundinamarca",
        "published_at": "2026-09-01",
        "description": "Experience in data and python.",
        "salary_text": "$2.000.000 - $3.000.000",
        "salary_min": 2_000_000,
        "salary_max": 3_000_000,
        "contract_type": "Término indefinido",
        "work_modality": None,
        "education_level": "Universitario",
        "experience_text": "24 meses",
    }
    rows = [
        {**base, "vacancy_id": "v1", "url": "https://x.co/1", "title": "Analista",
         "captured_at": CAPTURE_A},
        {**base, "vacancy_id": "v2", "url": "https://x.co/2", "title": "Ingeniero",
         "captured_at": CAPTURE_B},
        {**base, "vacancy_id": "v3", "url": "https://x.co/3", "title": "Auxiliar",
         "description": None, "captured_at": CAPTURE_A},
    ]
    return rows


class _DatasetDirTest(unittest.TestCase):
    """Redirects env.BASELINE / env.EMIT_DIR / env.STORE_DIR to a temp dir.

    Without this, tests would read and write the real data/ state.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for attr, value in [
            ("BASELINE", root / "_published.json"),
            ("EMIT_DIR", root / "emitido"),
            ("STORE_DIR", root / "store"),
        ]:
            original = getattr(env, attr)
            setattr(env, attr, value)
            self.addCleanup(setattr, env, attr, original)

    def write_store(self, dataset: str, rows: list[dict]) -> None:
        env.write_store(pd.DataFrame(rows), dataset)

    def emit(self, dataset: str) -> Path:
        return emit.emit(dataset)

    def hashes(self, dataset: str) -> dict[str, str]:
        out = env.EMIT_DIR / emit.DATASET_DIR / "data" / dataset
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(out.glob("*.parquet"))
        }


class WeeklyPartitionTest(_DatasetDirTest):
    def test_groups_by_capture_week(self):
        parts = emit._weekly(pd.DataFrame(_rows()))
        self.assertEqual(sorted(parts), ["week-2026-W40.parquet", "week-2026-W41.parquet"])
        self.assertEqual(len(parts["week-2026-W40.parquet"]), 2)
        self.assertEqual(sorted(parts["week-2026-W40.parquet"]["vacancy_id"]), ["v1", "v3"])

    def test_rows_without_date_are_not_lost(self):
        rows = _rows()
        rows[0]["captured_at"] = None
        parts = emit._weekly(pd.DataFrame(rows))
        self.assertIn(emit.UNDATED, parts)
        self.assertEqual(len(parts[emit.UNDATED]), 1)

    def test_internal_order_by_vacancy_id(self):
        parts = emit._weekly(pd.DataFrame(_rows()))
        self.assertEqual(
            list(parts["week-2026-W40.parquet"]["vacancy_id"]), ["v1", "v3"]
        )


class DailyPartitionTest(_DatasetDirTest):
    def test_groups_by_capture_day(self):
        rows = _rows("jobspy")
        parts = emit._daily(pd.DataFrame(rows))
        self.assertEqual(
            sorted(parts),
            ["day-2026-09-30.parquet", "day-2026-10-05.parquet"],
        )
        self.assertEqual(len(parts["day-2026-09-30.parquet"]), 2)


class StableBytesTest(_DatasetDirTest):
    def test_write_is_deterministic_for_same_content(self):
        """If bytes change, upload_folder re-uploads: the savings vanish."""
        rows = _rows()
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.parquet"
            b = Path(tmp) / "b.parquet"
            emit._stable(pd.DataFrame(rows)).to_parquet(a, index=False)
            emit._stable(pd.DataFrame(list(reversed(rows)))).to_parquet(b, index=False)
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),
                             hashlib.sha256(b.read_bytes()).hexdigest())

    def test_emitted_files_carry_the_canonical_schema(self):
        self.write_store("spe", _rows())
        out = self.emit("spe")
        files = sorted((out / "data" / "spe").glob("*.parquet"))
        self.assertTrue(files)
        read = pd.read_parquet(files[0])
        self.assertEqual(list(read.columns), COLUMNS)


class EmitStateTest(_DatasetDirTest):
    def test_reports_new_rows_against_baseline(self):
        self.write_store("spe", _rows())
        env.BASELINE.write_text(json.dumps({"rows_spe": 2}), encoding="utf-8")
        estado = json.loads((self.emit("spe") / "estado.json").read_text("utf-8"))
        self.assertEqual(estado["rows"], 3)
        self.assertEqual(estado["rows_new"], 1)

    def test_zero_growth_is_visible(self):
        """The signal that betrays a dead source: the corpus stopped growing."""
        self.write_store("spe", _rows())
        env.BASELINE.write_text(json.dumps({"rows_spe": 3}), encoding="utf-8")
        estado = json.loads((self.emit("spe") / "estado.json").read_text("utf-8"))
        self.assertEqual(estado["rows_new"], 0)

    def test_without_pull_no_growth_is_invented(self):
        self.write_store("spe", _rows())
        estado = json.loads((self.emit("spe") / "estado.json").read_text("utf-8"))
        self.assertIsNone(estado["rows_new"])

    def test_missing_store_is_a_hard_error(self):
        """Emitting an empty store would publish an empty dataset."""
        with self.assertRaises(SystemExit):
            self.emit("spe")


class RoundTripTest(_DatasetDirTest):
    """emit -> pull -> emit must reproduce identical bytes.

    This is the guarantee that published files stay immutable: if the
    round-trip changed a single byte of a closed file, upload_folder would
    re-upload it on every run and HF storage would grow forever.
    """

    def test_reemit_after_pull_changes_nothing(self):
        self.write_store("spe", _rows())
        first = self.emit("spe")
        hashes_before = self.hashes("spe")

        # What `pipeline pull` does: rebuild the store from what is published.
        published = pd.concat(
            [pd.read_parquet(p) for p in sorted((first / "data" / "spe").glob("*.parquet"))],
            ignore_index=True,
        )
        env.store_path("spe").unlink()
        env.write_store(published, "spe")

        self.emit("spe")
        hashes_after = self.hashes("spe")

        self.assertEqual(hashes_before, hashes_after, "round-trip altered published files")

    def test_new_row_only_touches_the_open_file(self):
        self.write_store("spe", _rows())
        self.emit("spe")
        before = self.hashes("spe")

        # A new vacancy arrives in the current week (W41).
        new = {**_rows()[0], "vacancy_id": "v99", "title": "New", "captured_at": CAPTURE_B}
        added = store.append("spe", pd.DataFrame([new]))
        self.assertEqual(added, 1)

        self.emit("spe")
        after = self.hashes("spe")

        self.assertEqual(before["week-2026-W40.parquet"], after["week-2026-W40.parquet"],
                         "a closed week must never change")
        self.assertNotEqual(before["week-2026-W41.parquet"], after["week-2026-W41.parquet"])


class BaselineMergeTest(_DatasetDirTest):
    def test_pull_of_one_dataset_erases_no_other_baseline(self):
        env.BASELINE.write_text(json.dumps({"rows_spe": 10}), encoding="utf-8")
        sync.write_baseline({"rows_jobspy": 5}, "repo", "main")
        data = json.loads(env.BASELINE.read_text("utf-8"))
        self.assertEqual(data["rows_spe"], 10)
        self.assertEqual(data["rows_jobspy"], 5)

    def test_corrupt_baseline_reads_as_absent(self):
        env.BASELINE.write_text("{broken", encoding="utf-8")
        self.assertIsNone(emit.read_baseline("spe"))


if __name__ == "__main__":
    unittest.main()
