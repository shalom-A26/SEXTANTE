"""JobSpy source: job boards for Colombia through the ``python-jobspy`` engine.

Runs one *general* search per site (no search term, ``location="Colombia"``)
so every hour returns the freshest top-N of each board, then maps JobSpy's
DataFrame to the canonical schema.

Site viability for Colombia (probe run 2026-10-05, see
``docs/source-viability.md``):

- **linkedin**  — works; needs ``fetch_description=True`` for full text.
- **indeed**    — works with ``country_indeed="colombia"`` (403 without it in
  earlier probes was a different code path; it works today).
- **bayt**      — works; returns rows located in Colombia.
- **glassdoor** — not available for Colombia (JobSpy raises).
- **google**    — returns no data for this location.
- **zip_recruiter** — 403.
- **naukri / bdjobs** — ignore the location filter (India / Bangladesh rows).

The site list below is the outcome of that probe; ``pipeline probe``
re-runs it on demand.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

from .. import env
from ..schema import normalize

# Sites confirmed working for Colombia (docs/source-viability.md).
ACTIVE_SITES = ["linkedin", "indeed", "bayt"]

# Everything JobSpy exposes, for `pipeline probe`.
ALL_SITES = ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter", "bayt", "naukri", "bdjobs"]

# JobSpy job_type -> canonical contract label (data values, kept in Spanish
# because the postings are Colombian).
CONTRACT_TYPES = {
    "fulltime": "Tiempo completo",
    "parttime": "Medio tiempo",
    "contract": "Contrato temporal",
    "internship": "Prácticas",
    "temporary": "Contrato temporal",
    "part-time": "Medio tiempo",
    "full-time": "Tiempo completo",
}


def _id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    base = path.rstrip("/").rsplit("/", 1)[-1]
    return base or None


def _split_location(loc: str | None) -> tuple[str | None, str | None]:
    """'Ciudad, Departamento, Colombia' -> (city, department)."""
    if not loc:
        return None, None
    parts = [s.strip() for s in loc.split(",") if s.strip()]
    if not parts:
        return None, None
    city = parts[0] or None
    department = parts[1] if len(parts) >= 3 else None
    if department and department.lower() == "colombia":
        department = None
    return city, department


def _salary_text(min_amount, max_amount, currency, interval) -> str | None:
    if pd.isna(min_amount) and pd.isna(max_amount):
        return None
    text = ""
    if currency and not pd.isna(currency):
        text += f"{currency} "
    if not pd.isna(min_amount) and not pd.isna(max_amount):
        text += f"{min_amount:,.0f} - {max_amount:,.0f}"
    elif not pd.isna(min_amount):
        text += f"desde {min_amount:,.0f}"
    elif not pd.isna(max_amount):
        text += f"hasta {max_amount:,.0f}"
    if interval and not pd.isna(interval):
        text += f" ({interval})"
    return text or None


def to_canonical(raw: pd.DataFrame) -> pd.DataFrame:
    """Map a JobSpy DataFrame to the canonical schema."""
    if len(raw) == 0:
        return normalize(pd.DataFrame())

    out = pd.DataFrame()
    out["vacancy_id"] = raw["job_url"].map(_id_from_url)
    out["source"] = raw["site"].astype(str)
    out["url"] = raw["job_url"]
    out["title"] = raw["title"]
    out["company"] = raw["company"]

    split = raw["location"].map(_split_location)
    out["city"] = [s[0] for s in split]
    out["department"] = [s[1] for s in split]

    out["published_at"] = raw["date_posted"].astype(str).replace("NaT", None)
    out["description"] = raw.get("description")

    out["salary_text"] = [
        _salary_text(r.min_amount, r.max_amount, r.currency, r.interval)
        for _, r in raw.iterrows()
    ]
    out["salary_min"] = raw.get("min_amount")
    out["salary_max"] = raw.get("max_amount")

    out["contract_type"] = raw.get("job_type").map(CONTRACT_TYPES) if "job_type" in raw else None
    is_remote = raw.get("is_remote")
    out["work_modality"] = is_remote.apply(lambda v: "Remoto" if v is True else None) if is_remote is not None else None
    out["education_level"] = None
    out["experience_text"] = None
    out["captured_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return normalize(out)


def scrape(
    sites: list[str] | None = None,
    results: int = 100,
    location: str = "Colombia",
) -> pd.DataFrame:
    """General (term-less) search on each site; canonical DataFrame out.

    A site that fails is reported and skipped — the run only fails if *every*
    site fails, so one flaky board doesn't redden the hourly capture while
    the others keep feeding the corpus.
    """
    from jobspy import scrape_jobs  # deferred: JobSpy is only needed at capture time

    sites = sites or ACTIVE_SITES
    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    for site in sites:
        try:
            raw = scrape_jobs(
                site_name=[site],
                search_term=None,
                location=location,
                results_wanted=results,
                country_indeed="colombia",
                fetch_description=True,
                user_agent=env.USER_AGENT,
                verbose=0,
            )
        except Exception as exc:  # noqa: BLE001 — a dead board must not kill the run
            print(f"  [jobspy] {site} failed: {type(exc).__name__}: {exc}")
            failures.append(site)
            continue
        n = len(raw)
        print(f"  [jobspy] {site}: {n} rows")
        if n:
            frames.append(to_canonical(raw))

    if not frames and failures and len(failures) == len(sites):
        raise RuntimeError(f"all JobSpy sites failed: {', '.join(failures)}")

    return normalize(pd.concat(frames, ignore_index=True)) if frames else normalize(pd.DataFrame())
