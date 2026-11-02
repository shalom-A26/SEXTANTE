"""Dashboard aggregates and CV-to-vacancy matching over a loaded run."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from sextante_analysis.supervised import estimate_salary, salary_target

from .data import RunData

GAP_MIN_SHARE = 0.15


def _clean(value: Any) -> Any:
    """JSON-safe scalars (NaN → None, numpy → Python)."""
    if isinstance(value, (np.floating, float)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{key: _clean(value) for key, value in row.items()}
            for row in frame.to_dict(orient="records")]


def _distribution(series: pd.Series, top: int = 8) -> list[dict[str, Any]]:
    counts = series.fillna("Sin dato").astype(str).value_counts()
    return [{"label": label, "count": int(count)} for label, count in counts.head(top).items()]


_TITLE_NOISE = re.compile(
    r"\s*(?:[-–—|/(:,!¡].*$|\b(?:con o sin|con|sin) experiencia\b.*$"
    r"|\b(?:junior|senior|sr|jr|i{1,3})\b\.?)",
    flags=re.IGNORECASE,
)


def clean_title(title: str) -> str:
    """'Asesor comercial call center - con o sin experiencia' -> 'Asesor comercial call center'."""
    text = _TITLE_NOISE.sub("", str(title or "")).strip()
    return text[:1].upper() + text[1:].lower() if text else ""


def segment_names(run: RunData) -> dict[int, str]:
    """Human label per segment: its most frequent cleaned posting title."""
    if run.segment_names is not None:
        return run.segment_names
    names = {}
    for segment, titles in run.postings.groupby("cluster_id")["title"]:
        common = titles.map(clean_title).replace("", pd.NA).dropna().value_counts()
        names[int(segment)] = str(common.index[0]) if len(common) else f"Segmento {segment}"
    run.segment_names = names
    return names


def _segment_top_skills(run: RunData, segment: int, top: int = 6) -> list[dict[str, Any]]:
    if run.segment_skills.empty:
        return []
    rows = run.segment_skills[run.segment_skills["cluster_id"] == segment].head(top)
    return [{"esco_uri": r.esco_uri, "skill": r.skill_label, "share": float(r.share),
             "lift": float(r.lift)} for r in rows.itertuples()]


def _salary_stats(values: pd.Series) -> dict[str, Any]:
    values = values.dropna()
    if values.empty:
        return {"median": None, "p25": None, "p75": None, "n": 0}
    return {"median": float(values.median()), "p25": float(values.quantile(0.25)),
            "p75": float(values.quantile(0.75)), "n": int(values.size)}


def dashboard(run: RunData) -> dict[str, Any]:
    if run.precomputed_dashboard is not None:
        return run.precomputed_dashboard
    postings = run.postings.copy()
    postings["salary"] = salary_target(postings)
    names = segment_names(run)
    terms = run.segment_profiles.set_index("cluster_id")["terms"].to_dict()

    segments = []
    for segment in run.segment_ids:
        members = postings[postings["cluster_id"] == segment]
        segments.append({
            "id": segment,
            "name": names.get(segment),
            "postings": int(len(members)),
            "terms": str(terms.get(segment, "")).split(" | ")[:8],
            "salary": _salary_stats(members["salary"]),
            "top_skills": _segment_top_skills(run, segment),
            "modality": _distribution(members["work_modality"], 4),
            "education": _distribution(members["education_level"], 5),
            "cities": _distribution(members["city"], 5),
        })

    # Skill demand by education level (academic-programs perspective).
    by_education: dict[str, Counter[str]] = {}
    for level, skills in zip(postings["education_level"].fillna("Sin dato"), run.posting_skills,
                             strict=True):
        by_education.setdefault(str(level), Counter()).update(skills)
    education_skills = [
        {"education": level, "postings": int((postings["education_level"].fillna("Sin dato")
                                               == level).sum()),
         "skills": [{"skill": run.skill_labels.get(uri, uri), "count": count}
                    for uri, count in counter.most_common(8)]}
        for level, counter in sorted(by_education.items(), key=lambda item: -sum(item[1].values()))
    ]

    total = len(postings)
    nodes = run.skill_nodes.head(60) if not run.skill_nodes.empty else run.skill_nodes
    kept = set(nodes.get("esco_uri", []))
    edges = run.skill_edges[
        run.skill_edges["source"].isin(kept) & run.skill_edges["target"].isin(kept)
    ] if not run.skill_edges.empty else run.skill_edges
    top_skills = run.skill_nodes.sort_values("postings", ascending=False).head(25)

    projection = run.projection
    if len(projection) > 1500:
        projection = projection.iloc[np.linspace(0, len(projection) - 1, 1500, dtype=int)]
    direct = run.transitions[run.transitions["steps"] == 1] if not run.transitions.empty \
        else run.transitions

    return {
        "run": {
            "run_id": run.manifest.get("run_id"),
            "created_at_utc": run.manifest.get("created_at_utc"),
            "corpus": run.manifest.get("source", {}).get("repo"),
            "revision": run.manifest.get("source", {}).get("revision"),
            "synthetic": run.manifest.get("source", {}).get("repo") == "synthetic-demo",
        },
        "overview": {
            "postings": total,
            "with_salary": int(postings["salary"].notna().sum()),
            "segments": len(run.segment_ids),
            "skills_detected": int(len(run.skill_labels)),
            "skill_mentions": run.manifest.get("results", {}).get("skill_mentions"),
            "duplicate_candidates": run.manifest.get("results", {}).get("duplicate_candidates"),
            "sources": _distribution(postings["source"]),
            "cities": _distribution(postings["city"], 10),
            "modality": _distribution(postings["work_modality"], 5),
            "contracts": _distribution(postings["contract_type"], 6),
            "education": _distribution(postings["education_level"], 6),
        },
        "segments": segments,
        "top_skills": [
            {"esco_uri": r.esco_uri, "skill": r.skill_label, "postings": int(r.postings),
             "share": float(r.postings) / total if total else 0.0,
             "community": int(r.community)}
            for r in top_skills.itertuples()
        ] if not top_skills.empty else [],
        "education_skills": education_skills,
        "salaries": {
            "overall": _salary_stats(postings["salary"]),
            "by_department": [
                {"department": dept, **_salary_stats(group)}
                for dept, group in postings.groupby(postings["department"].fillna("Sin dato"))[
                    "salary"] if group.notna().sum() >= 3
            ],
            "models": run.supervised,
        },
        "graph": {
            "metrics": run.graph_metrics,
            "nodes": _records(nodes[["esco_uri", "skill_label", "postings", "pagerank",
                                     "betweenness", "community"]]) if not nodes.empty else [],
            "edges": _records(edges) if not edges.empty else [],
            "segment_links": [
                {"from": int(r.from_segment), "to": int(r.to_segment),
                 "similarity": float(r.direct_similarity)}
                for r in direct.itertuples() if r.from_segment < r.to_segment
            ] if not direct.empty else [],
        },
        "projection": _records(projection[["component_1", "component_2", "cluster_id"]])
        if not projection.empty else [],
        "topics": _records(run.topics) if not run.topics.empty else [],
        "clustering_comparison": run.comparison,
    }


def _gaps(run: RunData, segment: int, have: set[str], top: int = 8) -> list[dict[str, Any]]:
    if run.segment_skills.empty:
        return []
    rows = run.segment_skills[
        (run.segment_skills["cluster_id"] == segment)
        & (run.segment_skills["share"] >= GAP_MIN_SHARE)
        & ~run.segment_skills["esco_uri"].isin(have)
    ].head(top)
    return [{"skill": r.skill_label, "esco_uri": r.esco_uri, "share": float(r.share)}
            for r in rows.itertuples()]


def _route(run: RunData, source: int, target: int) -> list[int]:
    if run.transitions.empty:
        return [source, target]
    row = run.transitions[(run.transitions["from_segment"] == source)
                          & (run.transitions["to_segment"] == target)]
    return [int(step) for step in row.iloc[0]["path"]] if len(row) else [source, target]


def match_cv(run: RunData, text: str, limit: int = 20,
             city: str | None = None, modality: str | None = None) -> dict[str, Any]:
    """Score a CV against every posting and segment; return matches + advice.

    ``match`` (0–100) = 50% text similarity (TF-IDF cosine, relative to the
    best posting for this CV) + 50% coverage of the posting's ESCO skills
    by the CV. Postings without detected skills use text similarity only.
    """
    vector = run.vectorizer.transform([text])
    cosine = np.asarray((run.matrix @ vector.T).todense()).ravel()
    cv_skills = {match["esco_uri"]: match["skill_label"] for match in run.matcher.match(text)}
    have = set(cv_skills)
    best = float(cosine.max()) if cosine.size else 0.0

    candidates = np.argsort(cosine)[::-1]
    postings = run.postings
    mask = np.ones(len(postings), dtype=bool)
    if city:
        mask &= postings["city"].fillna("").str.casefold().eq(city.casefold()).to_numpy()
    if modality:
        mask &= postings["work_modality"].fillna("").str.casefold().eq(
            modality.casefold()).to_numpy()
    candidates = [index for index in candidates[:2000] if mask[index]][:300]

    names = segment_names(run)
    scored = []
    for index in candidates:
        job_skills = run.posting_skills[index]
        text_score = float(cosine[index]) / best if best > 0 else 0.0
        coverage = len(job_skills & have) / len(job_skills) if job_skills else None
        score = text_score if coverage is None else 0.5 * text_score + 0.5 * coverage
        scored.append((score, index, text_score, coverage))
    scored.sort(key=lambda item: item[0], reverse=True)

    matches = []
    for score, index, text_score, coverage in scored[:limit]:
        row = postings.iloc[index]
        job_skills = run.posting_skills[index]
        matches.append({
            "vacancy_id": str(row["vacancy_id"]), "source": row["source"], "url": row["url"],
            "title": row.get("title"), "company": _clean(row.get("company")),
            "city": _clean(row.get("city")), "work_modality": _clean(row.get("work_modality")),
            "salary_min": _clean(row.get("salary_min")),
            "salary_max": _clean(row.get("salary_max")),
            "segment": int(row["cluster_id"]), "segment_name": names.get(int(row["cluster_id"])),
            "match": round(100 * score, 1),
            "text_similarity": round(100 * text_score, 1),
            "skill_coverage": None if coverage is None else round(100 * coverage, 1),
            "matched_skills": sorted(run.skill_labels.get(u, u) for u in job_skills & have),
            "missing_skills": sorted(run.skill_labels.get(u, u) for u in job_skills - have),
        })

    # Segment affinity: centroid cosine (relative) + share-weighted skill coverage.
    segment_cos = run.centroids @ np.asarray(vector.todense()).ravel()
    top_cos = float(segment_cos.max()) if segment_cos.size else 0.0
    affinities = []
    for position, segment in enumerate(run.segment_ids):
        profile = run.segment_skills[run.segment_skills["cluster_id"] == segment] \
            if not run.segment_skills.empty else pd.DataFrame(columns=["esco_uri", "share"])
        weight = float(profile["share"].sum())
        covered = float(profile[profile["esco_uri"].isin(have)]["share"].sum())
        coverage = covered / weight if weight else 0.0
        relative = float(segment_cos[position]) / top_cos if top_cos > 0 else 0.0
        affinities.append((0.5 * relative + 0.5 * coverage, segment, coverage))
    affinities.sort(reverse=True)
    current = affinities[0][1] if affinities else None
    salaries = None if run.segment_stats else salary_target(postings)

    def describe(affinity: float, segment: int, coverage: float) -> dict[str, Any]:
        if run.segment_stats:  # serving bundle: corpus-wide figures
            size = run.segment_stats[segment]["postings"]
            median = run.segment_stats[segment]["median_salary"]
        else:
            members = postings["cluster_id"] == segment
            size, median = int(members.sum()), _clean(salaries[members].median())
        return {
            "segment": segment, "name": names.get(segment),
            "affinity": round(100 * affinity, 1), "skill_coverage": round(100 * coverage, 1),
            "postings": size, "median_salary": median,
            "gaps": _gaps(run, segment, have),
        }

    niches = [describe(*item) for item in affinities[:3]]
    pivots = []
    if current is not None:
        for affinity, segment, coverage in affinities[1:]:
            if affinity < 0.5 * affinities[0][0]:
                continue
            item = describe(affinity, segment, coverage)
            item["route"] = [{"segment": s, "name": names.get(s)}
                             for s in _route(run, current, segment)]
            pivots.append(item)
        pivots = pivots[:3]

    salary = estimate_salary(run.salary_bundle, vector) if run.salary_bundle else None
    return {
        "cv_skills": sorted(cv_skills.values()),
        "current_segment": describe(*affinities[0]) if affinities else None,
        "matches": matches,
        "niches": niches,
        "pivots": pivots,
        "salary_estimate": salary,
        "method": "match = 50% similitud de texto TF-IDF (relativa a la mejor vacante) "
                  "+ 50% cobertura de habilidades ESCO de la vacante",
    }
