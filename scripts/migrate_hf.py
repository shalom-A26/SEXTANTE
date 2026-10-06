#!/usr/bin/env python
"""One-off migration of the Hugging Face dataset to the new two-folder layout.

Old layout (pre 2026-10-05)::

    data/semana-YYYY-Www.parquet   # mixed SPE + curated, Spanish columns
    store/... , train-*-of-*.parquet   # legacy leftovers (deleted)

New layout::

    data/spe/week-YYYY-Www.parquet     # English columns, `almacen` dropped
    data/jobspy/                       # starts empty; the capture pipeline fills it

Steps (safety first — upload before delete):

1. Download the published weekly files; count rows.
2. Rename Spanish columns to English, drop `almacen`.
3. Rebuild the local ``spe`` store and emit ``data/spe/``.
4. Abort if any row would be lost.
5. Upload ``data/spe/`` + card.
6. Only then delete the old paths (root weeklies, ``store/``, ``train-*``).

Usage::

    HF_TOKEN=hf_xxx .venv/bin/python scripts/migrate_hf.py --repo pxtron/vacantes-colombia
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import emit as emit_mod  # noqa: E402
from pipeline import env, store  # noqa: E402
from pipeline.schema import COLUMNS, LEGACY_RENAME  # noqa: E402

LEGACY_ROOT_PREFIX = "data/semana-"
LEGACY_STORE_PREFIX = "store/"
LEGACY_SHARD = re.compile(r"^train-\d{5}-of-\d{5}\.parquet$")


def _list_files(repo: str, token: str | None) -> tuple[list[str], list[str]]:
    from huggingface_hub import HfApi

    info = HfApi().repo_info(repo, repo_type="dataset", token=token)
    names = [s.rfilename for s in info.siblings]
    weeklies = sorted(n for n in names if n.startswith(LEGACY_ROOT_PREFIX) and n.endswith(".parquet"))
    legacy = [n for n in names if n.startswith(LEGACY_STORE_PREFIX) or LEGACY_SHARD.match(Path(n).name)]
    return weeklies, legacy


def _download(repo: str, paths: list[str], token: str | None) -> pd.DataFrame:
    from huggingface_hub import hf_hub_download

    parts = []
    for path in paths:
        cache = hf_hub_download(repo, path, repo_type="dataset", token=token)
        parts.append(pd.read_parquet(cache))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return pd.concat(parts, ignore_index=True)


def _to_english(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    out = df.rename(columns=LEGACY_RENAME)
    if "almacen" in out.columns:
        out = out.drop(columns=["almacen"])

    missing = [c for c in COLUMNS if c not in out.columns]
    if missing:
        raise SystemExit(f"ERROR: legacy files are missing canonical columns: {missing}")
    # Safety net: the store dedupes by vacancy_id, so compare against unique
    # ids, not raw rows — otherwise a (forbidden) duplicate would look like
    # data loss and abort a healthy migration.
    return out[COLUMNS], int(out["vacancy_id"].nunique(dropna=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate the HF dataset to data/spe/ + data/jobspy/")
    parser.add_argument("--repo", default="pxtron/vacantes-colombia")
    parser.add_argument("--upload", action="store_true", default=True)
    parser.add_argument("--no-upload", dest="upload", action="store_false",
                        help="build everything locally without touching HF (dry run)")
    args = parser.parse_args()

    env.load_local_env()
    token = os.environ.get("HF_TOKEN")
    if args.upload and not token:
        print("ERROR: HF_TOKEN is required (or pass --no-upload for a dry run)", file=sys.stderr)
        return 1

    weeklies, legacy = _list_files(args.repo, token)
    print(f"[migrate] found {len(weeklies)} legacy weekly file(s), {len(legacy)} legacy path(s) to delete")
    if not weeklies:
        print("[migrate] nothing to migrate (already migrated?)")
        return 0

    raw = _download(args.repo, weeklies, token)
    print(f"[migrate] downloaded {len(raw):,} rows")
    if "almacen" not in raw.columns:
        print("ERROR: legacy files have no `almacen` column — is this really the old layout?", file=sys.stderr)
        return 1

    frame, expected = _to_english(raw)
    print(f"[migrate] renamed columns to English: {len(frame):,} rows ({expected:,} unique ids) ready")

    # Rebuild the local spe store (dedupe by vacancy_id, first wins),
    # clearing any stale local store so the migration is reproducible.
    env.store_path("spe").unlink(missing_ok=True)
    added = store.append("spe", frame)
    print(f"[migrate] local spe store: {added:,} rows")

    out = emit_mod.emit("spe")
    emitted = sum(
        len(pd.read_parquet(p, columns=["vacancy_id"]))
        for p in sorted((out / "data" / "spe").glob("*.parquet"))
    )
    print(f"[migrate] emitted {emitted:,} rows into data/spe/")

    if emitted < expected:
        print(
            f"ERROR: row loss ({expected:,} unique ids -> {emitted:,} emitted); aborting BEFORE any upload/delete",
            file=sys.stderr,
        )
        return 1

    if args.upload:
        emit_mod.upload(out, "spe", args.repo)

        # Delete legacy paths only after a successful upload.
        from huggingface_hub import HfApi

        api = HfApi()
        for path in weeklies + legacy:
            try:
                api.delete_file(path, repo_id=args.repo, repo_type="dataset", token=token)
                print(f"[migrate] deleted legacy: {path}")
            except Exception as exc:  # noqa: BLE001
                print(f"[migrate] could not delete {path}: {exc}")

    print("[migrate] done" + ("" if args.upload else " (dry run: nothing uploaded)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
