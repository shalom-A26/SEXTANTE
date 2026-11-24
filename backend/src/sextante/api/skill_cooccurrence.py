"""Posting × skill incidence for the skill insights: label merge, dedupe, NPMI.

Three corrections are applied before any co-occurrence is counted
(``docs/techniques.md`` § 10):

* **Label merge**: graph skills whose labels normalize to the same text
  (casefold, no accents, punctuation and extra spaces dropped) are one skill;
  the URI with most postings represents it.
* **Posting dedupe**: one template posted thousands of times would otherwise
  dominate every association. ``postings.parquet`` carries no description and
  the run's duplicate pairs are a capped sample (not in ``API_FILES``), so
  postings are collapsed on stable keys (see ``unique_postings``).
* **Redundant pairs**: two skills that are the same concept (one label contains
  the other, or they share an ESCO alias, so one phrase matched both) never
  form a pair, a partner or a PMI-graph edge.

*Generic* skills (asked by >= ``GENERIC_MIN_SHARE`` of the deduped postings)
are left out of the PMI community graph and of the segment pivots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse

from sextante.analytics.taxonomy import normalize_text

# Posting dedupe: with at least TEMPLATE_MIN_SKILLS skills, an identical skill set is one
# template whatever its title or company (an exact 4+ skill combination repeated is a
# reposted template, not independent demand); with DEDUPE_MIN_SKILLS..TEMPLATE_MIN_SKILLS-1
# skills it also needs the same normalized title or the same known company.
DEDUPE_MIN_SKILLS = 3
TEMPLATE_MIN_SKILLS = 4
# Generic skills: asked by at least this share of the deduped postings. They connect every
# family, so they are excluded from the PMI community graph and from pivots.
GENERIC_MIN_SHARE = 0.05
# Skill pairs, ranked by NPMI.
PAIR_MIN_MARGINAL = 200     # deduped postings each skill needs
PAIR_MIN_TOGETHER = 50      # deduped postings asking for both
PAIRS_SIZE = 15
# Sparse PMI graph for community validation.
PMI_MIN_NPMI = 0.10         # clearly positive association (lift >= ~1.5–2.6, see docs)
PMI_MIN_TOGETHER = 30       # deduped postings asking for both
PMI_TOP_K = 10              # each skill keeps its k strongest qualifying edges (union)


@dataclass
class SkillIncidence:
    """Posting × merged-skill incidence over the graph nodes."""

    uris: list[str]                  # representative URI per merged skill
    labels: list[str]
    column_of: dict[str, int]        # every graph-node URI -> merged column
    matrix: sparse.csr_matrix        # all postings (topics, table demand)
    counts: np.ndarray               # all postings per merged skill
    total: int                       # postings in the run
    unique: np.ndarray               # row indices of the deduplicated postings
    deduped: sparse.csr_matrix       # matrix[unique]
    unique_counts: np.ndarray        # deduped postings per skill
    unique_total: int
    together: np.ndarray             # skills × skills deduped postings asking for both
    lift: np.ndarray                 # skills × skills lift over deduped postings
    npmi: np.ndarray                 # skills × skills normalized PMI (-1 when never together)
    redundant: np.ndarray            # skills × skills same concept (containment, shared alias)
    segment_ids: list[int]
    segment_counts: np.ndarray       # skills × segments deduped postings
    segment_sizes: np.ndarray        # deduped postings per segment


def _normalized(postings: pd.DataFrame, column: str) -> list[str]:
    if column not in postings:
        return [""] * len(postings)
    values = postings[column].fillna("").astype(str)
    lookup = {value: normalize_text(value) for value in values.unique()}
    return values.map(lookup).tolist()


def unique_postings(postings: pd.DataFrame, matrix: sparse.csr_matrix) -> np.ndarray:
    """Rows kept after collapsing near-identical postings (first occurrence wins).

    A posting with >= ``TEMPLATE_MIN_SKILLS`` skills is a copy of any earlier
    one with the identical skill set (a template reposted with changing title
    and company). With >= ``DEDUPE_MIN_SKILLS`` skills it is a copy of an
    earlier one with the same skill set and either the same normalized title or
    the same known company; with fewer skills a copy needs the same title,
    company and skill set. Rows must have sorted indices.
    """
    title, company = _normalized(postings, "title"), _normalized(postings, "company")
    indptr, indices = matrix.indptr, matrix.indices
    seen: set[tuple[Any, ...]] = set()
    keep = []
    for row in range(matrix.shape[0]):
        start, end = indptr[row], indptr[row + 1]
        skills = indices[start:end].tobytes()
        if end - start >= TEMPLATE_MIN_SKILLS:
            keys = [("template", skills)]
        elif end - start >= DEDUPE_MIN_SKILLS:
            keys = [("title", title[row], skills)]
            if company[row]:
                keys.append(("company", company[row], skills))
        else:
            keys = [("posting", title[row], company[row], skills)]
        if not any(key in seen for key in keys):
            keep.append(row)
        seen.update(keys)
    return np.asarray(keep, dtype=int)


def _aliases(matcher: Any) -> dict[str, set[str]]:
    """Normalized alias phrases per URI, read from the API matcher's trie."""
    out: dict[str, set[str]] = {}
    root = getattr(matcher, "root", None)
    stack = [(root, "")] if root is not None else []
    while stack:
        node, phrase = stack.pop()
        if phrase:
            for uri, _ in node.concepts:
                out.setdefault(uri, set()).add(phrase)
        for token, child in node.children.items():
            stack.append((child, f"{phrase} {token}" if phrase else token))
    return out


def _redundant(keys: list[str], members: list[list[str]], aliases: dict[str, set[str]]
               ) -> np.ndarray:
    """True for skill pairs that name the same concept."""
    names = [{key}.union(*(aliases.get(uri, set()) for uri in uris))
             for key, uris in zip(keys, members, strict=True)]
    padded = [f" {key} " for key in keys]
    out = np.zeros((len(keys), len(keys)), dtype=bool)
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            if padded[a] in padded[b] or padded[b] in padded[a] or names[a] & names[b]:
                out[a, b] = out[b, a] = True
    return out


def _association(together: np.ndarray, counts: np.ndarray, total: int
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Lift and NPMI = log2(lift) / -log2(P(A∩B)) for every skill pair."""
    expected = np.outer(counts, counts) / max(total, 1)
    lift = np.divide(together, expected, out=np.zeros_like(together), where=expected > 0)
    npmi = np.full_like(lift, -1.0)
    seen = together > 0
    pmi = np.log2(lift, out=np.zeros_like(lift), where=seen)
    surprise = -np.log2(together / max(total, 1), out=np.zeros_like(lift), where=seen)
    scaled = seen & (surprise > 0)
    npmi[scaled] = pmi[scaled] / surprise[scaled]
    npmi[seen & ~scaled] = 1.0  # every posting asks for both
    return lift, npmi


def skill_incidence(run: Any) -> SkillIncidence | None:
    nodes = run.skill_nodes
    if nodes.empty or not len(run.posting_skills):
        return None
    ordered = nodes.sort_values("postings", ascending=False, kind="stable")
    position: dict[str, int] = {}    # normalized label -> merged column
    uris: list[str] = []
    labels: list[str] = []
    members: list[list[str]] = []
    column_of: dict[str, int] = {}
    for uri, label in zip(ordered["esco_uri"].astype(str), ordered["skill_label"].astype(str),
                          strict=True):
        key = normalize_text(label) or uri
        if key not in position:
            position[key] = len(uris)
            uris.append(uri)
            labels.append(label)
            members.append([])
        column_of[uri] = position[key]
        members[position[key]].append(uri)
    keys = list(position)
    rows, cols = [], []
    for row, skills in enumerate(run.posting_skills):
        for uri in skills:
            column = column_of.get(uri)
            if column is not None:
                rows.append(row)
                cols.append(column)
    total = len(run.posting_skills)
    matrix = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(total, len(keys)))
    if not matrix.nnz:
        return None
    matrix.sum_duplicates()
    matrix.data[:] = 1.0  # two merged URIs in one posting still count once
    matrix.sort_indices()
    unique = unique_postings(run.postings, matrix)
    deduped = matrix[unique]
    unique_counts = np.asarray(deduped.sum(axis=0)).ravel()
    together = (deduped.T @ deduped).toarray()
    lift, npmi = _association(together, unique_counts, len(unique))
    segment_ids = [int(segment) for segment in run.segment_ids]
    position = {segment: index for index, segment in enumerate(segment_ids)}
    codes = run.postings["cluster_id"].map(position).fillna(-1).astype(int).to_numpy()[unique]
    valid = np.flatnonzero(codes >= 0)
    onehot = sparse.csr_matrix((np.ones(len(valid)), (valid, codes[valid])),
                               shape=(len(unique), len(segment_ids)))
    return SkillIncidence(
        uris=uris, labels=labels, column_of=column_of, matrix=matrix,
        counts=np.asarray(matrix.sum(axis=0)).ravel(), total=total, unique=unique,
        deduped=deduped, unique_counts=unique_counts, unique_total=len(unique),
        together=together, lift=lift, npmi=npmi,
        redundant=_redundant(keys, members, _aliases(getattr(run, "matcher", None))),
        segment_ids=segment_ids, segment_counts=(deduped.T @ onehot).toarray(),
        segment_sizes=np.asarray(onehot.sum(axis=0)).ravel(),
    )


def generic_columns(skills: SkillIncidence) -> np.ndarray:
    """Merged columns asked by >= ``GENERIC_MIN_SHARE`` of the deduped postings."""
    share = skills.unique_counts / max(skills.unique_total, 1)
    return np.flatnonzero(share >= GENERIC_MIN_SHARE)


def segment_lift(skills: SkillIncidence) -> tuple[np.ndarray, np.ndarray]:
    """Skills × segments share (of the segment's deduped postings) and lift over the corpus."""
    sizes = skills.segment_sizes[None, :]
    share = np.divide(skills.segment_counts, sizes, out=np.zeros_like(skills.segment_counts),
                      where=sizes > 0)
    overall = (skills.unique_counts / max(skills.unique_total, 1))[:, None]
    lift = np.divide(share, overall, out=np.zeros_like(share), where=overall > 0)
    return share, lift


def pairs(skills: SkillIncidence) -> list[dict[str, Any]]:
    """Strongest skill pairs by NPMI (ties: more postings together); pmi = log2(lift)."""
    left, right = np.triu_indices(len(skills.uris), k=1)
    together = skills.together[left, right]
    keep = ((together >= PAIR_MIN_TOGETHER)
            & (skills.unique_counts[left] >= PAIR_MIN_MARGINAL)
            & (skills.unique_counts[right] >= PAIR_MIN_MARGINAL)
            & ~skills.redundant[left, right] & (skills.npmi[left, right] > 0))
    left, right, together = left[keep], right[keep], together[keep]
    npmi = skills.npmi[left, right]
    order = np.lexsort((-together, -npmi))[:PAIRS_SIZE]
    return [{"a": skills.labels[left[i]], "b": skills.labels[right[i]],
             "together": int(together[i]), "lift": float(skills.lift[left[i], right[i]]),
             "pmi": float(np.log2(skills.lift[left[i], right[i]]))}
            for i in order]


def pmi_graph(skills: SkillIncidence) -> nx.Graph:
    """Sparse NPMI-weighted skill graph (nodes without a qualifying edge are left out).

    An edge needs NPMI >= ``PMI_MIN_NPMI``, ``PMI_MIN_TOGETHER`` deduped
    postings and two distinct concepts; it is kept when it is among the
    ``PMI_TOP_K`` strongest of either endpoint. Generic skills
    (``generic_columns``) are removed first: they co-occur with every family
    and would merge them into one hub community.
    """
    eligible = ((skills.together >= PMI_MIN_TOGETHER) & (skills.npmi >= PMI_MIN_NPMI)
                & ~skills.redundant)
    np.fill_diagonal(eligible, False)
    generic = generic_columns(skills)
    eligible[generic, :] = False
    eligible[:, generic] = False
    chosen = np.zeros_like(eligible)
    for i in range(len(skills.uris)):
        candidates = np.flatnonzero(eligible[i])
        top = candidates[np.argsort(-skills.npmi[i, candidates], kind="stable")[:PMI_TOP_K]]
        chosen[i, top] = True
    left, right = np.nonzero(np.triu(chosen | chosen.T, k=1))
    graph = nx.Graph()
    graph.add_weighted_edges_from(
        (skills.uris[a], skills.uris[b], float(skills.npmi[a, b]))
        for a, b in zip(left, right, strict=True))
    return graph
