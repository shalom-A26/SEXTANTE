"""Stage 6: skills–occupations graph, communities, centrality, transitions.

Two graphs are built from the run's skill mentions and K-Means segments:

* a **skill co-occurrence graph** (skills linked when they appear in the same
  posting) for communities (Louvain) and centrality (PageRank, betweenness);
* a **segment graph** (occupational segments linked by the similarity of
  their skill profiles) whose shortest paths are transition routes.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

MAX_SKILLS = 400            # graph nodes: most frequent skills only
MIN_COOCCURRENCE = 2        # edge weight threshold (postings sharing both)
SEGMENT_NEIGHBOURS = 3      # each segment keeps its k most similar segments


def segment_skill_profiles(mentions: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    """Share of each segment's postings mentioning each skill, plus lift."""
    columns = ["cluster_id", "esco_uri", "skill_label", "postings", "share", "lift"]
    if mentions.empty or segments.empty:
        return pd.DataFrame(columns=columns)
    keyed = mentions.merge(
        segments[["vacancy_id", "source", "cluster_id"]], on=["vacancy_id", "source"]
    ).drop_duplicates(["vacancy_id", "source", "esco_uri"])
    sizes = segments.groupby("cluster_id").size()
    total = len(segments)
    counts = keyed.groupby(["cluster_id", "esco_uri", "skill_label"]).size().rename("postings")
    profile = counts.reset_index()
    profile["share"] = profile["postings"] / profile["cluster_id"].map(sizes)
    global_share = keyed.groupby("esco_uri").size() / total
    profile["lift"] = profile["share"] / profile["esco_uri"].map(global_share)
    return profile.sort_values(["cluster_id", "share"], ascending=[True, False])[columns]


def skill_graph(mentions: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    if mentions.empty:
        return graph
    unique = mentions.drop_duplicates(["vacancy_id", "source", "esco_uri"])
    frequency = unique.groupby(["esco_uri", "skill_label"]).size().nlargest(MAX_SKILLS)
    kept = {uri for uri, _ in frequency.index}
    for (uri, label), count in frequency.items():
        graph.add_node(uri, label=label, postings=int(count))
    pairs: Counter[tuple[str, str]] = Counter()
    for _, group in unique[unique["esco_uri"].isin(kept)].groupby(["vacancy_id", "source"]):
        pairs.update(combinations(sorted(group["esco_uri"]), 2))
    for (left, right), weight in pairs.items():
        if weight >= MIN_COOCCURRENCE:
            graph.add_edge(left, right, weight=int(weight))
    return graph


def segment_graph(profiles: pd.DataFrame, segment_ids: list[int]) -> nx.Graph:
    """Segments linked to their nearest neighbours by skill-profile cosine."""
    graph = nx.Graph()
    graph.add_nodes_from(int(segment) for segment in segment_ids)
    if profiles.empty or len(segment_ids) < 2:
        return graph
    pivot = profiles.pivot_table(
        index="cluster_id", columns="esco_uri", values="share", fill_value=0.0
    ).reindex(segment_ids, fill_value=0.0)
    vectors = pivot.to_numpy()
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    unit = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)
    similarity = unit @ unit.T
    for row, source in enumerate(segment_ids):
        order = [col for col in np.argsort(similarity[row])[::-1] if col != row]
        for col in order[:SEGMENT_NEIGHBOURS]:
            value = float(similarity[row, col])
            if value > 0:
                graph.add_edge(int(source), int(segment_ids[col]),
                               similarity=value, distance=1.0 - value)
    return graph


def transition_routes(graph: nx.Graph) -> pd.DataFrame:
    rows = []
    lengths = dict(nx.all_pairs_dijkstra(graph, weight="distance"))
    for source, (costs, paths) in lengths.items():
        for target, cost in costs.items():
            if source == target:
                continue
            path = paths[target]
            similarity = (
                graph[source][target]["similarity"] if graph.has_edge(source, target) else 0.0
            )
            rows.append({
                "from_segment": int(source), "to_segment": int(target),
                "path": [int(step) for step in path], "steps": len(path) - 1,
                "cost": float(cost), "direct_similarity": float(similarity),
            })
    return pd.DataFrame(rows, columns=[
        "from_segment", "to_segment", "path", "steps", "cost", "direct_similarity",
    ])


def build_graphs(mentions: pd.DataFrame, segments: pd.DataFrame,
                 output_dir: str | Path) -> dict[str, Any]:
    """Write graph artifacts and return summary metrics for the manifest."""
    output_dir = Path(output_dir)
    profiles = segment_skill_profiles(mentions, segments)
    profiles.to_parquet(output_dir / "segment_skills.parquet", index=False)

    skills = skill_graph(mentions)
    communities: list[set[str]] = []
    if skills.number_of_edges():
        communities = nx.community.louvain_communities(skills, weight="weight", seed=42)
    community_of = {node: index for index, members in enumerate(communities) for node in members}
    pagerank = nx.pagerank(skills, weight="weight") if skills.number_of_edges() else {}
    sample = min(200, skills.number_of_nodes()) or None
    betweenness = (
        nx.betweenness_centrality(skills, k=sample, seed=42)
        if skills.number_of_edges() else {}
    )
    nodes = pd.DataFrame([
        {
            "esco_uri": node,
            "skill_label": data["label"],
            "postings": data["postings"],
            "degree": int(skills.degree(node)),
            "weighted_degree": float(skills.degree(node, weight="weight")),
            "pagerank": float(pagerank.get(node, 0.0)),
            "betweenness": float(betweenness.get(node, 0.0)),
            "community": int(community_of.get(node, -1)),
        }
        for node, data in skills.nodes(data=True)
    ], columns=["esco_uri", "skill_label", "postings", "degree", "weighted_degree",
                "pagerank", "betweenness", "community"])
    nodes.sort_values("pagerank", ascending=False).to_parquet(
        output_dir / "skill_graph_nodes.parquet", index=False
    )
    edges = pd.DataFrame(
        [{"source": a, "target": b, "weight": d["weight"]} for a, b, d in skills.edges(data=True)],
        columns=["source", "target", "weight"],
    )
    edges.to_parquet(output_dir / "skill_graph_edges.parquet", index=False)

    segment_ids = sorted(int(value) for value in segments["cluster_id"].unique())
    occupations = segment_graph(profiles, segment_ids)
    routes = transition_routes(occupations)
    routes.to_parquet(output_dir / "segment_transitions.parquet", index=False)

    modularity = (
        float(nx.community.modularity(skills, communities, weight="weight"))
        if communities else None
    )
    return {
        "skill_nodes": skills.number_of_nodes(),
        "skill_edges": skills.number_of_edges(),
        "skill_communities": len(communities),
        "skill_modularity": modularity,
        "segment_nodes": occupations.number_of_nodes(),
        "segment_edges": occupations.number_of_edges(),
        "transition_routes": int(len(routes)),
    }
