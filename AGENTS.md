# AGENTS.md — Guide for AI agents working on SEXTANTE

Academic data-mining project: Colombian job-posting capture pipeline
(SPE official export + JobSpy boards → canonical schema → Hugging Face).

All code, comments, docs and commit messages are in **English**. The data
*values* stay in Spanish — they describe Colombian postings.

## Project context

**Full project name**: *SEXTANTE — System for skill extraction, occupational
segmentation, salary estimation and detection of risk signals in Colombian
labor demand.* Academic project of the Universidad Tecnológica de Bolívar
(team of 4; the roster lives in the README's Team section).

**Problem**: real job requirements cannot be inferred from the job title
alone (`"Analista junior"` hides very different functions); the signal lives
in the free-text description, which has no uniform taxonomy and inconsistent
vocabulary. SEXTANTE turns Colombian job postings into structured data and,
down the line, measures demanded skills, salaries, occupational profiles and
demand risk signals.

**Final deliverable** (course roadmap): a startup-style MVP web app
(NextJS + FastAPI) with a landing page and a first-class
**analytics/visualization dashboard** for candidates, employers and academic
programs — including a **CV-upload flow** that extracts the candidate's
profile, scores it against the vacancy corpus with a **similarity
percentage**, shows the jobs the profile actually matches **with links back
to the live posting so the person can apply**, and recommends role pivots,
welcomed niches and skill gaps. CV integration and visualizations are core
requirements, not extras.

**Stage map**:

| Stage | Content | Status |
|---|---|---|
| 1 · Data extraction | SPE + JobSpy → canonical schema → HF | ✅ **this repository** |
| 2 · Text mining | ESCO skill extraction, duplicate detection by textual similarity, EDA | 🔜 planned |
| 3 · Representations | TF-IDF, Word2Vec, Spanish transformers, topic modeling | 🔜 planned |
| 4 · Segmentation | PCA/t-SNE/UMAP + K-Means/hierarchical/DBSCAN | 🔜 planned |
| 5 · Supervised models | Salary estimation / classification | 🔜 planned |
| 6 · Skills–occupations graph | Communities, centrality, transition routes | 🔜 planned |
| 7 · Distributed | Apache Spark if volume justifies it | if needed |
| 8 · MVP product | Web app + dashboard + CV matching & recommendations | 🔜 planned |

**Operating rule for agents**: this repository currently contains **Stage 1
(data extraction) only**. There is no analysis, NLP, modeling, graph or web
code here — and none may be added unless explicitly requested. The
17-column canonical schema (`pipeline/schema.py`) is the contract all
future stages consume; treat `data/spe/` + `data/jobspy/` on Hugging Face as
the corpus those stages will read. When asked for "the project", know that
the capture pipeline is the foundation, not the whole product.

## Useful commands

```bash
# Environment
.venv/bin/python --version        # Python >= 3.10 (venv created with uv)
uv pip install -r requirements.txt            # capture pipeline (pinned; what CI installs)

# Which JobSpy sites work for Colombia right now?
.venv/bin/python -m pipeline probe

# Full cycle (needs HF_TOKEN; see "Secrets")
.venv/bin/python -m pipeline pull    --dataset all      # restore corpus from HF
.venv/bin/python -m pipeline capture --source jobspy --results 100
.venv/bin/python -m pipeline capture --source spe
.venv/bin/python -m pipeline emit    --dataset all --upload

# Manual local capture (dev; automation runs in GitHub Actions)
./scripts/capture.sh [jobspy|spe|all]

# Tests
python -m unittest discover -s tests

# One-off: migrate the HF dataset to the data/spe/ + data/jobspy/ layout
# (already run on 2026-10-05; kept for reference)
HF_TOKEN=hf_xxx .venv/bin/python scripts/migrate_hf.py --repo pxtron/vacantes-colombia
```

The whole test suite (capture, emission, sync, SPE, JobSpy mapping,
environment) runs with `python -m unittest discover -s tests`. There is no
linter configured.

**Automated capture runs in GitHub Actions**:
- `.github/workflows/jobspy_capture.yml` — cron `17,47 * * * *` UTC (every
  30 min; off-peak minutes on purpose, see the workflow comment).
- `.github/workflows/spe_12h.yml` — cron `23 4,16 * * *` UTC (23:23/11:23
  Colombia time). The SPE export is a ~415 MB snapshot that barely changes
  hour to hour.
Both workflows share the `hf-upload` concurrency group so they never push to
Hugging Face simultaneously. Both can also be triggered manually with
`workflow_dispatch`.

## Project rules (critical)

1. **Data contract**: every source must emit the **canonical 17-column
   schema** of `pipeline/schema.py`, in the exact order. Use `normalize()`
   before saving and `validate()` to check.
2. **Data ethics (no exceptions)**:
   - Never break `robots.txt`. No block evasion, no personal login/cookies,
     no proxies.
   - No personal data of candidates.
   - Identifiable `User-Agent`: `SEXTANTE-UTB-university-research/1.0 (...)`
     (defined as `pipeline.USER_AGENT`).
   - Throttling on requests.
   - SPE is downloaded via the portal's official export mechanism only.
3. **Dates**: `captured_at` is always stamped `%Y-%m-%d %H:%M:%S`;
   `published_at` stays exactly as the source gives it (variable format).
   Stores are append-only, so `captured_at` is the **first** time we saw the
   vacancy: never overwrite it.
4. **Append-only stores (`keep="first"`)**: a vacancy already present is
   **never rewritten**. This is what makes published files immutable.
   - Dedupe key for `spe`: `vacancy_id` (`CODIGO_VACANTE`; several distinct
     vacancies can share a provider URL).
   - Dedupe key for `jobspy`: `url`.
   - Implemented in `pipeline/store.append()`; returns how many rows are
     *new*, never the total.
5. **Cross-source duplicates** are distinguished by the `source` column
   (`spe`, `linkedin`, `indeed`, `bayt`, ...).
6. **Persistent memory = Hugging Face** (`pxtron/vacantes-colombia`):
   - `data/spe/week-*.parquet` — ISO week of `captured_at`.
   - `data/jobspy/day-*.parquet` — calendar day of `captured_at`.
   - Before capturing, rebuild the stores with `pipeline pull`; after
     capturing, republish with `pipeline emit`. The GitHub Actions runner is
     ephemeral: without the pull there is no accumulation.
   - Partition by **capture date**, not publication date: archiving by
     `published_at` would force reopening files that are already published.
   - `emit._stable()` fixes types and row order: identical content must
     produce identical bytes, or `upload_folder` re-uploads the file and the
     savings are lost. If you touch that function, there are tests covering it.
   - Never delete HF paths that still hold the corpus; the migration script
     (`scripts/migrate_hf.py`) is the only place allowed to delete legacy
     layout files, and only after a verified upload.
7. **Visible failures**: `pipeline capture` exits with code 1 when a source
   fails, and `pipeline emit` writes `estado.json` with the run's counts
   (including `rows_new`, which is `null` when there was no pull baseline).
   Do not reintroduce summary branches that only compare against a local
   total.
8. **Secrets**: `HF_TOKEN` lives as a repository secret (GitHub) and in a
   local `.env` (gitignored). Never paste tokens into chat or commit them;
   rotate the secret when it changes.

## Domain / glossary

- **Vacancy/job offer**: a job posting with a free-text description.
- **Canonical schema**: the 17 columns documented in the README.
- **Source/portal**: where a posting is extracted from (`spe`, `linkedin`,
  `indeed`, `bayt`, ...).
- **Store**: local append-only parquet per dataset
  (`data/store/<dataset>.parquet`), rebuildable from HF.
- **Capture date**: when the pipeline first saw the vacancy; unit of
  partitioning (`week-*` for SPE, `day-*` for JobSpy).
- **Emission**: turning stores into the published partition files.

## Architecture

- `pipeline/schema.py` — 17-column contract (+ legacy rename map).
- `pipeline/env.py` — paths, `.env` loading, stable type coercion.
- `pipeline/store.py` — append-only stores, dedupe, footer-only row counts.
- `pipeline/sync.py` — `pull`: rebuild stores from HF, write the published
  baseline (`data/_published.json`).
- `pipeline/emit.py` — partition, write `data/spe/` + `data/jobspy/`, static
  dataset card, upload.
- `pipeline/sources/spe.py` — official SPE export → canonical schema.
- `pipeline/sources/jobspy_source.py` — JobSpy general search → canonical
  schema; holds `ACTIVE_SITES`.
- `pipeline/__main__.py` — CLI (`probe | pull | capture | emit`).
- `scripts/capture.sh` — manual local capture.
- `scripts/migrate_hf.py` — one-off HF layout migration (already run).
- `.github/workflows/jobspy_capture.yml`, `.github/workflows/spe_12h.yml` —
  automated capture.
- `tests/` — 49 tests: stores, emission (incl. byte-stable round-trip), SPE
  source, JobSpy mapping, environment.
- `docs/architecture.md` — C4 model, all diagrams in Mermaid.
- `docs/source-viability.md` — source study, probe results.

## Known traps

- `pipeline.store.count_rows()` reads the parquet **footer**; never replace
  it with `pd.read_parquet` (Arrow #34314 race → exit 134 at teardown; it
  killed a production capture on 2026-10-05). Covered by tests.
- `pipeline.sources.spe._VERIFY_SSL` disables TLS verification for the rest
  of the run after the first `SSLError` (the SPE CA chain is incomplete).
  Covered by tests; resets every process.
- Uploads require `HF_TOKEN`; `pipeline emit --upload` without it fails
  loudly by design.

## Documentation

- `README.md` — description, usage, active sources, dataset layout.
- `docs/architecture.md` — C4 model (context, containers, components,
  deployment), flows, sequences, data model. All diagrams in Mermaid.
- `docs/source-viability.md` — source viability study.
- Rule: when architecture or diagrams change, update the docs in the same
  commit. Docs are English-only (the es/en split was removed in the
  2026-10-05 refactor).
