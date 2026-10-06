"""Emission: build the Hugging Face dataset directory and publish it.

Each dataset partitions its store into files keyed by ``captured_at`` — the
*first* time the pipeline saw a vacancy:

- ``data/spe/week-YYYY-Www.parquet``    — ISO week (immutable once closed)
- ``data/jobspy/day-YYYY-MM-DD.parquet`` — calendar day (immutable once closed)

Why partition by capture date and not publication date: a March vacancy that
an export finally delivers in October belongs to the October drawer. Archive
by publication date and every late-arriving historical row would force
rewriting an already-published file.

Why only the current week/day file re-uploads: rows are frozen
(``keep="first"`` in the stores), so closed files never change; ``_stable``
guarantees identical content produces identical bytes, and
``upload_folder`` skips files already present upstream. Publishing stays
cheap no matter how often the cron fires.

Upload requires ``HF_TOKEN`` (write scope). ``estado.json`` is run state for
the workflow summary and is deliberately *not* uploaded; the static dataset
card (``README.md``) is.
"""

from __future__ import annotations

import argparse
import json
import shutil
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import env
from .schema import COLUMNS

# Dataset directory inside the HF repo (mirrors the local emit dir).
NOMBRE_DATASET = "vacantes-colombia"
REPO_DEFAULT = "pxtron/vacantes-colombia"

# Partition file prefixes, per dataset.
PREFIX = {"spe": "week", "jobspy": "day"}
UNDATED = "undated.parquet"


def _stable(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic shape: fixed types, rows ordered by (vacancy_id, url).

    If the logical content of a partition does not change, the parquet bytes
    do not change either, and ``upload_folder`` skips the file. Column types
    must not depend on which stores happened to be present in the run, and
    row order must not depend on capture order — both are enforced here.

    ``url`` is the tie-breaker because jobspy ids are derived from URL paths
    and can repeat across postings (e.g. Indeed's ``viewjob``); without it,
    byte stability would silently depend on arrival order.
    """
    df = env.coerce_types(df)
    return df.sort_values(["vacancy_id", "url"], kind="stable", na_position="last").reset_index(drop=True)


def _weekly(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split a frame into ISO-week files by ``captured_at``."""
    captured = pd.to_datetime(df["captured_at"], errors="coerce", format="mixed", utc=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        periods = captured.dt.to_period("W")
    names = pd.Series(UNDATED, index=df.index, dtype=object)
    valid = periods.notna()
    if valid.any():
        names.loc[valid] = [
            f"{PREFIX['spe']}-{p.year}-W{p.week:02d}.parquet" for p in periods[valid]
        ]
    return {name: _stable(part) for name, part in df.groupby(names)}


def _daily(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split a frame into day files by ``captured_at``."""
    captured = pd.to_datetime(df["captured_at"], errors="coerce", format="mixed", utc=True)
    names = pd.Series(UNDATED, index=df.index, dtype=object)
    valid = captured.notna()
    if valid.any():
        names.loc[valid] = [
            f"{PREFIX['jobspy']}-{d.date().isoformat()}.parquet"
            for d in captured[valid]
        ]
    return {name: _stable(part) for name, part in df.groupby(names)}


PARTITIONERS = {"spe": _weekly, "jobspy": _daily}


def read_baseline(dataset: str) -> int | None:
    """Rows published before this run (written by ``pipeline pull``).

    ``None`` when there was no pull — emit then refuses to invent a growth
    number out of the total.
    """
    if not env.BASELINE.exists():
        return None
    try:
        data = json.loads(env.BASELINE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    value = data.get(f"rows_{dataset}")
    return int(value) if value is not None else None


def emit(dataset: str, out_root: Path | None = None) -> Path:
    """Write the dataset folder for one dataset: partitions + card + estado."""
    if not env.store_path(dataset).exists():
        raise SystemExit(
            f"ERROR: local store for '{dataset}' not found "
            f"({env.store_path(dataset)}). Run `pipeline pull --dataset {dataset}` first."
        )

    frame = pd.read_parquet(env.store_path(dataset))
    out = (out_root or env.EMIT_DIR) / NOMBRE_DATASET
    data_dir = out / "data" / dataset
    # Rebuild this dataset's folder from scratch: a stale partition left over
    # from a previous local run would otherwise ride along on upload
    # (allow_patterns covers data/<dataset>/*). Scoped to this dataset so an
    # emit of `spe` never touches `data/jobspy/`.
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    parts = PARTITIONERS[dataset](frame) if len(frame) else {}
    for name, part in parts.items():
        part.to_parquet(data_dir / name, index=False)

    baseline = read_baseline(dataset)
    captured = pd.to_datetime(frame["captured_at"], errors="coerce", format="mixed", utc=True)
    estado = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": dataset,
        "rows": int(len(frame)),
        "rows_new": None if baseline is None else int(len(frame)) - baseline,
        "files": len(parts),
        "latest_capture": str(captured.max()) if captured.notna().any() else None,
    }
    (out / "estado.json").write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "README.md").write_text(_card(), encoding="utf-8")

    growth = "" if estado["rows_new"] is None else f", new: {estado['rows_new']:+,}"
    print(f"[emit] {dataset}: {len(frame):,} rows{growth} in {len(parts)} file(s) -> {data_dir}")
    return out


def _card() -> str:
    """Static dataset card (English). Static on purpose: identical bytes on
    every run, so ``upload_folder`` uploads it once and then skips it."""
    return f"""---
license: other
dataset_info:
  config: default
  split: train
---
# vacantes-colombia

Colombian job-posting corpus maintained by the SEXTANTE capture pipeline
(University Tecnológica de Bolívar). Two datasets under `data/`:

- **`data/spe/`** — historical corpus from the official Servicio Público de
  Empleo export (`buscadordeempleo.gov.co`) plus the early curated sources,
  partitioned by capture week: `week-YYYY-Www.parquet`.
- **`data/jobspy/`** — postings captured every hour through JobSpy
  (LinkedIn, Indeed, Bayt) with a general search for Colombia, partitioned
  by capture day: `day-YYYY-MM-DD.parquet`.

## Invariants

- **Append-only**: a vacancy is written once, in the partition of its
  *first* capture, and never rewritten. Closed partitions are immutable.
- **`captured_at` = first observation** (not last), which lets you measure
  time-to-fill (`published_at` -> `captured_at`).
- Dedupe key: `vacancy_id` for SPE (`CODIGO_VACANTE`), `url` for JobSpy.
- Only the current week/day file changes between runs; everything else is
  skipped on upload because its bytes are already upstream.

## Columns (canonical schema, 17)

{", ".join(COLUMNS)}

Column names are English; values stay in Spanish — they describe Colombian
postings. No candidate personal data: only publicly posted job ads.

## Provenance and ethics

1. **SPE** — official mass export of the public employment service (3 HTTP
   requests per capture, the portal's own mechanism, no scraping).
2. **JobSpy boards** — ethical scraping: identifiable User-Agent, throttling,
   robots.txt honored, no block evasion. Site viability is documented in
   `docs/source-viability.md` of the source repository.

See the source repository (github.com/shalom-A26/SEXTANTE) for the pipeline,
the architecture diagrams and the viability study.
"""


def upload(out: Path, dataset: str, repo: str = REPO_DEFAULT) -> None:
    """Upload one dataset's files (plus the card); never touches the other."""
    env.load_local_env()
    import os

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit(
            "ERROR: set HF_TOKEN (huggingface.co/settings/tokens) for upload. "
            "You can put it in a `.env` at the repo root (gitignored)."
        )
    from huggingface_hub import HfApi

    api = HfApi()
    if not api.repo_exists(repo, repo_type="dataset", token=token):
        api.create_repo(repo, repo_type="dataset", private=True, token=token)

    api.upload_folder(
        folder_path=str(out),
        repo_id=repo,
        repo_type="dataset",
        token=token,
        # estado.json is run state, not data; the card rides along.
        allow_patterns=[f"data/{dataset}/*", "README.md"],
    )
    print(f"[emit] uploaded data/{dataset}/ to https://huggingface.co/datasets/{repo}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit the dataset and optionally upload it")
    parser.add_argument("--dataset", choices=[*env.DATASETS, "all"], default="all")
    parser.add_argument("--upload", action="store_true", help="upload to Hugging Face (needs HF_TOKEN)")
    parser.add_argument("--repo", default=REPO_DEFAULT, help=f"target dataset (default: {REPO_DEFAULT})")
    args = parser.parse_args()

    datasets = env.DATASETS if args.dataset == "all" else (args.dataset,)
    for dataset in datasets:
        out = emit(dataset)
        if args.upload:
            upload(out, dataset, args.repo)


if __name__ == "__main__":
    main()
