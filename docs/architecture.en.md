# SEXTANTE Architecture

> [Spanish](arquitectura.md) · [English](architecture.en.md) · [README](../README.en.md)

C4 model of the platform (context, containers, components and deployment), main data flows, capture sequences and data model. All diagrams are written in **Mermaid** so they render in docs, editors and GitHub.

## Contents

1. [Overview](#overview)
2. [C4 model](#c4-model)
   - [Level 1 · Context](#level-1--context)
   - [Level 2 · Containers](#level-2--containers)
   - [Level 3 · Components](#level-3--components)
   - [Level 4 · Deployment](#level-4--deployment)
3. [Data flow and periodic capture](#data-flow-and-periodic-capture)
4. [Sequence: SPE asynchronous export](#sequence-spe-asynchronous-export)
5. [Data model](#data-model)
6. [Design decisions](#design-decisions)

---

## Overview

SEXTANTE is an ETL/ELT pipeline for Colombian job vacancies:

1. **Extracts** from three sources: the official SPE export (massive, ~285k rows/capture), El Empleo (HTML + JSON-LD) and LinkedIn (JobSpy).
2. **Normalises** everything to the **17-column canonical schema** (`src/extraccion/esquema.py`, `normalizar()` / `validar()`).
3. **Stores** into two **append-only** stores: canonical big corpus in parquet (SPE) and curated corpus in CSV (El Empleo + LinkedIn). A vacancy already seen is never rewritten; `fecha_captura` stays pinned to the first observation.
4. **Persistent memory = Hugging Face**: `sync_hf.py` rebuilds the local stores from the published files (`data/semana-*.parquet`) before each run; `emitir_dataset.py` publishes them again.
5. **Capture is automatic every 6 hours** on **GitHub Actions** (`.github/workflows/captura_6h.yml`); the local cron is disabled and `scripts/capturar_6h.sh` remains for manual development use.

Current state: **322,313 vacancies** (319,765 SPE + 2,548 curated) in the private HF dataset `pxtron/vacantes-colombia`, published as weekly parquet files; active workflow `0 5,11,17,23 * * *` UTC (= 00/06/12/18 Colombia time). There is no local database: the analytics layer reads from HF.

**Why weekly.** The previous layout published the corpus twice (`store/` folder plus `train-*-of-*` shards) and never deleted the shards of previous generations: 650 MB of content with 283 MB dead (44 %) and ~1.32 GB of upload per day. With the weekly layout, each vacancy lives in the file for the week it was first seen; because rows are frozen, files for closed weeks are **immutable** and `upload_folder` skips them (their content is already in the repo). Each run uploads only the current week's file: **~14 MB per run on average**, **~58 MB/day** against the previous layout's ~1.32 GB/day (~23× less). The migration executed on 2026-10-04 left the repo at **166 MB of content** (650 MB before) with the same 322,313 vacancies. `used_storage` (~19 GB, mostly history HF does not release) does not shrink when files are deleted: what stops is the growth.

Week W40 is the transitional exception: it holds the legacy backfill (277,864 of the 322,313 rows fall into it, because earlier rows inherit `fecha_captura` from their last observation), so its file weighs 143 MB and every run until Monday the 5th rewrites it whole. From W41 on, the current week's file starts empty and the cost returns to ~14 MB per run.

---

## C4 model

### Level 1 · Context

Who uses the system and the external systems it interacts with.

```mermaid
flowchart LR
    u["UTB team<br/>Analytics and Data Mining"]
    s{{"SEXTANTE<br/>Colombian labour-market<br/>analytics"}}
    spe["SPE · Job Search<br/>buscadordeempleo.gov.co<br/>API /backbue/v1"]
    ee["El Empleo<br/>elempleo.com"]
    li["LinkedIn<br/>via JobSpy"]
    hf["Hugging Face Hub<br/>pxtron/vacantes-colombia (private)"]

    u -->|configures, runs, queries| s
    s -->|"official CSV export (3 requests/capture)"| spe
    s -->|"public listings + JSON-LD detail"| ee
    s -->|"term searches"| li
    s -->|"weekly files data/semana-*.parquet (append-only)"| hf
    s -.->|"only public offer information"| u

    classDef sist fill:#1168bd,color:#fff,stroke:#0b4884;
    classDef ext fill:#999999,color:#fff,stroke:#6b6b6b;
    class s sist;
    class spe,ee,li,hf ext;
```

- **UTB team**: configures and runs the workflow (Repo Actions) and queries results (CLI + validation notebook + HF dataset).
- **SPE**: external state system from which the full export is downloaded (official mechanism, no scraping).
- **El Empleo** and **LinkedIn**: portals scraped under ethical criteria (throttling, identifiable UA, robots.txt).
- **Hugging Face Hub**: the pipeline's persistent memory and the dataset publishing target (private, academic).

### Level 2 · Containers

Decomposition of the system into executable and storage containers.

```mermaid
flowchart TB
    subgraph RUNNER["GitHub Actions · Ubuntu runner (ephemeral, per run)"]
        wf["Workflow captura_6h.yml"]
        sync["sync_hf.py<br/>--pull rebuilds the stores"]
        corpus["corpus.py<br/>collection orchestrator"]
        emit["emitir_dataset.py<br/>weekly HF emission"]

        subgraph EPHEMERAL["data/ on the runner (discarded when done)"]
            storespe[("parquet<br/>data/raw/spe/vacantes_spe.parquet")]
            storecu[("CSV<br/>data/raw/vacantes.csv")]
            emitd[("dataset dir<br/>data/emitido/vacantes-colombia/<br/>data/semana-*.parquet")]
        end
    end

    subgraph LOCAL["UTB machine (manual development)"]
        shdev["scripts/capturar_6h.sh"]
        edacli["Local CLI<br/>.venv + notebooks"]
        notebook["Jupyter · eda_validacion.ipynb"]
    end

    spe["SPE /backbue/v1"]
    ee["El Empleo"]
    li["LinkedIn (JobSpy)"]
    hub["HF Hub (persistent)<br/>data/semana-*.parquet"]

    wf --> sync
    sync --> hub
    wf --> corpus
    corpus -->|"POST /export/csv/async + POLL + GET download"| spe
    corpus -->|"GET listings + JSON-LD detail"| ee
    corpus -->|"scrape_jobs(...)"| li
    corpus --> storespe
    corpus --> storecu
    wf --> emit
    emit --> storespe
    emit --> storecu
    emit --> emitd
    emitd -->|"--hf-upload (HF_TOKEN) · current week only"| hub
    shdev -.->|"same logic locally"| corpus
    notebook --> hub
    notebook --> storespe
    notebook --> storecu
    edacli -.->|"same logic locally"| sync
    edacli -.->|"same logic locally"| corpus
    edacli -.->|"same logic locally"| emit

    classDef cont fill:#1168bd,color:#fff,stroke:#0b4884;
    classDef almacen fill:#d9ead3,stroke:#6aa84f;
    classDef ext fill:#999999,color:#fff,stroke:#6b6b6b;
    class wf,sync,corpus,emit,shdev,notebook cont;
    class storespe,storecu,emitd almacen;
    class spe,ee,li,hub ext;
```

- **corpus.py**: orchestrates sources, applies `normalizar()`, saves with append-only dedupe and, in manual mode, snapshots. Exits with code 1 if a requested source fails.
- **sync_hf.py**: the gateway to persistent memory — rebuilds `data/raw/spe/vacantes_spe.parquet` and `data/raw/vacantes.csv` from the published `data/semana-*.parquet` (with a fallback to the `store/` layout for datasets not yet migrated) and leaves `data/raw/_publicado.json` with the previous run's counts.
- **emitir_dataset.py**: consolidates both stores, groups them by `fecha_captura` week and generates the HF directory (`data/semana-*.parquet` + dataset card + `estado.json`), which `--hf-upload` publishes skipping what is already in the repo.
- **Hugging Face as the only analytics storage**: there is no local database. `src/analisis/datos_hf.py` reads the parquet files read-only and records the resolved revision.
- **Jupyter**: EDA validating schema and coverage.

### Level 3 · Components

Internal components of the extraction/emission container.

```mermaid
flowchart LR
    subgraph SRC["src/extraccion/"]
        schema["esquema.py<br/>17-column contract"]
        base["base.py<br/>ethical HTTP + append-only save/snapshots"]
        corpus["corpus.py<br/>CLI orchestrator"]
        sync["sync_hf.py<br/>rebuilds stores from HF"]
        emitir["emitir_dataset.py<br/>HF dataset by week"]

        subgraph PORTALS["portales/"]
            spe["spe.py<br/>official export → parquet"]
            ele["elempleo.py<br/>HTML + JSON-LD"]
            lin["linkedin_jobspy.py<br/>JobSpy → schema"]
        end
    end

    corpus --> spe
    corpus --> ele
    corpus --> lin
    spe -->|"normalizar()"| schema
    ele -->|"normalizar()"| schema
    lin -->|"normalizar()"| schema
    base --> corpus
    sync --> base
    base --> emitir
    emitir --> schema
    emitir --> sync

    classDef borde fill:#f3f3f3,stroke:#999;
    classDef mod fill:#1168bd,color:#fff;
    class SRC borde;
    class schema,base,corpus,sync,emitir,spe,ele,lin mod;
```

Key component details:

- **spe.py** — drives the massive export: `descargar_export_csv()` (async job), `_parsear_salario()` (bucket → `salario_min`/`salario_max`), `exportar_a_canonico()` (`id_vacante = spe-<CODIGO_VACANTE>`), `guardar_parquet()` (append-only by `id_vacante`, `keep="first"`, returns how many rows are new). Includes retry for the portal's intermittent TLS (`verify=False` only after SSL failure, with a warning).
- **elempleo.py** — public SEO listings + JSON-LD `JobPosting` detail (`baseSalary`, `employmentType`, `jobLocationType`…).
- **linkedin_jobspy.py** — `scrape_jobs(site_name=["linkedin"], location="Colombia", ...)` per term; typically 10 searches × 25.
- **base.py** — session with `User-Agent: SEXTANTE-UTB-university-research/1.0`, request pauses, `guardar_lotes()` (append + dedupe `url`, never rewriting what was already seen), `guardar_snapshot()`.
- **esquema.py** — defines and validates the single output contract.
- **sync_hf.py** — `restaurar_stores()` splits what was published between the two stores by `almacen`; `descargar_estado()` picks the weekly layout or, if the repo has no weekly files yet, the inherited `store/`. It writes `data/raw/_publicado.json` so the emission can measure real growth.
- **emitir_dataset.py** — `consolidar()` merges SPE+curated and adds `almacen`; `particionar_por_semana()` groups by `fecha_captura`; `_salida_estable()` fixes dtypes and row order so identical content yields identical bytes (and `upload_folder` skips the file); it generates the dataset card, `estado.json` and, on `--hf-upload`, migrates the previous layout **only if the corpus is known to have been restored**.

### Level 4 · Deployment

The capture pipeline runs on GitHub Actions infrastructure (ephemeral Ubuntu runner); the local machine is only for manual development/queries.

```mermaid
flowchart TB
    subgraph CLOUD["GitHub Actions · private repo shalom-A26/SEXTANTE"]
        subgraph WF["Workflow · captura_6h.yml (cron '0 5,11,17,23 * * *' UTC)"]
            checkout["checkout"]
            python["setup-python 3.12"]
            deps["pip install -r requirements.txt"]
            pull["python -m src.extraccion.sync_hf --pull"]
            spe["python -m src.extraccion.corpus --fuentes spe"]
            cur["python -m src.extraccion.corpus --fuentes linkedin elempleo"]
            emit["python -m src.extraccion.emitir_dataset --hf-upload"]
        end
        CFG["Config<br/>HF_TOKEN = repo secret"]
    end

    subgraph HUB["Hugging Face Hub"]
        dset["pxtron/vacantes-colombia (private)<br/>data/semana-*.parquet"]
    end

    subgraph PC["UTB machine (manual development)"]
        venv[".venv · scripts/capturar_6h.sh"]
        nb["Jupyter notebook"]
    end

    subgraph NET["Internet (HTTPS)"]
        speext["buscadordeempleo.gov.co /backbue/v1"]
        ee["elempleo.com"]
        li["linkedin.com"]
        hfapi["huggingface.co (datasets API)"]
    end

    checkout --> python --> deps --> pull
    pull --> spe --> cur --> emit
    CFG -.-> emit
    pull -->|"downloads data/semana-*.parquet"| hfapi
    emit -->|"uploads current week (--hf-upload)"| hfapi
    hfapi --> dset
    spe --> speext
    cur --> ee
    cur --> li
    venv --> speext
    venv --> ee
    venv --> li
    nb --> hfapi

    classDef nodo fill:#3d3d3d,color:#fff,stroke:#222;
    classDef ext fill:#999999,color:#fff;
    class CLOUD,HUB,PC nodo;
    class speext,ee,li,hfapi ext;
```

- Cadence: every 6 h (Colombia time 00/06/12/18) the runner re-captures the SPE export, appends the curated data and **republishes** the dataset into HF. The nominal cron is not honoured to the minute: measured across 20 runs in September–October 2026, deviations range from −3.4 h to +2.6 h with one ~8.8 h blind window. The average stays at ~4 captures per day, but not at the documented hours.
- The runner is ephemeral: all local writes under `data/` are discarded when the job ends; accumulation continuity is guaranteed by `sync_hf --pull` at the start.
- `HF_TOKEN` lives as a repository secret (never in code); the workflow only needs read permission for checkout.
- The local machine (user pxtron) can run `scripts/capturar_6h.sh` for manual development; its local stores are seeds/queries, not the primary memory.

---

## Data flow and periodic capture

A closed loop with HF as persistent memory:

```mermaid
flowchart LR
    hub["HF · data/semana-*.parquet"] -->|"sync_hf --pull on each run"| norm["normalizar()<br/>same 17-column schema"]
    sources["Sources (SPE / El Empleo / LinkedIn)"] -->|"raw rows (variable format)"| norm
    norm -->|"canonical append-only store"| stores["pair of stores<br/>data/raw/ + data/raw/spe/"]
    stores -->|"consolidar() + particionar_por_semana()"| emit["emitir_dataset.py"]
    emit --> hfdir["HF dataset dir<br/>data/semana-*.parquet + card"]
    hfdir -->|"--hf-upload · only what changed"| hub

    classDef d1 fill:#1168bd,color:#fff;
    classDef d2 fill:#d9ead3,stroke:#6aa84f;
    classDef d3 fill:#fff2cc,stroke:#bf9000;
    class sources,norm d1;
    class stores,hub d2;
    class emit,hfdir d3;
```

Growth and storage:

- The corpus grows with the **genuinely new** vacancies (dedupe by `CODIGO_VACANTE` for SPE and by `url` for curated); no purges.
- Growth on HF is bounded by the immutability of closed weeks: each vacancy is uploaded **once**, and only the current week's file is rewritten on each run.
- Cost: ~35 k new vacancies/week ≈ 3.3 MB of new data per day, but the upload is paid on the whole current week's file (~14 MB average per run, ~58 MB/day) against ~1.32 GB/day in the previous layout (~23× less). The already-accumulated history (18.5 GB) does not shrink — HF does not release it — but it stops growing.
- `data/raw/_publicado.json` holds the previous run's counts, which lets the workflow Summary tell "it grew" apart from "it contributed nothing" — the signal that exposes a dead source.
- Snapshots (`data/snapshots/`) remain as manual development/registry artefacts (the runner keeps no disk).

---

## Sequence: SPE asynchronous export

SPE does not expose a direct download endpoint: an export job is created and polled until `completed` (the portal's own official mechanism).

```mermaid
sequenceDiagram
    autonumber
    participant P as portales/spe.py
    participant API as SPE /backbue/v1
    participant JOB as Export job

    P->>API: POST /vacantes/export/csv/async
    API-->>P: 202 {jobId, status:"queued"}
    Note over P: base.py sets project User-Agent and pauses between requests
    loop until status = "completed"
        P->>API: GET /vacantes/export/csv/async/{jobId}/status
        API-->>P: processing … completed
    end
    P->>API: GET /vacantes/export/csv/async/{jobId}/download
    API-->>P: 200 CSV ~415 MB (UTF-8 with BOM)
    P->>P: exportar_a_canonico() → guardar_parquet()
```

Export result observed on 2026-10-04: **~285 k rows → 319,765 unique** rows accumulated in the store by `id_vacante` (the export includes duplicated rows of the same `CODIGO_VACANTE` dropped by `guardar_parquet()`).

---

## Data model

### Entity–relationship diagram

```mermaid
erDiagram
    VACANTE {
        text id_vacante PK "spe-<CODIGO_VACANTE>"
        text portal "spe | elempleo | linkedin"
        text url "original link"
        text titulo "job title"
        text empresa "provider/employer"
        text ciudad "municipality (SPE)"
        text departamento "native SPE"
        text fecha_publicacion "source format"
        text descripcion "free text → NLP"
        text salario_texto "source bucket"
        number salario_min "COP/month"
        number salario_max "COP/month"
        text tipo_contrato "native SPE"
        text modalidad "Teletrabajo if SPE TELETRABAJO=1"
        text nivel_educativo "native SPE"
        text experiencia_texto "N months (SPE)"
        text fecha_captura "%Y-%m-%d %H:%M:%S · first observation"
        text almacen "spe|curado (weekly file)"
    }
```

### Dictionary / coverage

| Column | Native in | SPE coverage | Notes |
| --- | --- | --- | --- |
| `id_vacante` | all | 100% | SPE: `spe-<CODIGO_VACANTE>` |
| `portal` | all | 100% | source label |
| `url` | all | 100% | SPE: `URL_DETALLE_VACANTE` |
| `titulo` | all | 100% | `TITULO_VACANTE` |
| `empresa` | SPE/ElEmpleo | ~100% | `NOMBRE_PRESTADOR` |
| `ciudad` | SPE/ElEmpleo | ~100% | `MUNICIPIO` |
| `departamento` | SPE | ~100% | was 0% before SPE |
| `fecha_publicacion` | all | ~100% | source format |
| `descripcion` | all | 100% | NLP basis |
| `salario_texto` | SPE/ElEmpleo | ~100% | SPE bucket |
| `salario_min`/`salario_max` | SPE | ~78% | derived from bucket |
| `tipo_contrato` | SPE/ElEmpleo | ~100% | SPE contract |
| `modalidad` | all | ~0.8% remote | SPE `TELETRABAJO=1` |
| `nivel_educativo` | SPE | ~100% | was 0% before |
| `experiencia_texto` | SPE | ~100% | `MESES_EXPERIENCIA_CARGO` |
| `fecha_captura` | all | 100% | stamp `%Y-%m-%d %H:%M:%S`; because stores are append-only it is the **first** time we saw the vacancy |
| `almacen` | emission | — | `spe`/`curado`; decides which local store each row returns to on `--pull` |

---

## Design decisions

| Topic | Decision | Reason |
| --- | --- | --- |
| Master source | SPE official export (API `/backbue/v1`) | State data, official mechanism, ~285k offers/capture, ~100% coverage of key fields. |
| Per-source dedupe | SPE by `id_vacante` (CODIGO_VACANTE); curated by `url` | Several distinct SPE vacancies share the provider's `url`; record-level precedence. |
| Store semantics | **append-only** (`keep="first"`): what was already seen is never rewritten | Pins `fecha_captura` to the first observation (making vacancy lifetime measurable), makes the store byte-reproducible, and is the precondition for immutable weekly files. Without it, an edited vacancy would force rewriting its week's file. |
| Schema | Single 17-column canonical schema (`esquema.py`) | Single output contract; `normalizar()` before saving, `validar()` in EDA. |
| Dataset partition | by **`fecha_captura` week**, not `fecha_publicacion` | Archiving a March vacancy when the export delivers it in October would force reopening and rewriting an already-published file. With `fecha_captura`, each file is written once. |
| Stable writes | dtypes and row order pinned in `_salida_estable()` | Identical content → identical bytes → `upload_folder` skips the file. Without it, the ~23× saving is lost to formatting noise. |
| Capture cadence | workflow `0 5,11,17,23 * * *` UTC (= 00/06/12/18 Colombia) | Balance between data freshness and load on the state portal; 4 daily captures (the scheduler does not honour the minute). |
| Persistent memory | HF = canonical store (`data/semana-*.parquet`) | The runner is ephemeral; `sync_hf --pull` rebuilds the stores from what was published before capturing, and `emitir_dataset` republishes afterwards. |
| Corpus retention | accumulation without purges (dedupe by genuinely new vacancy) | Real growth = new vacancies; with immutable weeks, uploading no longer costs the size of the corpus. |
| Visible failures | `corpus.py` exits with code 1 if a source fails; `estado.json` + Summary compare against what was published | Previously the store restored from HF made everything look healthy while the corpus stopped growing. |
| Layout migration | `store/` and `train-*` are deleted only if the corpus is known to have been restored (rows ≥ published) | A failed `--pull` would publish a tiny dataset; deleting the history is irreversible from code (recoverable only from HF's history). |
| HF upload | automatic on every run (`--hf-upload`, `HF_TOKEN` as secret) | The corpus must grow by itself; the token lives in the repo secret, not in code. |
| Concurrency | `concurrency: captura-periodica` (cancel-in-progress: false) | Avoids two simultaneous runs writing to HF at once. |
| Local cron | disabled (script kept for manual development) | Automatic operation belongs to GitHub Actions; the UTB machine stays free. |
| Snapshots | only on manual captures (canonical parquet, no raw CSV) | The raw export CSV is ~415 MB; parquet is enough as a reproducible cut. |
| SPE intermittent TLS | `verify=False` **only** after validation failure | Read-only state site; warned via `warnings`. |
| Publishing | **private** HF dataset `pxtron/vacantes-colombia` | Academic use; no public redistribution of third-party portal data. |
| Analytics storage | HF only (weekly parquet) | DuckDB was removed: it had been write-only since `898a7e3` and produced a ~200 MB binary under `data/duckdb/` that was not in `.gitignore`. `pyarrow`/`polars` read the parquet files serverlessly. |

Original document is in **[Spanish (arquitectura.md)](arquitectura.md)**; this English version is a translation.

---

## Analytics and job-title–skill graph layer

Analytics reads the private `pxtron/vacantes-colombia` `data/semana-*.parquet`
files.
`src/analisis/datos_hf.py` uses the Hugging Face cache and records the resolved
Analytics reads the private `pxtron/vacantes-colombia` `data/semana-*.parquet`
files. `src/analisis/datos_hf.py` uses the Hugging Face cache and records the
resolved commit; it neither invokes collectors nor changes stores. Since each
vacancy lives in a single file and rows are frozen, deduplication by
`id_vacante` is only a safety net.

`src/procesamiento/habilidades.py` extracts **endogenous vocabulary**: n-grams
from the descriptions themselves, filtered by frequency and an occupational
signal (Aho-Corasick), with no dependency on an external taxonomy.
`src/grafos/construir_grafo.py` emits nodes, edges, audit data, and a provenance
manifest. `metricas_grafo.py` provides TF-IDF cosine similarity, communities,
and exploratory proximity signals.

```mermaid
flowchart LR
    hf["Private HF<br/>data/semana-*.parquet"] --> access["datos_hf.py<br/>read + revision"]
    access --> dashboard["dashboard_metricas.ipynb"]
    access --> extractor["habilidades.py<br/>n-grams + occupational signal"]
    extractor --> builder["construir_grafo.py"]
    builder --> artifacts["nodes/edges/audit/manifest"]
    artifacts --> network["grafo_habilidades_ocupaciones.ipynb"]
```

The current volume does not justify Spark. It remains an option for millions
of texts or distributed NLP/embedding inference.

**Current findings (2026-10-04).** Occupational mapping is the bottleneck:
195,175 normalised job titles of which 157,172 appear only once, and with
`minimo_ocupacion=5` only 6,763 occupations remain over 90,015 vacancies. Node
degree does not help prioritise skills — its top terms are contractual
conditions — while ranking by occupational signal does yield legible terms. The
network is connected (1 component).
