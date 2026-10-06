# SEXTANTE architecture

> [README](../README.md) · [Source viability](source-viability.md)

C4 model of the pipeline (context, containers, components, deployment), main
data flows, capture sequences and data model. All diagrams are **Mermaid** so
they render in docs, editors and GitHub.

## Contents

1. [Summary](#summary)
2. [C4 model](#c4-model)
   - [Level 1 · Context](#level-1--context)
   - [Level 2 · Containers](#level-2--containers)
   - [Level 3 · Components](#level-3--components)
   - [Level 4 · Deployment](#level-4--deployment)
3. [Data flow and scheduled capture](#data-flow-and-scheduled-capture)
4. [Sequence: hourly JobSpy capture](#sequence-hourly-jobspy-capture)
5. [Sequence: SPE export](#sequence-spe-export)
6. [Data model](#data-model)
7. [Design decisions](#design-decisions)

---

## Summary

SEXTANTE is an ELT pipeline of Colombian job postings:

1. **Extract** from two source groups: the official SPE export (massive,
   ~285k rows/capture) and JobSpy job boards (LinkedIn, Indeed, Bayt) with a
   general search for Colombia.
2. **Normalize** everything to the **canonical 17-column schema**
   (`pipeline/schema.py`, `normalize()` / `validate()`).
3. **Save** in two **append-only local stores** (`data/store/spe.parquet`,
   `data/store/jobspy.parquet`). A vacancy already seen is never rewritten;
   `captured_at` stays fixed at the first observation.
4. **Persistent memory = Hugging Face**: `python -m pipeline pull` recomposes the
   local stores from the published partitions before each run;
   `pipeline emit` publishes them back. The runner is ephemeral, so without
   this step there is no accumulation.
5. **Capture is automated**: hourly for JobSpy
   (`.github/workflows/jobspy_hourly.yml`, cron `5 * * * *` UTC) and every
   12 hours for SPE (`.github/workflows/spe_12h.yml`, cron `0 4,16 * * *`
   UTC). Both share the `hf-upload` concurrency group. There is no local
   cron; `scripts/capture.sh` is the manual development entry point.

**Why two partition grains.** The SPE export is a full snapshot of a portal
that changes slowly: weekly files keep the number of published files low and
each closed week is immutable. JobSpy runs hourly and surfaces new postings
the same day: daily files give an analysis-friendly time series (one row per
capture day) without creating 24 files per day that the same run keeps
rewriting. In both cases only the *current* file changes between runs.

**Upload economics.** Rows are frozen (`keep="first"`), so closed files
never change; `emit._stable()` guarantees identical content produces
identical bytes, and `upload_folder` skips files already present upstream.
Publishing stays cheap no matter how often the cron fires.

---

## C4 model

### Level 1 · Context

Who uses the system and which external systems it talks to.

```mermaid
flowchart LR
    u["UTB team<br/>data mining course"]
    s{{"SEXTANTE<br/>Colombian job-posting<br/>capture pipeline"}}
    spe["SPE · Public Employment Service<br/>buscadordeempleo.gov.co<br/>API /backbue/v1"]
    boards["Job boards via JobSpy<br/>LinkedIn · Indeed · Bayt"]
    hf["Hugging Face Hub<br/>pxtron/vacantes-colombia"]

    u -->|configures, runs, queries| s
    s -->|"official CSV export (3 requests/capture)"| spe
    s -->|"general search, location=Colombia"| boards
    s -->|"partitions data/spe/*.parquet<br/>data/jobspy/*.parquet (append-only)"| hf
    s -.->|"public job ads only"| u

    classDef system fill:#1168bd,color:#fff,stroke:#0b4884;
    classDef external fill:#999999,color:#fff,stroke:#6b6b6b;
    class s system;
    class spe,boards,hf external;
```

- **UTB team**: configures and runs the workflows (GitHub Actions) and
  queries the dataset (CLI + Hugging Face).
- **SPE**: state system offering a mass export (official mechanism, no
  scraping).
- **Job boards**: scraped through JobSpy with ethical criteria
  (identifiable User-Agent, throttling, robots.txt; viability per site in
  [source-viability.md](source-viability.md)).
- **Hugging Face Hub**: persistent memory of the pipeline and destination of
  the published dataset.

### Level 2 · Containers

Decomposition into executable containers and data stores.

```mermaid
flowchart TB
    subgraph RUNNER["GitHub Actions · Ubuntu runner (ephemeral, per run)"]
        wf_h["jobspy_hourly.yml<br/>cron 5 * * * * UTC"]
        wf_s["spe_12h.yml<br/>cron 0 4,16 * * * UTC"]
        pull["pipeline pull<br/>restore stores from HF"]
        cap["pipeline capture<br/>spe | jobspy"]
        emit["pipeline emit<br/>partition + upload"]

        subgraph EPHEMERAL["data/ on the runner (discarded after the run)"]
            store_local[("data/store/<br/>spe.parquet · jobspy.parquet")]
            emit_local[("data/emitido/vacantes-colombia/<br/>data/spe/* · data/jobspy/*")]
        end
    end

    subgraph LOCAL["Local machine (manual development)"]
        sh["scripts/capture.sh"]
        probe["pipeline probe<br/>site viability check"]
        tests["unittest suite"]
    end

    spe_api["SPE /backbue/v1"]
    boards["JobSpy: LinkedIn<br/>Indeed · Bayt"]
    hub["HF Hub (persistent)<br/>data/spe/week-*.parquet<br/>data/jobspy/day-*.parquet"]

    wf_h --> pull
    wf_s --> pull
    pull --> hub
    wf_h --> cap
    wf_s --> cap
    cap -->|"official export API"| spe_api
    cap -->|"scrape_jobs(...)"| boards
    cap --> store_local
    wf_h --> emit
    wf_s --> emit
    emit --> store_local
    emit --> emit_local
    emit_local -->|"--upload (HF_TOKEN)<br/>only current week/day"| hub
    sh -.->|same logic, manually| pull
    probe -.-> boards
    tests -.-> store_local
```

### Level 3 · Components

Inside the `pipeline` package.

```mermaid
flowchart TB
    cli["pipeline/__main__.py<br/>CLI: probe · pull · capture · emit"]
    sync["pipeline/sync.py<br/>pull: rebuild stores<br/>+ write published baseline"]
    emitc["pipeline/emit.py<br/>partition by captured_at<br/>_stable() byte reproducibility<br/>static dataset card"]
    storec["pipeline/store.py<br/>append-only, dedupe keys<br/>count_rows() footer-only"]
    env["pipeline/env.py<br/>paths · .env loader<br/>coerce_types()"]
    schema["pipeline/schema.py<br/>17-column contract<br/>LEGACY_RENAME"]
    spe["pipeline/sources/spe.py<br/>official export → canonical"]
    jobspy["pipeline/sources/jobspy_source.py<br/>scrape_jobs → canonical<br/>ACTIVE_SITES"]

    cli --> sync
    cli --> emitc
    cli --> spe
    cli --> jobspy
    sync --> env
    emitc --> env
    emitc --> storec
    spe --> storec
    jobspy --> storec
    storec --> schema
    emitc --> schema
    spe --> env
    jobspy --> env

    classDef core fill:#1168bd,color:#fff;
    classDef src fill:#36a3f7,color:#fff;
    class schema,env core;
    class spe,jobspy src;
```

| Component | Responsibility | Depends on |
|---|---|---|
| `schema` | Canonical columns, `normalize()`, legacy rename map | — |
| `env` | Paths, `.env` loading, stable type coercion | `schema` |
| `store` | Append-only dedupe per dataset, footer-only counts | `env`, `schema` |
| `sync` | Rebuild stores from HF, published baseline | `env` |
| `emit` | Partition, stabilize bytes, card, upload | `env`, `store` |
| `sources.spe` | Official export → canonical | `store`, `env` |
| `sources.jobspy_source` | JobSpy → canonical, active sites | `store`, `env` |
| `__main__` | CLI wiring | everything |

### Level 4 · Deployment

```mermaid
flowchart LR
    subgraph GH["GitHub"]
        repo["shalom-A26/SEXTANTE<br/>(public)"]
        actions["Actions runners<br/>hourly + 12h"]
    end

    subgraph HF["Hugging Face"]
        ds["dataset pxtron/vacantes-colombia<br/>data/spe/ · data/jobspy/ · README.md"]
        secret["secret HF_TOKEN<br/>(write scope)"]
    end

    repo --> actions
    actions -->|"pull → capture → emit → upload"| ds
    secret -.->|"read by Actions"| actions
```

The local machine is optional: it runs the same CLI manually
(`scripts/capture.sh`) and the test suite. No service is permanently deployed.

---

## Data flow and scheduled capture

```mermaid
flowchart TB
    start(["cron fires"]) --> pull["pipeline pull<br/>restore store(s) from HF<br/>write data/_published.json baseline"]
    pull --> which{"which workflow?"}

    which -->|"hourly"| js["capture --source jobspy<br/>general search per active site<br/>→ append, dedupe by url"]
    which -->|"12h"| sp["capture --source spe<br/>official CSV export → append,<br/>dedupe by vacancy_id"]

    js --> emitj["emit --dataset jobspy<br/>data/jobspy/day-YYYY-MM-DD.parquet"]
    sp --> emits["emit --dataset spe<br/>data/spe/week-YYYY-Www.parquet"]

    emitj --> up["upload: current day file<br/>+ static card; closed files skipped"]
    emits --> up

    up --> estado["estado.json: rows,<br/>rows_new, latest_capture"]
    estado --> summary["Actions run summary<br/>warns on zero growth"]
    summary --> end(["done"])

    classDef warn fill:#d9534f,color:#fff;
    class summary warn;
```

Failure behavior:

- `pipeline capture` exits with code 1 if a source fails (a restored store
  would otherwise make the run *look* healthy while the corpus stopped
  growing).
- `pipeline emit` refuses to run when the store is missing (emitting an
  empty store would publish an empty dataset).
- `rows_new` is `null` when there was no pull baseline — growth is never
  invented from the total.

---

## Sequence: hourly JobSpy capture

```mermaid
sequenceDiagram
    participant cron as GitHub Actions
    participant hf as Hugging Face
    participant p as pipeline
    participant jb as Job boards

    cron->>p: pipeline pull --dataset jobspy
    p->>hf: list data/jobspy/*.parquet
    hf-->>p: partition files
    p->>hf: download partitions
    hf-->>p: parquet bytes
    p->>p: rebuild data/store/jobspy.parquet<br/>+ write baseline data/_published.json

    cron->>p: pipeline capture --source jobspy
    loop each active site (linkedin, indeed, bayt)
        p->>jb: scrape_jobs(site, location=Colombia,<br/>search_term=None, fetch_description=True)
        jb-->>p: jobs DataFrame
    end
    p->>p: map to canonical schema<br/>append, dedupe by url (keep first)

    cron->>p: pipeline emit --dataset jobspy --upload
    p->>p: partition by captured_at day<br/>_stable(): types + (vacancy_id, url) order
    p->>hf: upload_folder(data/jobspy/*, README.md)<br/>skips unchanged (byte-identical) files
    p->>p: estado.json (rows, rows_new)
    p-->>cron: exit 0 / 1
```

## Sequence: SPE export

```mermaid
sequenceDiagram
    participant cron as GitHub Actions
    participant p as pipeline
    participant spe as SPE API /backbue/v1
    participant hf as Hugging Face

    cron->>p: pipeline pull --dataset spe
    p->>hf: download data/spe/week-*.parquet
    hf-->>p: partitions (rebuild store + baseline)

    cron->>p: pipeline capture --source spe
    p->>spe: POST /vacantes/export/csv/async
    spe-->>p: {jobId} (202)
    loop up to ~5 min
        p->>spe: GET .../status
        spe-->>p: processing / completed
    end
    p->>spe: GET .../download
    spe-->>p: CSV (~415 MB)
    p->>p: map to canonical schema<br/>append, dedupe by vacancy_id

    cron->>p: pipeline emit --dataset spe --upload
    p->>p: partition by captured_at ISO week
    p->>hf: upload current week file only
    p-->>cron: exit 0 / 1
```

---

## Data model

### Canonical schema (17 columns)

| # | Column | Type | Meaning |
|---|---|---|---|
| 1 | `vacancy_id` | text | Primary key: `spe-<CODIGO_VACANTE>` / id from the job URL |
| 2 | `source` | text | Origin: `spe`, `linkedin`, `indeed`, `bayt`, ... |
| 3 | `url` | text | Posting URL (dedupe key for jobspy) |
| 4 | `title` | text | Job title |
| 5 | `company` | text | Employer |
| 6 | `city` | text | City (parsed from the source location) |
| 7 | `department` | text | Department, when the source provides it |
| 8 | `published_at` | text | Publication date as given by the source |
| 9 | `description` | text | Full description, when available |
| 10 | `salary_text` | text | Salary as written (band or range) |
| 11 | `salary_min` | float | Numeric lower bound (COP), when parseable |
| 12 | `salary_max` | float | Numeric upper bound (COP), when parseable |
| 13 | `contract_type` | text | Contract type |
| 14 | `work_modality` | text | `Teletrabajo` / `Remoto`, when flagged |
| 15 | `education_level` | text | Required education, when provided |
| 16 | `experience_text` | text | Experience requirement as text |
| 17 | `captured_at` | text | **First** capture timestamp (`%Y-%m-%d %H:%M:%S`) |

Column names are English (renamed on 2026-10-05 from the original Spanish
schema); values stay in Spanish. Unavailable fields are null.

### Published layout (Hugging Face)

```
data/
├── spe/
│   ├── week-2026-W38.parquet    # rows first captured in ISO week 38
│   ├── week-2026-W41.parquet    # current week (the only file that changes)
│   └── undated.parquet          # rows without a parseable captured_at
└── jobspy/
    ├── day-2026-10-04.parquet   # closed day: immutable
    ├── day-2026-10-05.parquet   # current day (rewritten hourly)
    └── undated.parquet
```

Plus a static `README.md` (dataset card; identical bytes every run, uploaded
once) and, locally only, `estado.json` (run state, never uploaded).

### Invariants

- **Partition by capture date**: each row lives in the file of the week/day
  it was *first* seen; the row is frozen, so closed files are immutable.
- **Dedupe keys**: `vacancy_id` (spe) / `url` (jobspy).
- **Byte stability**: `_stable()` fixes dtypes and orders rows by
  `(vacancy_id, url)`; same content ⇒ same bytes ⇒ `upload_folder` skips.
- **Baseline**: `data/_published.json` (written by `pull`) is what lets
  `estado.json` report genuinely new rows.

---

## Design decisions

| Decision | Alternative rejected | Why |
|---|---|---|
| Two datasets (`spe/`, `jobspy/`) | Single mixed folder | Different cadence and grain; lets each workflow publish independently without touching the other's files |
| Weekly files for SPE, daily for JobSpy | Hourly files | A run's new rows are tens, not thousands; hourly files would multiply file count for no analytical gain. SPE changes little in 24h |
| Partition by `captured_at` | Partition by `published_at` | Late-arriving historical rows (SPE back to 2021) would force rewriting already-published files |
| Append-only (`keep="first"`) | Upsert latest version | Freezes rows ⇒ immutable closed files ⇒ cheap uploads; `captured_at` keeps its "first seen" meaning |
| HF as the only memory | Local database / CI cache | Runners are ephemeral; HF gives a single durable, queryable source of truth |
| Pull before capture, hard-fail on error | Best-effort pull | Without it a fresh runner would publish an incomplete corpus over a healthy one |
| Static dataset card | Card with live counts | Counts change every run ⇒ bytes change ⇒ re-upload every run. Counts live in `estado.json` instead |
| Footer-only row counts (`count_rows`) | `pd.read_parquet` | Arrow #34314 race: thread-pooled reader alive at shutdown aborts the process with exit 134 |
| One 12h SPE workflow | Hourly SPE capture | ~415 MB export per run, slow-changing portal; 2 runs/day is enough and kinder to a state service |
