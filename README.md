<p align="center"><img src="docs/assets/logo.svg" alt="SEXTANTE logo" width="96"></p>

# SEXTANTE

**System for skill extraction, occupational segmentation, salary estimation
and detection of risk signals in Colombian labor demand.**

SEXTANTE collects job postings published in Colombia and turns their
free-text descriptions into structured data. The problem it attacks: real
job requirements cannot be known from the title alone — *"Analista junior"*
can mean very different functions and requirements, and the relevant
information usually lives in the description, written as free text with no
uniform taxonomy and inconsistent vocabulary. That makes it hard to measure
which skills the market actually demands, what it pays for them, and how
occupational profiles relate to each other. From that structured data the
project identifies skills, analyzes salaries, groups similar occupational
profiles and detects patterns or anomalies in labor demand.

An academic project of the Universidad Tecnológica de Bolívar (data mining &
analytics course). The Hugging Face dataset is **private** (ask the team for
access); the GitHub repository is public so the Actions cron runs are free.

## Project scope

> **This repository implements the full pipeline end to end**: Stage 1
> capture (`backend/src/sextante/ingestion/`), batch analytics for Stages 2–6
> (`backend/src/sextante/analytics/`, see [`docs/analytics.md`](docs/analytics.md)) and the
> Stage 8 MVP — FastAPI backend (`backend/src/sextante/api/`) and Next.js web app
> (`frontend/`), see [`docs/mvp.md`](docs/mvp.md). What is still pending (a full
> run on the real corpus, manual validation, deployment) is tracked in
> [`docs/roadmap.md`](docs/roadmap.md). The canonical 17-column schema is the
> contract every later stage consumes.

| Stage | Content | Status |
|---|---|---|
| **1 · Data extraction** | SPE official export + JobSpy boards (LinkedIn, Indeed, Bayt) → canonical schema → append-only stores → Hugging Face. Ethical scraping, 30-min + 12h cadence | ✅ **this repository** |
| 2 · Text mining | Skill extraction against the **ESCO** open taxonomy; duplicate detection by textual similarity; exploratory data analysis | 🟡 baseline (`backend/src/sextante/analytics/`: EDA, exact ESCO matching, MinHash duplicate candidates); not yet validated |
| 3 · Text representations | TF-IDF, Word2Vec, transformers for Spanish; topic modeling | 🟡 baseline (TF-IDF + NMF in batch; optional multilingual embeddings; Word2Vec only in the notebook) |
| 4 · Segmentation | Dimensionality reduction (PCA, t-SNE, UMAP) + unsupervised clustering (K-Means, hierarchical, DBSCAN) of occupational profiles | ✅ K-Means published; hierarchical/DBSCAN + t-SNE compared in batch (UMAP notebook-only) |
| 5 · Supervised models | Salary estimation and classification tasks | ✅ Salary-band classifier over the official SPE bands (postings publish bands, not exact salaries), cross-validated against a majority baseline |
| 6 · Skills–occupations graph | Communities, centrality, and occupational transition routes | ✅ skill co-occurrence graph (Louvain, PageRank, betweenness) + segment transition routes |
| 7 · Distributed processing | Apache Spark when the data volume justifies it | ⏸ not needed so far (see roadmap) |
| **8 · MVP product** | Web application (NextJS + FastAPI) — final course deliverable | ✅ built and tested locally on a demo run; not deployed yet |

### Stage 8 — what the product must do

The final deliverable is a startup-style MVP: a web application with a
**landing page** and an **analytical dashboard** where findings are
consulted from three perspectives — **candidates, employers and academic
programs** — presenting trends, gaps and statistical signals.

- **CV integration** (core, not an extra): a person submits their CV; the
  product extracts their profile (skills, experience, education) and
  contrasts it against the vacancy corpus.
- **Profile–job matching with a similarity percentage**: each person sees
  the kind of jobs their profile *actually* matches, **ranked by match
  %** (skills / occupation / seniority).
- **Every match links back to the original job posting so the person can
  apply** — the canonical schema's `url` column already carries the source
  link for this.
- **Recommendations**: whether the person should pivot to another role, in
  which niche their profile is well received, and which gaps to close for a
  target role.
- **Visualizations and dashboard are first-class requirements**, not a
  finishing touch: trends, gaps, statistical signals, the graph, and the
  CV-integration views all rendered in the product.

The CV→vacancy matching and application links build directly on the columns
Stage 1 already publishes: `url`, `description`, `vacancy_id`.

### Course themes applied

- Exploratory data analysis and variable preparation.
- Dimensionality reduction (PCA, t-SNE, UMAP).
- Supervised methods for estimation/classification.
- Unsupervised clustering (K-Means, hierarchical, DBSCAN).
- Text mining and NLP: cleaning, normalization, TF-IDF, topic modeling,
  vector representations.
- Information extraction from web sources.
- Network/graph analytics: communities, centrality, path/connection
  algorithms.
- Distributed processing with Apache Spark when volume justifies it.
- Data ethics, privacy, transparency and responsible use as transversal
  axes.

## Team

| # | Member | Code |
|---|---|---|
| 1 | Alejandro Patrón Montero | T00078181 |
| 2 | Shalom Jhoana Arrieta Marrugo | T00082962 |
| 3 | Karla Andrea Barraza Torres | T00082880 |
| 4 | Katlyn Gutiérrez Cardona | T00082259 |

## Repository layout

```
SEXTANTE/
├── backend/                     # everything Python, one installable package
│   ├── src/sextante/
│   │   ├── core/                # shared contract: 17-column schema, paths, .env
│   │   ├── ingestion/           # Stage 1 capture: SPE + JobSpy → append-only stores → HF
│   │   ├── analytics/           # Stages 2–6: cleaning, ESCO, duplicates, TF-IDF, segments, salary, graph
│   │   └── api/                 # Stage 8 FastAPI: dashboard aggregates, CV matching
│   ├── tests/                   # unittest suite (capture, emission, analytics, API)
│   ├── requirements/            # pinned dependencies: base, analysis, api, dev, embeddings, notebooks
│   ├── pyproject.toml           # package metadata + ruff
│   └── Dockerfile               # API image (deployed on Render via render.yaml)
├── frontend/                    # Next.js app: landing, dashboard, CV flow (deployed on Vercel)
├── data/                        # local stores and analytics runs (gitignored, rebuilt from Hugging Face)
├── docs/                        # architecture (C4 + medallion view), analytics, MVP, roadmap
├── notebooks/                   # course demo notebook
├── scripts/                     # manual capture wrapper, one-off HF migration
├── .github/workflows/           # scheduled capture, daily analytics, CI
└── render.yaml                  # Render blueprint for the API
```

There is no separate `shared/` folder on purpose: frontend and backend share
no code. What they share is a **contract**, the 17-column canonical schema
(`backend/src/sextante/core/schema.py`) and the API responses (mirrored as
types in `frontend/lib/api.ts`); `sextante.core` is that shared layer on the
backend side. Commands run from the repository root (`python -m
sextante.ingestion …`, `python -m sextante.analytics …`) so `data/` stays in
one place.

## How it works (Stage 1)

```
SPE official export ─┐
LinkedIn  ───────────┼─> canonical schema ─> append-only stores ─> data/spe/ + data/jobspy/ ─> Hugging Face
Indeed / Bayt ───────┘        (17 cols)        (dedupe, frozen rows)   (weekly / daily Parquet)
```

1. **Extract** — `pipeline capture --source spe` downloads the SPE's official
   CSV export (~285k vacancies, 3 HTTP requests). `pipeline capture --source
   jobspy` runs a general search (no term, `location=Colombia`) on each
   active job board.
2. **Normalize** — every source maps to the canonical schema
   (`backend/src/sextante/core/schema.py`).
3. **Append** — stores are append-only with `keep="first"`: a vacancy seen
   once is frozen forever. `captured_at` is the *first* observation, never
   overwritten.
4. **Publish** — rows are partitioned by capture date into
   `data/spe/week-YYYY-Www.parquet` (ISO week) and
   `data/jobspy/day-YYYY-MM-DD.parquet` (day), and uploaded to Hugging Face.
   Closed partitions are immutable, so each run only re-uploads the current
   week/day file.

**Hugging Face is the persistent memory.** GitHub Actions runners are
ephemeral: every run starts with `pipeline pull` (restore the published
corpus), captures, then emits and uploads.

## Cadence

| Workflow | Schedule (UTC) | Source |
|---|---|---|
| `.github/workflows/jobspy_capture.yml` | every 30 min at :17 & :47 | JobSpy boards |
| `.github/workflows/spe_12h.yml` | 04:23 & 16:23 (23:23 & 11:23 Colombia) | SPE official export |

The minutes (:17, :47, :23) are deliberately off-peak: GitHub delays or
drops scheduled runs at high-load minutes such as :00 and :05.

The two workflows share a concurrency group so they never upload to Hugging
Face at the same time.

## Usage

```bash
python -m venv .venv && .venv/bin/pip install -r backend/requirements/base.txt
.venv/bin/pip install --no-deps -e backend      # makes the `sextante` package importable

# Which JobSpy sites work for Colombia right now?
.venv/bin/python -m sextante.ingestion probe

# Full local run (needs HF_TOKEN for pull/upload, see below)
.venv/bin/python -m sextante.ingestion pull    --dataset all
.venv/bin/python -m sextante.ingestion capture --source jobspy --results 100
.venv/bin/python -m sextante.ingestion capture --source spe
.venv/bin/python -m sextante.ingestion emit    --dataset all --upload
```

Or use the manual wrapper: `./scripts/capture.sh [jobspy|spe|all]`.

### Tests

```bash
python -m unittest discover -s backend/tests
```

The analysis tests need `backend/requirements/analysis.txt`; CI runs the full suite
plus `ruff check backend` on every push and pull request (`.github/workflows/tests.yml`).

### Analytics and MVP (quick start, no token needed)

```bash
uv pip install -r backend/requirements/api.txt && uv pip install --no-deps -e backend
python -m sextante.analytics demo                 # synthetic run → data/analysis/runs/
uvicorn sextante.api.main:app --port 8000        # API on the newest run
cd frontend && npm install && npm run dev             # web app on http://localhost:3000
```

Real corpus: `python -m sextante.analytics run --esco-csv skills_es.csv [--upload]`
(see [`docs/analytics.md`](docs/analytics.md)).

### Token

Uploads need an `HF_TOKEN` (write scope). Put it in a `.env` at the repo
root (gitignored) or export it — the exported value wins. Never commit it.

## Active sources

| Source | Status | Notes |
|---|---|---|
| **SPE** (`buscadordeempleo.gov.co`) | ✅ | Official mass export, ~285k vacancies/capture, 2021→today |
| **LinkedIn** (JobSpy) | ✅ | General search for Colombia, full descriptions |
| **Indeed** (JobSpy) | ✅ | `country_indeed="colombia"` |
| **Bayt** (JobSpy) | ✅ | Returns Colombia-located rows |
| Glassdoor | ❌ | Not available for Colombia in JobSpy |
| Google | ❌ | Returns no data for this location |
| ZipRecruiter | ❌ | 403 |
| Naukri / BDJobs | ❌ | Ignore the location filter (India / Bangladesh rows) |

Full viability study: [`docs/source-viability.md`](docs/source-viability.md).

## Dataset

`pxtron/vacantes-colombia` (Hugging Face, **private** — ask the team for
access; publishing it publicly is a separate decision):

```
data/
├── spe/
│   ├── week-2026-W38.parquet   # immutable once the week closes
│   └── ...
└── jobspy/
    ├── day-2026-10-05.parquet  # rewritten on every capture run while today lasts
    └── ...
```

- **Dedupe key**: `vacancy_id` for SPE (`CODIGO_VACANTE`), `url` for JobSpy.
- **Schema**: 17 canonical columns, English names, Spanish values (the
  postings are Colombian). No candidate personal data — only public job ads.
- **Growth**: see `estado.json` in the Actions run summary of each capture.

## Ethics

- Identifiable User-Agent, throttling, `robots.txt` respected.
- SPE is downloaded through the portal's official export mechanism (no
  scraping).
- No block evasion, no proxies, no personal credentials.
- No personal data of candidates — only publicly posted vacancies.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — C4 model (Mermaid), data
  flows, sequences, data model.
- [`docs/source-viability.md`](docs/source-viability.md) — source study and
  probe results.
- [`docs/analytics.md`](docs/analytics.md) — batch analytics (Stages 2–6):
  setup, ESCO taxonomy, derived artifacts, models, graph, validation.
- [`docs/mvp.md`](docs/mvp.md) — Stage 8: API endpoints, CV matching method,
  web app, running locally and deploying.
- [`docs/roadmap.md`](docs/roadmap.md) — what is done and what is left.
- [`AGENTS.md`](AGENTS.md) — working agreements for AI agents (commands,
  invariants, hard rules).
