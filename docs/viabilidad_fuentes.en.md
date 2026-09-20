# Data source viability

> **🌐 English** · [Versión en español](viabilidad_fuentes.md)

Probe date: 2026-09-20.
Tools: `python-jobspy` 1.1.13, `requests` 2.x. Low-volume tests.

## Summary

| Source | Viable? | Detail | Pilot priority |
| --- | --- | --- | --- |
| **SPE – official export** (`buscadordeempleo.gov.co`) | ✔ Yes | Full vacancy CSV export via API `/backbue/v1` (official async job). ~285k rows/capture; canonical store accumulated to 246.5k unique; ~100% coverage of key fields. | 1 |
| **LinkedIn** (via JobSpy) | ✔ Yes | Listing + full description. 10/10 in test. | 2 |
| **El Empleo** (`elempleo.com.co`) | ✔ Yes | Public HTML listing + JSON-LD `JobPosting` detail. 20 unique offers per SEO page. | 3 |
| **Computrabajo** | ✘ No | `robots.txt` and page respond 403. Aggressive blocking (Cloudflare). Not viable without evasion. | — |
| **Indeed** (via JobSpy) | ✘ No | `IndeedException: bad response with status code: 403`. | — |
| **Glassdoor** (via JobSpy) | ✘ No | `KeyError: 'GLASSDOOR'`. | — |

## Detail per source

### 1. SPE – official export (`buscadordeempleo.gov.co`) — master source

The SPE vacancy search is a SPA at `https://www.buscadordeempleo.gov.co/` consuming a REST API at `https://www.buscadordeempleo.gov.co/backbue/v1`.

Probe findings (2026-09-20):

- The page is **not** scraping: the portal offers its own bulk export (the *"CSV (Se exportan todas las vacantes)"* button in the web UI). The flow uses an async job:
  1. `POST /vacantes/export/csv/async` → `{jobId}` (202 queued).
  2. `GET  /vacantes/export/csv/async/{jobId}/status` → `processing` → `completed`.
  3. `GET  /vacantes/export/csv/async/{jobId}/download` → CSV (~415 MB, UTF-8 with BOM).
- Result (2026-09-20): the first probe returned **284,958 rows** in the CSV → **196,783 unique vacancies** by `CODIGO_VACANTE` (the export contains duplicated rows of the same code; they are deduplicated). Later captures added new codes: the canonical store now accumulates **246,551 unique** (2026-09-20).
- **100% coverage** in the 20,000 sampled vacancies (and `100%` globally): `TITULO_VACANTE`, `DESCRIPCION_VACANTE`, `NIVEL_ESTUDIOS`, `RANGO_SALARIAL`, `DEPARTAMENTO`, `MUNICIPIO`, `TIPO_CONTRATO`, `NOMBRE_PRESTADOR`, `FECHA_PUBLICACION`, `MESES_EXPERIENCIA_CARGO`, `TELETRABAJO`, `SECTOR_ECONOMICO`, `URL_DETALLE_VACANTE`.
- History: publications from **2021-06-25** up to the capture date (continuous updates; `max_date` via `GET /vacantes/date`).
- License: vacancy data from the state public employment service, published by the government; it contains no personal candidate data. Considered legitimate and ethical use (official source = legitimacy floor).
- Numeric salary: `RANGO_SALARIAL` is a **bucket** (e.g. `$1.500.001 - $2.000.000`, `A Convenir`, `Mayor de $15.000.001`). The SPE module converts it to `salario_min`/`salario_max` (~78% numeric).
- `URL_DETALLE_VACANTE` points to the original offer (computrabajo ~192k, elempleo ~36k, SPE ~30k, magneto ~21k, etc.) — SPE aggregates vacancies from many portals.
- Ethics note: downloaded via the portal's official export mechanism (3 HTTP requests per full capture), no evasion. The portal has an intermittent TLS certificate; `spe.py` retries with `verify=False` **only** after an SSL validation failure (public, read-only state site).

Implementation: `src/extraccion/portales/spe.py`, orchestrated with `python -m src.extraccion.corpus --fuentes spe`. Storage: `data/raw/spe/vacantes_spe.parquet` (dedupe by `id_vacante`, not by `url`).

### 2. LinkedIn via JobSpy (`pip install python-jobspy`)

JobSpy aggregates vacancies from several portals into a single normalised `DataFrame`.

- Installed: `python-jobspy` 1.1.13 (Python ≥ 3.10).
- Test: `scrape_jobs(site_name=["linkedin"], search_term="analista", location="Colombia", results_wanted=10)` → **10 rows, 9 with full description**.
- `DataFrame` columns: `job_url`, `site`, `title`, `company`, `location`, `job_type`, `date_posted`, `interval`, `min_amount`, `max_amount`, `currency`, `is_remote`, `num_urgent_words`, `benefits`, `emails`, `description`.
- Notes:
  - The installed version's API does **not** accept `hours_old`, `linkedin_fetch_description` or `description_format` (version signature).
  - LinkedIn searches globally: with `location="Colombia"`, global remote offers executable from Colombia may appear.
  - Indeed → 403. Glassdoor → KeyError. Discarded in the JobSpy engine.

### 3. El Empleo (`elempleo.com/co/`)

- `robots.txt` accessible and permissive (only blocks admin/private paths → `Disallow: */Admin/`, `*/Management/`, etc.).
- Public listing: `https://www.elempleo.com/co/ofertas-empleo/` plus SEO variants by city or job:
  - `.../co/ofertas-empleo/bogota`, `.../medellin`, `.../trabajo-analista`, etc.
  - Each page contains **20 unique offers** (numeric id at the end of `/co/ofertas-trabajo/<slug>-<id>`).
- Listing cards: `data-url` attribute (offer link) and `data-ga4-offerdata` (JSON with `id`, `title`, `company`, `location`, `salary` as text).
- Offer detail: `JSON-LD application/ld+json` block of type `JobPosting` with:
  - `title`, `description`, `datePosted`, `validThrough`
  - `employmentType` (`CONTRACTOR`, `FULL_TIME`, ...)
  - `hiringOrganization.name`
  - `baseSalary`: `currency=COP`, `minValue`, `maxValue`, `unitText=MONTH`
  - `jobLocationType` (`TELECOMMUTE`, ...)
  - `jobLocation.address` (usually country `CO` only; the city comes from the listing card).
- Web API (`/co/api/joboffers/findbyfilter`) returns `401 Authorization has been denied` → **not used** (avoid evasion/fragile auth).

### 4. Computrabajo — discarded

- Both `robots.txt` data and the page respond 403.
- Home and listings are blocked too. The provider blocks non-browser clients.
- For a project with data ethics as a cross-cutting axis, discarded (no evasion techniques will be used).

### 5. SPE – open data on datos.gov.co — discarded as a path

- `serviciodeempleo.gov.co/transparencia-e-informacion/.../publicacion-de-datos-abiertos` links to the Socrata catalogue of `datos.gov.co` for the entity "Servicio Publico de Empleo".
- The Socrata catalogue of datos.gov.co does **not** contain a vacancy dataset with free description (only Medellín OPE attendance/linked records and unemployment aggregates).
- Conclusion: the correct path for SPE is the **official export of `buscadordeempleo.gov.co`** (see section 1), not datos.gov.co.

## Adopted ethical criteria (course cross-cutting axis)

1. **Respect `robots.txt`** and each portal's terms of use.
2. **Do not** use personal logins/cookies, proxies or block-evasion techniques.
3. **Control volume** with throttling (pause between requests) to avoid affecting the portals.
4. **Identifiable `User-Agent`** with the project: `SEXTANTE-UTB-university-research/1.0 (...)`.
5. Use the **official source (SPE)** as the dataset's legitimacy floor whenever available.
6. **Do not collect personal candidate data**; only public offer information.
7. Document the provenance of each record in the `portal` + `url` fields.

## Pilot decision

Build the extraction engine with **SPE (official export)** as the volume master source (big corpus in parquet), plus **JobSpy → LinkedIn** (fast, normalised DataFrame, full descriptions) and **El Empleo** (HTML + JSON-LD, open robots, no login), all normalised to the 17-column canonical schema defined in `src/extraccion/esquema.py`.