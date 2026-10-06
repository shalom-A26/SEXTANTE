# Source viability study

> [README](../README.md) · [Architecture](architecture.md)

Which sources can actually feed the pipeline for Colombia, and why the active
list is what it is. Last full probe: **2026-10-05** (`python -m pipeline probe`,
`python-jobspy==1.2.0`).

## Summary

| Source | Status | Evidence |
|---|---|---|
| **SPE** (`buscadordeempleo.gov.co`) | ✅ active | Official mass export via `/backbue/v1` async job: ~285k vacancies/capture, full text, education, salary band, contract type, experience, 2021→today. 3 HTTP requests per capture. |
| **LinkedIn** (JobSpy) | ✅ active | General search `location=Colombia` returns Colombian postings (Bogotá, Medellín, Cartagena, Barranquilla…); 8/8 rows with full descriptions when `fetch_description=True` (~7.6 s for 8 rows). |
| **Indeed** (JobSpy) | ✅ active | 8/8 rows in Colombian cities (Medellín, Cali, Bogotá, Usaquén…) with descriptions, with `country_indeed="colombia"`. Probes in 2026-02 returned 403; it works again as of 2026-10-05. |
| **Bayt** (JobSpy) | ✅ active | 8/8 rows with `location=Colombia` (regional board with Colombian listings). |
| **Glassdoor** (JobSpy) | ❌ discarded | JobSpy raises `Glassdoor is not available for COLOMBIA` (country tuple lacks COLOMBIA). Also Cloudflare-protected. |
| **Google** (JobSpy) | ❌ discarded | `Google returned no job data` for `location=Colombia`. |
| **ZipRecruiter** (JobSpy) | ❌ discarded | HTTP 403 on every attempt. |
| **Naukri** (JobSpy) | ❌ discarded | Ignores the Colombia filter: returns India rows (`Colombia, India` is a locality there). |
| **BDJobs** (JobSpy) | ❌ discarded | Ignores the Colombia filter: 8/8 rows in Bangladesh (Dhaka, Gazipur…). |
| **El Empleo** (`elempleo.com`) | ❌ removed (2026-10-05) | Custom scraper; replaced by JobSpy boards in the refactor. Historic rows (2,603, with LinkedIn) were migrated into `data/spe/` as legacy corpus. |

## Probe method

```bash
python -m pipeline probe                     # all known sites, location=Colombia
python -m pipeline probe --sites linkedin,indeed
```

For each site the probe runs a **general search** (no `search_term`,
`location="Colombia"`, `results=8`, `fetch_description=True`) and reports row
count, whether descriptions came back, and a title sample. A site is *viable*
only if it returns rows **located in Colombia** — some boards answer with rows
that ignore the location filter entirely (Naukri, BDJobs), which would poison
the corpus with non-Colombian postings.

### Latest results (2026-10-05, JobSpy 1.2.0)

| Site | Rows | Descriptions | Locations returned | Verdict |
|---|---|---|---|---|
| linkedin | 8 | 8/8 (full text, ~2.5–3.8k chars) | Cartagena, Medellín, Barranquilla, Cauca/Sucre, Colombia | ✅ |
| indeed | 8 | 8/8 | Medellín, Cali, Bogotá, Usaquén (CO) | ✅ |
| bayt | 8 | 0/8 (listing-level text) | Colombia ×8 | ✅ |
| naukri | 2 | 0/2 | `Colombia, India` (locality in India) | ❌ location ignored |
| bdjobs | 8 | 0/8 | Dhaka, Gazipur, Bangladesh ×8 | ❌ location ignored |
| glassdoor | 0 | — | error: `Glassdoor is not available for COLOMBIA` | ❌ |
| google | 0 | — | error: `Google returned no job data` | ❌ |
| zip_recruiter | 0 | — | error: HTTP 403 | ❌ |

Site availability is not permanent (Indeed went 403 → working again). The
active list lives in `pipeline/sources/jobspy_source.py::ACTIVE_SITES` and
should be re-validated with `pipeline probe` whenever captures start
returning zero rows.

## SPE: the export API

The public search exposes a REST API under `/backbue/v1` that generates a CSV
export of **all** registered vacancies through an asynchronous job — the same
"CSV (export all vacancies)" button of the web UI:

1. `POST /vacantes/export/csv/async` → `{jobId}` (202 queued)
2. `GET  .../{jobId}/status` → polling until `completed`
3. `GET  .../{jobId}/download` → CSV (~415 MB, UTF-8 BOM)

Observed: ~285k vacancies with complete description, education level,
department, salary band, contract type and experience in months.

Caveats handled in `pipeline/sources/spe.py`:

- The CA chain is incomplete → TLS validation fails systematically; the first
  `SSLError` disables verification for the rest of the run (see
  `_VERIFY_SSL`).
- The export takes up to ~5 minutes of polling at 2 s intervals.
- Download is throttled by nature: 3 requests + status polls per capture,
  twice a day.

## Why JobSpy over direct scraping

- LinkedIn, Indeed and Bayt are behind anti-bot measures (Cloudflare, 403s);
  JobSpy maintains the adapters and their fixes.
- One dependency with a single `scrape_jobs()` interface → one mapping
  function to the canonical schema instead of one scraper per portal.
- Ethical posture is preserved: our identifiable User-Agent is passed
  through (`user_agent=`), searches are general and throttled, and we only
  read what the boards publish without login.

## What was rejected and why (history)

- **Computrabajo**: 403 on list pages for anonymous clients (2026-02 probe).
- **El Empleo**: custom HTML+JSON scraper, brittle to redesigns; superseded by
  JobSpy in the 2026-10-05 refactor.
- **Direct LinkedIn scraping** without JobSpy: would violate our own
  no-block-evasion rule (rotating headers/fingerprints); not acceptable.

## Re-probing

Run `python -m pipeline probe` and update this table. If a site changes its
verdict, update `ACTIVE_SITES` **and** the README's active-sources table in
the same commit.
