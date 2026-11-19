# SEXTANTE architecture

> [README](../README.md) · [Data](data.md) · [Techniques](techniques.md) · [Source viability](source-viability.md)

How SEXTANTE is built: C4 model (context, containers, components,
deployment), the scheduled data flow, the capture sequences and the design
decisions. The data itself (schema, medallion layers, layouts) is in
[data.md](data.md); what each technique does is in
[techniques.md](techniques.md). All diagrams are **Mermaid** so they render
in docs, editors and GitHub.

## Contents

1. [Summary](#summary)
2. [C4 model](#c4-model)
   - [Level 1 · Context](#level-1--context)
   - [Level 2 · Containers](#level-2--containers)
   - [Level 3 · Components](#level-3--components)
   - [Level 4 · Deployment](#level-4--deployment)
3. [Data flow and scheduled capture](#data-flow-and-scheduled-capture)
4. [Data layers](#data-layers) (details in [data.md](data.md))
5. [Sequence: JobSpy capture](#sequence-jobspy-capture)
6. [Sequence: SPE export](#sequence-spe-export)
7. [Design decisions](#design-decisions)

---

## Summary

SEXTANTE has three parts that share one data contract (the 17-column
schema in `backend/src/sextante/core/schema.py`):

- **Capture** (`sextante.ingestion`): an ELT pipeline of Colombian job
  postings, described step by step below.
- **Analytics** (`sextante.analytics`): a daily batch run that reads a pinned
  revision of the corpus and publishes derived artifacts under `derived/`
  (see [analytics.md](analytics.md), [techniques.md](techniques.md)).
- **Product** (`sextante.api` + `frontend/`): a FastAPI service that loads
  the latest run and a Next.js web app with the dashboard and the CV flow
  (see [mvp.md](mvp.md)).

The capture pipeline:

1. **Extract** from two source groups: the official SPE export (massive,
   ~285k rows/capture) and JobSpy job boards (LinkedIn, Indeed, Bayt) with a
   general search for Colombia.
2. **Normalize** everything to the **canonical 17-column schema**
   (`backend/src/sextante/core/schema.py`, `normalize()` / `validate()`).
3. **Save** in two **append-only local stores** (`data/store/spe.parquet`,
   `data/store/jobspy.parquet`). A vacancy already seen is never rewritten;
   `captured_at` stays fixed at the first observation.
4. **Persistent memory = Hugging Face**: `python -m sextante.ingestion pull` recomposes the
   local stores from the published partitions before each run;
   `python -m sextante.ingestion emit` publishes them back. The runner is ephemeral, so without
   this step there is no accumulation.
5. **Capture is automated**: every 30 minutes for JobSpy
   (`.github/workflows/jobspy_capture.yml`, cron `17,47 * * * *` UTC) and
   twice a day for SPE (`.github/workflows/spe_12h.yml`, cron `23 4,16 * * *`
   UTC). Both share the `hf-upload` concurrency group. Cron minutes are
   deliberately off-peak: GitHub delays or drops scheduled runs at
   high-load minutes like :00/:05. There is no local
   cron; `scripts/capture.sh` is the manual development entry point.

**Why two partition grains.** The SPE export is a full snapshot of a portal
that changes slowly: weekly files keep the number of published files low and
each closed week is immutable. JobSpy runs every 30 minutes and surfaces new
postings the same day: daily files give an analysis-friendly time series (one
row per capture day) without creating dozens of files per day that the same
run keeps rewriting. In both cases only the *current* file changes between
runs.

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
    people["Candidates · employers ·<br/>academic programs"]
    s{{"SEXTANTE<br/>capture · analytics ·<br/>API + web app"}}
    spe["SPE · Public Employment Service<br/>buscadordeempleo.gov.co<br/>API /backbue/v1"]
    boards["Job boards via JobSpy<br/>LinkedIn · Indeed · Bayt"]
    hf["Hugging Face Hub<br/>pxtron/vacantes-colombia"]

    u -->|configures, runs, queries| s
    s -->|"official CSV export (3 requests/capture)"| spe
    s -->|"general search, location=Colombia"| boards
    s -->|"partitions data/spe/*.parquet<br/>data/jobspy/*.parquet (append-only)"| hf
    s -.->|"public job ads only"| u
    people -->|"dashboard, CV matching"| s

    classDef system fill:#1168bd,color:#fff,stroke:#0b4884;
    classDef external fill:#999999,color:#fff,stroke:#6b6b6b;
    class s system;
    class spe,boards,hf external;
```

- **UTB team**: configures and runs the workflows (GitHub Actions) and
  queries the dataset (CLI + Hugging Face).
- **Candidates, employers, academic programs**: use the web app; a CV sent
  for matching is processed in memory and never stored.
- **SPE**: state system offering a mass export (official mechanism, no
  scraping).
- **Job boards**: scraped through JobSpy with ethical criteria
  (identifiable User-Agent, throttling, robots.txt; viability per site in
  [source-viability.md](source-viability.md)).
- **Hugging Face Hub**: persistent memory of the pipeline and destination of
  the published dataset.

### Level 2 · Containers

Decomposition into executable containers and data stores. First the
capture side, then analytics and the product.

```mermaid
flowchart TB
    subgraph RUNNER["GitHub Actions · Ubuntu runner (ephemeral, per run)"]
        wf_h["jobspy_capture.yml<br/>cron 17,47 * * * * UTC"]
        wf_s["spe_12h.yml<br/>cron 23 4,16 * * * UTC"]
        pull["sextante.ingestion pull<br/>restore stores from HF"]
        cap["sextante.ingestion capture<br/>spe | jobspy"]
        emit["sextante.ingestion emit<br/>partition + upload"]

        subgraph EPHEMERAL["data/ on the runner (discarded after the run)"]
            store_local[("data/store/<br/>spe.parquet · jobspy.parquet")]
            emit_local[("data/emitido/vacantes-colombia/<br/>data/spe/* · data/jobspy/*")]
        end
    end

    subgraph LOCAL["Local machine (manual development)"]
        sh["scripts/capture.sh"]
        probe["sextante.ingestion probe<br/>site viability check"]
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

**Analytics and product containers**

```mermaid
flowchart LR
    hub["HF Hub<br/>data/spe · data/jobspy"]
    batch["analytics.yml · daily 06:00 UTC<br/>sextante.analytics run<br/>(pinned corpus revision)"]
    derived["HF Hub<br/>derived/runs/&lt;id&gt; · latest.json"]
    api["sextante.api on Render<br/>FastAPI (in-memory serving bundle)"]
    web["frontend/ on Vercel<br/>Next.js dashboard + CV"]
    user(("Candidate / employer /<br/>academic program"))

    hub --> batch --> derived --> api
    batch -.->|"deploy hook"| api
    web -->|"/api/dashboard, /api/cv/match"| api
    user --> web
    web -.->|"apply link (url)"| sourcejob["Original posting"]
```

The CV travels only in the request to `/api/cv/match`; nothing is stored.
Details: [analytics.md](analytics.md), [mvp.md](mvp.md).

### Level 3 · Components

Inside the capture side: `sextante.ingestion` plus the shared `sextante.core`.
The analytics modules are listed in [techniques.md](techniques.md); the API
modules in [mvp.md](mvp.md).

```mermaid
flowchart TB
    cli["sextante/ingestion/__main__.py<br/>CLI: probe · pull · capture · emit"]
    sync["sextante/ingestion/sync.py<br/>pull: rebuild stores<br/>+ write published baseline"]
    emitc["sextante/ingestion/emit.py<br/>partition by captured_at<br/>_stable() byte reproducibility<br/>static dataset card"]
    storec["sextante/ingestion/store.py<br/>append-only, dedupe keys<br/>count_rows() footer-only"]
    env["sextante/core/env.py<br/>paths · .env loader<br/>coerce_types()"]
    schema["sextante/core/schema.py<br/>17-column contract<br/>LEGACY_RENAME"]
    spe["sextante/ingestion/sources/spe.py<br/>official export → canonical"]
    jobspy["sextante/ingestion/sources/jobspy_source.py<br/>scrape_jobs → canonical<br/>ACTIVE_SITES"]

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
        actions["Actions runners<br/>capture 30 min + 12 h ·<br/>analytics daily · CI"]
        secrets["repository secrets<br/>HF_TOKEN · RENDER_DEPLOY_HOOK_URL"]
    end

    subgraph HF["Hugging Face (private dataset)"]
        ds["pxtron/vacantes-colombia<br/>data/spe/ · data/jobspy/ · README.md"]
        derived["derived/runs/&lt;id&gt; · derived/latest.json"]
    end

    subgraph RENDER["Render (free instance)"]
        api["sextante-api<br/>backend/Dockerfile"]
    end

    subgraph VERCEL["Vercel"]
        web["sextante-web<br/>root directory frontend/"]
    end

    repo --> actions
    secrets -.->|"read by workflows"| actions
    actions -->|"pull → capture → emit → upload"| ds
    actions -->|"analytics run --upload"| derived
    actions -.->|"deploy hook"| api
    repo -->|"render.yaml"| api
    repo -->|"push"| web
    api -->|"serving bundle (read token)"| derived
    web -->|"NEXT_PUBLIC_API_URL"| api
```

- **Secrets** live in GitHub (`HF_TOKEN` with write scope for the workflows,
  `RENDER_DEPLOY_HOOK_URL`) and in Render (a read-only `HF_TOKEN`); never in
  the repository.
- **API** (Render): the image is built from `backend/Dockerfile` with context
  `backend/`; at start it downloads only the run's `serving/` bundle so it fits
  a 512 MB instance.
- **Web app** (Vercel): Next.js with root directory `frontend/`; it calls the
  API through `NEXT_PUBLIC_API_URL`.
- The local machine is optional: it runs the same CLI manually
  (`scripts/capture.sh`), the demo run and the test suite.

---

## Data flow and scheduled capture

```mermaid
flowchart TB
    start(["cron fires"]) --> pull["sextante.ingestion pull<br/>restore store(s) from HF<br/>write data/_published.json baseline"]
    pull --> which{"which workflow?"}

    which -->|"30 min"| js["capture --source jobspy<br/>general search per active site<br/>→ append, dedupe by url"]
    which -->|"12h"| sp["capture --source spe<br/>official CSV export → append,<br/>dedupe by vacancy_id"]

    js --> emitj["emit --dataset jobspy<br/>data/jobspy/day-YYYY-MM-DD.parquet"]
    sp --> emits["emit --dataset spe<br/>data/spe/week-YYYY-Www.parquet"]

    emitj --> up["upload: current day file<br/>+ static card; closed files skipped"]
    emits --> up

    up --> estado["estado.json: rows,<br/>rows_new, latest_capture"]
    estado --> summary["Actions run summary<br/>warns on zero growth"]
    summary --> finished(["done"])

    classDef warn fill:#d9534f,color:#fff;
    class summary warn;
```

Failure behavior:

- `sextante.ingestion capture` exits with code 1 if a source fails (a restored store
  would otherwise make the run *look* healthy while the corpus stopped
  growing).
- `sextante.ingestion emit` refuses to run when the store is missing (emitting an
  empty store would publish an empty dataset).
- `rows_new` is `null` when there was no pull baseline — growth is never
  invented from the total.

---

## Data layers

The medallion view (landing → bronze → silver → gold), the canonical schema,
the Hugging Face and local layouts and their invariants live in
[data.md](data.md). The techniques that move data between layers are in
[techniques.md](techniques.md).

---

## Sequence: JobSpy capture

```mermaid
sequenceDiagram
    participant cron as GitHub Actions
    participant hf as Hugging Face
    participant p as sextante.ingestion
    participant jb as Job boards

    cron->>p: pull --dataset jobspy
    p->>hf: list data/jobspy/*.parquet
    hf-->>p: partition files
    p->>hf: download partitions
    hf-->>p: parquet bytes
    p->>p: rebuild data/store/jobspy.parquet<br/>+ write baseline data/_published.json

    cron->>p: capture --source jobspy
    loop each active site (linkedin, indeed, bayt)
        p->>jb: scrape_jobs(site, location=Colombia,<br/>search_term=None, fetch_description=True)
        jb-->>p: jobs DataFrame
    end
    p->>p: map to canonical schema<br/>append, dedupe by url (keep first)

    cron->>p: emit --dataset jobspy --upload
    p->>p: partition by captured_at day<br/>_stable(): types + (vacancy_id, url) order
    p->>hf: upload_folder(data/jobspy/*, README.md)<br/>skips unchanged (byte-identical) files
    p->>p: estado.json (rows, rows_new)
    p-->>cron: exit 0 / 1
```

## Sequence: SPE export

```mermaid
sequenceDiagram
    participant cron as GitHub Actions
    participant p as sextante.ingestion
    participant spe as SPE API /backbue/v1
    participant hf as Hugging Face

    cron->>p: pull --dataset spe
    p->>hf: download data/spe/week-*.parquet
    hf-->>p: partitions (rebuild store + baseline)

    cron->>p: capture --source spe
    p->>spe: POST /vacantes/export/csv/async
    spe-->>p: {jobId} (202)
    loop up to ~5 min
        p->>spe: GET .../status
        spe-->>p: processing / completed
    end
    p->>spe: GET .../download
    spe-->>p: CSV (~415 MB)
    p->>p: map to canonical schema<br/>append, dedupe by vacancy_id

    cron->>p: emit --dataset spe --upload
    p->>p: partition by captured_at ISO week
    p->>hf: upload current week file only
    p-->>cron: exit 0 / 1
```

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
