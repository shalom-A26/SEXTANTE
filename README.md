# SEXTANTE

**Colombian job-posting capture pipeline.** Extracts vacancies from the
official Servicio Público de Empleo (SPE) export and from job boards via
[JobSpy](https://github.com/Bunsly/JobSpy) (LinkedIn, Indeed, Bayt),
normalizes everything to a canonical 17-column schema, and publishes them as
Parquet files to a [Hugging Face dataset](https://huggingface.co/datasets/pxtron/vacantes-colombia).

An academic project of the Universidad Tecnológica de Bolívar (data mining &
analytics).

## How it works

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
   (`pipeline/schema.py`).
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
| `.github/workflows/jobspy_hourly.yml` | every hour at :05 | JobSpy boards |
| `.github/workflows/spe_12h.yml` | 04:00 & 16:00 (23:00 & 11:00 Colombia) | SPE official export |

The two workflows share a concurrency group so they never upload to Hugging
Face at the same time.

## Usage

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# Which JobSpy sites work for Colombia right now?
.venv/bin/python -m pipeline probe

# Full local run (needs HF_TOKEN for pull/upload, see below)
.venv/bin/python -m pipeline pull    --dataset all
.venv/bin/python -m pipeline capture --source jobspy --results 100
.venv/bin/python -m pipeline capture --source spe
.venv/bin/python -m pipeline emit    --dataset all --upload
```

Or use the manual wrapper: `./scripts/capture.sh [jobspy|spe|all]`.

### Tests

```bash
python -m unittest discover -s tests
```

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

`pxtron/vacantes-colombia` (Hugging Face, private):

```
data/
├── spe/
│   ├── week-2026-W38.parquet   # immutable once the week closes
│   └── ...
└── jobspy/
    ├── day-2026-10-05.parquet  # rewritten hourly while today lasts
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
- [`AGENTS.md`](AGENTS.md) — working agreements for AI agents (commands,
  invariants, hard rules).
