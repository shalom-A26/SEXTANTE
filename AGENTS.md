# AGENTS.md

Guide for anyone (human or AI agent) changing this repository. Project overview:
[`README.md`](README.md). How the system works: [`docs/architecture.md`](docs/architecture.md).
Claude Code also reads [`CLAUDE.md`](CLAUDE.md), which adds stack and library notes and must
stay consistent with this file.

## What this is

SEXTANTE, a system that reads Colombian job postings at scale: captures them from the official
SPE export and job boards, extracts skills (ESCO), segments occupations, estimates salary bands,
builds a skills graph, and serves a dashboard plus CV matching. Academic project of the
Universidad Tecnológica de Bolívar (team of 4, roster in the README).

- `backend/`: one Python package, `sextante` (src layout).
  - `core/`: the shared contract, 17-column schema (`schema.py`), repo paths and `.env` (`env.py`).
  - `ingestion/`: Stage 1 capture into append-only stores published on Hugging Face.
  - `analytics/`: Stages 2–6 batch run (cleaning, ESCO, duplicates, TF-IDF, NMF, segments,
    salary bands, skills graph) written under `derived/` on HF.
  - `api/`: Stage 8 FastAPI (dashboard aggregates, CV matching), deployed on Render.
- `frontend/`: Next.js 16 + TypeScript, GSAP, three.js, shadcn/ui; deployed on Vercel.
  This Next.js version has breaking changes: read the guide in
  `frontend/node_modules/next/dist/docs/` before writing Next.js code.
- `data/`: local stores and runs (gitignored, rebuilt from HF). `docs/`: architecture, data,
  techniques. `notebooks/`: course demo. `.github/workflows/`: capture, analytics, CI.

## Commands

Run everything from the repository root (`data/` and `.env` live there).

```bash
# backend (Python ≥ 3.10, uv)
uv venv && uv pip install -r backend/requirements/api.txt && uv pip install --no-deps -e backend
.venv/bin/python -m sextante.ingestion probe|pull|capture|emit   # capture CLI
.venv/bin/python -m sextante.analytics demo                      # synthetic run, no HF needed
.venv/bin/python -m sextante.analytics run --esco-csv skills_es.csv [--upload]
.venv/bin/uvicorn sextante.api.main:app --port 8000              # http://127.0.0.1:8000/docs
.venv/bin/python -m unittest discover -s backend/tests           # no network needed
ruff check backend

# frontend
cd frontend
npm run dev                                                      # http://localhost:3000
npm run typecheck && npm run build && node scripts/check-guide.ts
```

## Rules

- **Language**: code, comments, docs and commits in English. UI text is Spanish (Colombian
  users); data *values* stay in Spanish.
- **Commits**: small, Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `ci:`...).
  Work on a branch and open a PR to `main`; CI (`tests.yml`) must pass.
- **Verify before claiming done**: run the tests and, for behaviour changes, the real thing
  (capture locally without `--upload`, the demo run + API, the web app). New non-trivial logic
  gets a test.
- **Data contract**: every source emits the 17 canonical columns of
  `backend/src/sextante/core/schema.py`, in order; `normalize()` before saving, `validate()` to
  check.
- **Append-only, immutable data**: stores use `keep="first"`; a vacancy already present is never
  rewritten and `captured_at` (`%Y-%m-%d %H:%M:%S`) is the first time it was seen. Dedupe keys:
  `vacancy_id` for SPE, `url` for job boards. `published_at` stays as the source gives it.
  Partition by capture date (SPE `week-*`, JobSpy `day-*`), never by publication date.
- **Hugging Face is the memory** (`pxtron/vacantes-colombia`, private): `pull` before capture,
  `emit` after; runners are ephemeral. `emit._stable()` must keep identical content byte-identical
  (tests cover it). Never delete HF paths that hold the corpus. Analytics reads a pinned revision
  and writes only under `derived/`; it never edits source rows.
- **Visible failures**: `capture` exits 1 when a source fails; `emit` writes `estado.json` with
  `rows_new` (`null` without a pull baseline). Never report growth computed from a local total.
- **Honest outputs**: salaries are official SPE **bands**, never exact amounts; match % is a
  ranking heuristic, not a probability; ESCO matches, duplicates and segments are signals until
  validated. The web guide's six rows are fictional and labelled so; demo runs are flagged
  `synthetic`.
- **Data ethics (no exceptions)**: respect `robots.txt`; no block evasion, proxies, logins or
  cookies; identifiable User-Agent (`sextante.USER_AGENT`); throttle requests; SPE only through
  its official export; no personal data of candidates; CVs are processed in memory and never
  stored or logged.
- **Secrets**: `HF_TOKEN` lives in GitHub secrets, Render and a local `.env` (gitignored).
  Never commit or paste tokens; never commit `data/`.
- **Accessibility**: respect `prefers-reduced-motion` (static fallback for the 3D scene), keyboard
  access, visible focus.

## Known traps

- `ingestion/store.count_rows()` reads the Parquet **footer**; never replace it with
  `pd.read_parquet` (Arrow #34314 race → exit 134 at teardown; it killed a production capture on
  2026-10-05).
- `ingestion/sources/spe._VERIFY_SSL` disables TLS verification for the rest of the run after
  the first `SSLError` (the SPE CA chain is incomplete); resets every process.
- `core/env.ROOT` is `parents[4]` of `env.py` (the repo root); the Docker image sets
  `SEXTANTE_ROOT=/app` because the package lives in site-packages there.
- Capture workflows run every 30 min / 12 h on `main` and share the `hf-upload` concurrency group
  with analytics; a broken command stops the corpus from growing, so check the first cron run
  after touching them.
- Fonts (Boska, Switzer) load from Fontshare's CDN; their licence forbids committing the files.

## Keeping docs in sync

Code is not done until the docs describe it. In every PR, check:

| If you change... | Update |
| --- | --- |
| An API endpoint, its params or payload | `docs/architecture.md` § API (and `frontend/lib/api.ts` types) |
| The capture flow, workflows, schedules or concurrency | `docs/architecture.md` § Data flow, sequences, C4 diagrams |
| The schema, a dedupe key, a partition or the HF / local layout | `docs/data.md` (schema, layouts, invariants) |
| A source (URL, export, active job boards, probe results) | `docs/data.md` § Source viability and `ACTIVE_SITES` |
| A file written by an analytics run | `docs/data.md` § Derived artifacts |
| A constant, threshold, formula or technique (TF-IDF, MinHash, K-Means, bands, graph, matching) | `docs/techniques.md` (and the web guide's `pipeline.ts` if it mirrors it) |
| How analytics is run (CLI flags, ESCO setup, GitHub Actions) | `docs/architecture.md` § Analytics runs |
| Deployment, Dockerfile, `render.yaml`, environment variables | `docs/architecture.md` § Hosting / Level 4 and the README quick start |
| Routes, components or the user journey of the web app | `docs/architecture.md` § Web app |
| Folders, packages or commands | `README.md` (layout, quick start), this file and `CLAUDE.md` |
| You find docs that no longer match the code | Fix them in the same PR |

Then add one dated line to the
[architecture changelog](docs/architecture.md#architecture-changelog) describing the change in
system terms (not just "updated code").

Diagrams are Mermaid. Before pushing, render the ones you touched, for example with
`npx -y @mermaid-js/mermaid-cli -i file.mmd -o /tmp/out.svg`, or check the GitHub preview of the
PR. Avoid reserved words as node ids (`end`, `graph`, `subgraph`). A broken diagram is a broken
doc.
