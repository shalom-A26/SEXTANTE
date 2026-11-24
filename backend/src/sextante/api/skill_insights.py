"""Skill-level dashboard insights: kinds, pivots, pairs, salary, niches, communities, topics.

Pure functions over a loaded run. They need the full run (every posting with
its skills); the serving bundle never reaches them because its dashboard is
precomputed over the full run by ``serving.build_bundle``. Every figure is an
association between skills, segments and salary bands over postings, never a
causal effect. Skills are merged by normalized label and co-occurrence, salary,
niche, pivot and community figures use deduplicated postings
(``skill_cooccurrence.py``). Definitions and formulas: ``docs/techniques.md`` § 10.
"""

from __future__ import annotations

import re
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse

from sextante.analytics.supervised import BAND_EDGES, salary_band

from . import skill_cooccurrence as sc

# Skills table and "núcleo duro".
TABLE_SIZE = 30                      # most demanded skills in the table
CORE_SIZE = 10                       # highest PageRank skills
# Kind rule (top-segment share = share of the skill's deduped postings in its most common
# segment; breadth = segments where its lift is >= 1): especializada when the top-segment
# share is >= SPECIALIZED_MIN_SEGMENT_SHARE; transversal when breadth is >=
# TRANSVERSAL_MIN_SEGMENT_FRACTION of the segments; intermedia otherwise.
SPECIALIZED_MIN_SEGMENT_SHARE = 0.60
TRANSVERSAL_MIN_SEGMENT_FRACTION = 0.40
# Pivots between directly linked segments (share and lift = share in the segment / share
# in all deduped postings). Generic skills (``skill_cooccurrence.GENERIC_MIN_SHARE``)
# never appear. shared: share >= PIVOT_MIN_SHARE in both segments. missing: share >=
# PIVOT_MIN_SHARE and lift >= PIVOT_MIN_LIFT in the target, and origin share <=
# PIVOT_MISSING_MAX_RATIO x target share (a missing skill is never also shared).
PIVOT_MIN_SHARE = 0.05
PIVOT_MIN_LIFT = 1.5
PIVOT_MISSING_MAX_RATIO = 0.5
PIVOT_LIST_SIZE = 5
# Salary (deduped postings): "high" = band lower bound >= $2M ("$2M o más").
HIGH_SALARY_FLOOR = 2_000_000
HIGH_SALARY_BAND = BAND_EDGES.index(HIGH_SALARY_FLOOR) + 1
SALARY_MIN_POSTINGS = 100            # salaried postings a skill needs to be ranked
SALARY_LIST_SIZE = 8                 # rows in salary.top and salary.bottom
BOOST_ANCHOR_MIN_POSTINGS = 300      # salaried postings of an anchor skill
BOOST_MIN_COMBO = 150                # salaried postings asking for anchor + complement
BOOST_MIN_GAIN = 0.05                # minimum rise in high-salary share (5 points)
BOOST_SIZE = 8
# Niche skills: few neighbours, concentrated in one segment. Their partner uses its own,
# lower support floors: a niche skill rarely reaches the pair floors (PAIR_MIN_*).
NICHE_MAX_DEGREE_QUANTILE = 0.25
NICHE_MIN_SEGMENT_SHARE = 0.60
NICHE_MIN_POSTINGS = 100             # deduped postings
NICHE_SIZE = 10
NICHE_PARTNER_MIN_TOGETHER = 20      # deduped postings asking for niche skill + partner
NICHE_PARTNER_MIN_MARGINAL = 50      # deduped postings asking for the partner
# Community validation and bridge skills on the sparse PMI graph (``skill_cooccurrence.pmi_graph``).
BRIDGE_SIZE = 10
COMMUNITY_TOP_SKILLS = 3
SEGMENT_COMMUNITY_MIN_SHARE = 0.10   # a segment "uses" a community holding >= 10% of its mass
# Topic profiles.
TOPIC_TITLES = 3
TOPIC_SEGMENTS = 2
TOPIC_SKILLS = 4
TOPIC_SKILL_MIN_SHARE = 0.10         # a topic's skill must appear in >= 10% of its postings
# A top title must read as a job title: no template placeholder character, at least
# TOPIC_TITLE_MIN_CHARS characters, at least TOPIC_TITLE_MIN_LETTER_SHARE letters among its
# non-space characters and one word of >= TOPIC_TITLE_MIN_WORD letters.
TOPIC_TITLE_PLACEHOLDERS = "${}"
TOPIC_TITLE_MIN_CHARS = 3
TOPIC_TITLE_MIN_LETTER_SHARE = 0.5
TOPIC_TITLE_MIN_WORD = 3


def _merged_nodes(nodes: pd.DataFrame, skills: sc.SkillIncidence | None) -> pd.DataFrame:
    """One graph-node row per merged skill (the URI with most postings), postings merged."""
    if nodes.empty:
        return nodes
    if skills is None:
        return nodes.assign(column=-1)
    frame = nodes.assign(column=nodes["esco_uri"].astype(str).map(skills.column_of))
    frame = frame.dropna(subset=["column"]).astype({"column": int}).sort_values(
        "postings", ascending=False, kind="stable").drop_duplicates("column")
    return frame.assign(postings=skills.counts[frame["column"].to_numpy()].astype(int))


def _focus(skills: sc.SkillIncidence | None) -> dict[int, tuple[int, float]]:
    """Most common segment of each merged skill (deduped postings) and its share there."""
    if skills is None or not skills.segment_ids:
        return {}
    best = skills.segment_counts.argmax(axis=1)
    peak = skills.segment_counts.max(axis=1)
    return {column: (skills.segment_ids[int(best[column])],
                     float(peak[column] / skills.unique_counts[column]))
            for column in range(len(skills.uris))
            if skills.unique_counts[column] > 0 and peak[column] > 0}


def skill_kind(top_share: float | None, breadth: int, segments: int) -> str:
    """Kind from the top-segment share and the breadth (segments with lift >= 1)."""
    if top_share is None:
        return "intermedia"
    if top_share >= SPECIALIZED_MIN_SEGMENT_SHARE:
        return "especializada"
    if breadth > 0 and breadth >= TRANSVERSAL_MIN_SEGMENT_FRACTION * segments:
        return "transversal"
    return "intermedia"


def _kinds(nodes: pd.DataFrame, focus: dict[int, tuple[int, float]],
           skills: sc.SkillIncidence | None) -> dict[int, str]:
    if skills is None or not skills.segment_ids:
        return {int(column): "intermedia" for column in nodes["column"]}
    breadth = (sc.segment_lift(skills)[1] >= 1.0).sum(axis=1)
    return {int(r.column): skill_kind(focus.get(r.column, (None, None))[1],
                                      int(breadth[r.column]), len(skills.segment_ids))
            for r in nodes.itertuples()}


def _table(nodes: pd.DataFrame, focus: dict[int, tuple[int, float]],
           skills: sc.SkillIncidence | None, total: int) -> list[dict[str, Any]]:
    if nodes.empty:
        return []
    kinds = _kinds(nodes, focus, skills)
    rows = []
    for r in nodes.sort_values(["postings", "pagerank"], ascending=False).head(
            TABLE_SIZE).itertuples():
        segment, share = focus.get(r.column, (None, None))
        rows.append({
            "esco_uri": r.esco_uri, "skill_label": r.skill_label, "postings": int(r.postings),
            "share": float(r.postings) / total if total else 0.0, "degree": int(r.degree),
            "weighted_degree": float(r.weighted_degree), "betweenness": float(r.betweenness),
            "pagerank": float(r.pagerank), "community": int(r.community),
            "top_segment": segment, "top_segment_share": share, "kind": kinds[int(r.column)],
        })
    return rows


def _core(nodes: pd.DataFrame) -> list[dict[str, Any]]:
    if nodes.empty:
        return []
    return [{"esco_uri": r.esco_uri, "skill_label": r.skill_label, "postings": int(r.postings),
             "pagerank": float(r.pagerank), "degree": int(r.degree)}
            for r in nodes.sort_values("pagerank", ascending=False).head(CORE_SIZE).itertuples()]


def generic_skills(skills: sc.SkillIncidence | None) -> set[int]:
    """Merged columns too generic for pivots (``skill_cooccurrence.generic_columns``)."""
    return set() if skills is None else {int(c) for c in sc.generic_columns(skills)}


def pivots(skills: sc.SkillIncidence | None, transitions: pd.DataFrame,
           generic: set[int]) -> list[dict[str, Any]]:
    """Shared and missing non-generic skills for every direct segment link, both directions."""
    if skills is None or transitions.empty or not skills.segment_ids:
        return []
    share, lift = sc.segment_lift(skills)
    usable = np.ones(len(skills.uris), dtype=bool)
    usable[sorted(generic)] = False
    present = usable[:, None] & (share >= PIVOT_MIN_SHARE)
    position = {segment: index for index, segment in enumerate(skills.segment_ids)}

    def ranked(columns: np.ndarray, key: np.ndarray) -> list[str]:
        order = sorted(zip(columns, key, strict=True),
                       key=lambda item: (-item[1], skills.labels[item[0]]))
        return [skills.labels[column] for column, _ in order[:PIVOT_LIST_SIZE]]

    direct = transitions[transitions["steps"] == 1].sort_values(
        ["from_segment", "direct_similarity"], ascending=[True, False])
    rows = []
    for r in direct.itertuples():
        origin, target = position.get(int(r.from_segment)), position.get(int(r.to_segment))
        shared: list[str] = []
        missing: list[str] = []
        if origin is not None and target is not None:
            gap = (present[:, target] & (lift[:, target] >= PIVOT_MIN_LIFT)
                   & (share[:, origin] <= PIVOT_MISSING_MAX_RATIO * share[:, target]))
            both = np.flatnonzero(present[:, origin] & present[:, target] & ~gap)
            shared = ranked(both, np.minimum(share[both, origin], share[both, target]))
            gaps = np.flatnonzero(gap)
            missing = ranked(gaps, share[gaps, target])
        rows.append({"from_segment": int(r.from_segment), "to_segment": int(r.to_segment),
                     "similarity": float(r.direct_similarity),
                     "shared": shared, "missing": missing})
    return rows


def _salary(postings: pd.DataFrame, skills: sc.SkillIncidence | None) -> dict[str, Any]:
    rows = skills.unique if skills is not None else np.arange(len(postings))
    bands = salary_band(postings.iloc[rows])
    salaried = bands.notna().to_numpy(dtype=bool)
    high = salaried & (bands.fillna(-1).astype(int).to_numpy() >= HIGH_SALARY_BAND)
    overall = float(high.sum() / salaried.sum()) if salaried.sum() else None
    out: dict[str, Any] = {"overall_high_share": overall, "top": [], "bottom": [], "boosts": []}
    if overall is None or skills is None:
        return out
    x = skills.deduped
    paid = x.T @ salaried.astype(float)
    rich = x.T @ high.astype(float)
    share = np.divide(rich, paid, out=np.zeros_like(paid), where=paid > 0)
    eligible = [int(i) for i in np.flatnonzero(paid >= SALARY_MIN_POSTINGS)]

    def row(i: int) -> dict[str, Any]:
        return {"skill_label": skills.labels[i], "postings_with_salary": int(paid[i]),
                "high_share": float(share[i]),
                "lift": float(share[i] / overall) if overall > 0 else None}

    top = sorted(eligible, key=lambda i: (-share[i], -paid[i]))[:SALARY_LIST_SIZE]
    bottom = sorted((i for i in eligible if i not in top),
                    key=lambda i: (share[i], -paid[i]))[:SALARY_LIST_SIZE]
    out["top"], out["bottom"] = [row(i) for i in top], [row(i) for i in bottom]

    pair_paid = (x.T @ sparse.diags(salaried.astype(float)) @ x).toarray()
    pair_rich = (x.T @ sparse.diags(high.astype(float)) @ x).toarray()
    anchors = sorted((i for i in eligible
                      if paid[i] >= BOOST_ANCHOR_MIN_POSTINGS and share[i] < overall),
                     key=lambda i: -paid[i])
    for a in anchors:
        combo = pair_paid[a].copy()
        combo[a] = 0
        combo[skills.redundant[a]] = 0  # a synonym is not a second skill
        combo_share = np.where(combo >= BOOST_MIN_COMBO,
                               pair_rich[a] / np.maximum(combo, 1), -1.0)
        b = int(combo_share.argmax())
        if combo_share[b] - share[a] < BOOST_MIN_GAIN:
            continue
        out["boosts"].append({
            "anchor": skills.labels[a], "complement": skills.labels[b],
            "anchor_postings": int(paid[a]), "anchor_high_share": float(share[a]),
            "combo_postings": int(combo[b]), "combo_high_share": float(combo_share[b]),
        })
        if len(out["boosts"]) == BOOST_SIZE:
            break
    return out


def _niche(nodes: pd.DataFrame, skills: sc.SkillIncidence | None,
           focus: dict[int, tuple[int, float]]) -> list[dict[str, Any]]:
    if skills is None or nodes.empty:
        return []
    low_degree = float(np.quantile(nodes["degree"], NICHE_MAX_DEGREE_QUANTILE))
    candidates = []
    for r in nodes.itertuples():
        segment, share = focus.get(r.column, (None, None))
        count = int(skills.unique_counts[r.column])
        if (share is not None and r.degree <= low_degree and share >= NICHE_MIN_SEGMENT_SHARE
                and count >= NICHE_MIN_POSTINGS):
            candidates.append((r, segment, share, count))
    candidates.sort(key=lambda item: (-item[2], -item[3], item[0].skill_label))
    rows = []
    for r, segment, share, count in candidates[:NICHE_SIZE]:
        i = int(r.column)
        partner = ((skills.together[i] >= NICHE_PARTNER_MIN_TOGETHER)
                   & (skills.unique_counts >= NICHE_PARTNER_MIN_MARGINAL)
                   & ~skills.redundant[i] & (skills.npmi[i] > 0))
        partner[i] = False
        scores = np.where(partner, skills.npmi[i], -np.inf)
        j = int(scores.argmax())
        found = bool(np.isfinite(scores[j]))
        rows.append({
            "skill_label": r.skill_label, "postings": count, "degree": int(r.degree),
            "top_segment": segment, "top_segment_share": share,
            "partner": skills.labels[j] if found else None,
            "partner_lift": float(skills.lift[i, j]) if found else None,
        })
    return rows


def skill_insights(run: Any, skills: sc.SkillIncidence | None) -> dict[str, Any]:
    nodes = _merged_nodes(run.skill_nodes, skills)
    focus = _focus(skills)
    return {
        "table": _table(nodes, focus, skills, len(run.postings)),
        "core": _core(nodes),
        "pivots": pivots(skills, run.transitions, generic_skills(skills)),
        "pairs": sc.pairs(skills) if skills is not None else [],
        "salary": _salary(run.postings, skills),
        "niche": _niche(nodes, skills, focus),
    }


def pmi_bridges(run: Any, skills: sc.SkillIncidence | None,
                size: int = BRIDGE_SIZE) -> list[dict[str, Any]]:
    """Bridge skills: highest betweenness on the sparse NPMI graph (generic skills removed).

    On the dense co-occurrence graph betweenness mostly tracks frequency, so the
    generic skills always win; on the NPMI graph it marks the skills that link
    otherwise separate skill families. Unweighted, exact betweenness.
    """
    if skills is None:
        return []
    graph = sc.pmi_graph(skills)
    if not graph.number_of_edges():
        return []
    scores = nx.betweenness_centrality(graph)
    community = dict(zip(run.skill_nodes["esco_uri"], run.skill_nodes["community"], strict=True)) \
        if not run.skill_nodes.empty else {}
    column = {uri: index for index, uri in enumerate(skills.uris)}
    ranked = sorted((uri for uri, value in scores.items() if value > 0),
                    key=lambda uri: (-scores[uri], skills.labels[column[uri]]))[:size]
    return [{"esco_uri": uri, "skill_label": skills.labels[column[uri]],
             "postings": int(skills.counts[column[uri]]), "degree": int(graph.degree(uri)),
             "betweenness": float(scores[uri]), "community": int(community.get(uri, -1))}
            for uri in ranked]


def community_validation(run: Any, skills: sc.SkillIncidence | None) -> dict[str, Any]:
    """Louvain on the sparse NPMI skill graph, and how each segment spreads over it."""
    out: dict[str, Any] = {"pmi_edges": 0, "pmi_communities": 0, "pmi_modularity": None,
                           "communities": [], "segments": []}
    if skills is None:
        return out
    graph = sc.pmi_graph(skills)
    if not graph.number_of_edges():
        return out
    found = nx.community.louvain_communities(graph, weight="weight", seed=42)
    found = sorted(found, key=lambda members: (-len(members), min(members)))
    column = {uri: index for index, uri in enumerate(skills.uris)}
    groups = [[column[uri] for uri in members] for members in found]
    out.update(
        pmi_edges=int(graph.number_of_edges()), pmi_communities=len(found),
        pmi_modularity=float(nx.community.modularity(graph, found, weight="weight")),
        communities=[
            {"community": index, "size": len(members),
             "top_skills": [skills.labels[i] for i in sorted(
                 members, key=lambda i: (-skills.unique_counts[i], skills.labels[i]))[
                 :COMMUNITY_TOP_SKILLS]]}
            for index, members in enumerate(groups)
        ],
    )
    sizes = skills.segment_sizes
    for position, segment in enumerate(skills.segment_ids):
        if sizes[position] <= 0:
            mass = np.zeros(len(groups))
        else:
            share = skills.segment_counts[:, position] / sizes[position]
            mass = np.array([share[members].sum() for members in groups])
        weight = float(mass.sum())
        if weight <= 0:
            out["segments"].append({"segment": int(segment), "dominant_community": None,
                                    "dominant_share": None, "communities_used": 0})
            continue
        shares = mass / weight
        out["segments"].append({
            "segment": int(segment), "dominant_community": int(shares.argmax()),
            "dominant_share": float(shares.max()),
            "communities_used": int((shares >= SEGMENT_COMMUNITY_MIN_SHARE).sum()),
        })
    return out


def topic_profiles(run: Any, topics: list[dict[str, Any]], skills: sc.SkillIncidence | None,
                   titles: pd.Series) -> list[dict[str, Any]]:
    """Add size, titles, segments and over-represented skills to each NMF topic.

    Needs ``topic_assignments.parquet`` next to the run; without it the topics
    are returned unchanged (the fields are optional for the frontend). Topics
    describe the run as published, so they use every posting (no dedupe).
    """
    path = run.run_dir / "topic_assignments.parquet"
    if not topics or not path.is_file():
        return topics
    assignments = pd.read_parquet(path, columns=["vacancy_id", "source", "topic_id"])
    assignments = assignments.astype({"vacancy_id": str, "source": str}).drop_duplicates(
        ["vacancy_id", "source"])
    keys = run.postings[["vacancy_id", "source"]].astype(str)
    topic_of = keys.merge(assignments, how="left", on=["vacancy_id", "source"])[
        "topic_id"].to_numpy()
    total = len(run.postings)
    clusters = run.postings["cluster_id"].reset_index(drop=True)
    titles = titles.fillna("").astype(str).reset_index(drop=True)
    readable = {title: topic_title_ok(title) for title in titles.unique()}
    result = []
    for topic in topics:
        mask = topic_of == topic["topic_id"]
        count = int(mask.sum())
        named = titles[mask]
        named = named[named.map(readable).astype(bool)]
        segments = clusters[mask].value_counts(normalize=True).head(TOPIC_SEGMENTS)
        result.append({
            **topic, "postings": count, "share": count / total if total else 0.0,
            "top_titles": [str(t) for t in named.value_counts().head(TOPIC_TITLES).index],
            "top_segments": [{"segment": int(segment), "share": float(value)}
                             for segment, value in segments.items()],
            "top_skills": _topic_skills(skills, mask, count),
        })
    return result


def topic_title_ok(title: str) -> bool:
    """True when a cleaned title reads as a job title (rules at ``TOPIC_TITLE_*``)."""
    text = title.strip()
    if len(text) < TOPIC_TITLE_MIN_CHARS or any(c in text for c in TOPIC_TITLE_PLACEHOLDERS):
        return False
    visible = [c for c in text if not c.isspace()]
    letters = sum(c.isalpha() for c in visible)
    if letters < TOPIC_TITLE_MIN_LETTER_SHARE * len(visible):
        return False
    return re.search(rf"[^\W\d_]{{{TOPIC_TITLE_MIN_WORD},}}", text) is not None


def _topic_skills(skills: sc.SkillIncidence | None, mask: np.ndarray, count: int) -> list[str]:
    if skills is None or not count:
        return []
    inside = np.asarray(skills.matrix[mask].sum(axis=0)).ravel() / count
    overall = skills.counts / skills.total
    lift = np.divide(inside, overall, out=np.zeros_like(inside), where=overall > 0)
    candidates = np.flatnonzero(inside >= TOPIC_SKILL_MIN_SHARE)
    order = candidates[np.lexsort((-inside[candidates], -lift[candidates]))]
    return [skills.labels[i] for i in order[:TOPIC_SKILLS]]
