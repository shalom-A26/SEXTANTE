"""Exact phrase matching against a versioned Spanish ESCO skills CSV."""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_SYNONYMS = Path(__file__).with_name("synonyms_es.csv")
TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(TOKEN_RE.findall(text))


@dataclass
class _TrieNode:
    children: dict[str, "_TrieNode"] = field(default_factory=dict)
    concepts: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class EscoMatcher:
    """A memory-resident token trie with deterministic longest matches."""

    root: _TrieNode
    taxonomy_version: str
    concepts: int
    synonyms_added: int = 0

    def match(self, text: Any) -> list[dict[str, str]]:
        tokens = TOKEN_RE.findall(normalize_text(text))
        matches: dict[str, dict[str, str]] = {}
        for start in range(len(tokens)):
            node = self.root
            position = start
            found: list[tuple[int, tuple[str, str]]] = []
            while position < len(tokens) and tokens[position] in node.children:
                node = node.children[tokens[position]]
                position += 1
                if node.concepts:
                    found.extend((position, concept) for concept in node.concepts)
            for end, (uri, label) in found:
                phrase = " ".join(tokens[start:end])
                if uri not in matches:
                    matches[uri] = {
                        "esco_uri": uri,
                        "skill_label": label,
                        "matched_text": phrase,
                    }
        return list(matches.values())


def _column(headers: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {item.casefold().replace("_", ""): item for item in headers}
    return next(
        (normalized[candidate.casefold().replace("_", "")] for candidate in candidates
         if candidate.casefold().replace("_", "") in normalized),
        None,
    )


def load_esco_csv(
    path: str | Path,
    taxonomy_version: str = "1.2.1",
    synonyms: str | Path | None = DEFAULT_SYNONYMS,
) -> EscoMatcher:
    """Load the skills CSV downloaded from the official ESCO portal.

    The preferred-label and alternative-label columns are read from the
    language-specific CSV; occupation rows and malformed concepts are ignored.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(8192)
        stream.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(stream, dialect=dialect)
        headers = reader.fieldnames or []
        uri_col = _column(headers, ("conceptUri", "concept_uri", "uri"))
        label_col = _column(headers, ("preferredLabel", "preferred_label", "label"))
        alt_col = _column(headers, ("altLabels", "alternativeLabels", "alt_labels"))
        type_col = _column(headers, ("conceptType", "concept_type", "type"))
        if not uri_col or not label_col:
            raise ValueError("ESCO CSV must include conceptUri and preferredLabel columns")

        root = _TrieNode()
        known_uris: set[str] = set()
        by_label: dict[str, tuple[str, str]] = {}
        for row in reader:
            uri = (row.get(uri_col) or "").strip()
            label = (row.get(label_col) or "").strip()
            concept_type = (row.get(type_col) or "").casefold() if type_col else ""
            is_not_skill = (
                concept_type
                and "skill" not in concept_type
                and "competence" not in concept_type
            )
            if not uri or not label or is_not_skill:
                continue
            known_uris.add(uri)
            aliases = [label]
            if alt_col:
                aliases.extend(part.strip() for part in re.split(r"[|\n;]", row.get(alt_col) or ""))
            concept = (uri, label)
            by_label.setdefault(normalize_text(label), concept)
            for alias in aliases:
                normalized = normalize_text(alias)
                if len(normalized) < 3:
                    continue
                node = root
                for token in normalized.split():
                    node = node.children.setdefault(token, _TrieNode())
                if concept not in node.concepts:
                    node.concepts.append(concept)
        if not known_uris:
            raise ValueError("ESCO CSV contains no skill concepts; check the selected CSV")
    matcher = EscoMatcher(root=root, taxonomy_version=taxonomy_version, concepts=len(known_uris))
    if synonyms is not None:
        matcher.synonyms_added = _add_synonyms(root, synonyms, by_label)
    return matcher


def _add_synonyms(root: _TrieNode, path: Path, by_label: dict[str, tuple[str, str]]) -> int:
    """Attach curated Colombian synonyms to ESCO concepts, resolved by label.

    Rows whose ``esco_label`` is not a skill in the loaded CSV are skipped,
    so the file never injects concepts that the taxonomy does not contain.
    """
    added = 0
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            concept = by_label.get(normalize_text(row.get("esco_label")))
            alias = normalize_text(row.get("synonym"))
            if concept is None or len(alias) < 2:
                continue
            node = root
            for token in alias.split():
                node = node.children.setdefault(token, _TrieNode())
            if concept not in node.concepts:
                node.concepts.append(concept)
                added += 1
    return added


def extract_skills(frame: pd.DataFrame, matcher: EscoMatcher) -> pd.DataFrame:
    """Return one row per posting/concept match, preserving source identifiers."""
    output: list[dict[str, Any]] = []
    for row in frame[["vacancy_id", "source", "url", "description"]].itertuples(index=False):
        if not isinstance(row.description, str) or not row.description.strip():
            continue
        for match in matcher.match(row.description):
            output.append({
                "vacancy_id": row.vacancy_id,
                "source": row.source,
                "url": row.url,
                **match,
            })
    return pd.DataFrame(output, columns=[
        "vacancy_id", "source", "url", "esco_uri", "skill_label", "matched_text"
    ])


def matcher_from_mentions(mentions: pd.DataFrame) -> EscoMatcher:
    """Rebuild a matcher from the aliases actually seen in the corpus.

    The API uses it to read skills from a CV without shipping the ESCO CSV:
    only skills that occur in vacancies can be matched or recommended anyway.
    """
    root = _TrieNode()
    pairs = mentions[["esco_uri", "skill_label", "matched_text"]].drop_duplicates()
    for uri, label, phrase in pairs.itertuples(index=False):
        for alias in {normalize_text(phrase), normalize_text(label)}:
            if len(alias) < 3:
                continue
            node = root
            for token in alias.split():
                node = node.children.setdefault(token, _TrieNode())
            if (uri, label) not in node.concepts:
                node.concepts.append((uri, label))
    return EscoMatcher(root=root, taxonomy_version="corpus-lexicon",
                       concepts=int(pairs["esco_uri"].nunique()))
