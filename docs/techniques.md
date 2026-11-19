# SEXTANTE techniques

Every technique the pipeline applies, in order, with the parameters the code
actually uses. Paths are relative to `backend/src/sextante/`. Where the data
lives between steps is in [data.md](data.md); how the pieces are deployed is in
[architecture.md](architecture.md). The web guide ("Cómo funciona") runs a
TypeScript mirror of these techniques on six example rows
(`frontend/components/guide/pipeline.ts`).

| # | Technique | Layer it produces | Code |
|---|---|---|---|
| 1 | [Capture and canonical schema](#1-capture-and-canonical-schema) | Bronze | `ingestion/sources/`, `core/schema.py` |
| 2 | [Append-only store and key dedupe](#2-append-only-store-and-key-dedupe) | Bronze | `ingestion/store.py`, `ingestion/emit.py`, `ingestion/sync.py` |
| 3 | [Text repair and normalization](#3-text-repair-and-normalization) | Silver | `analytics/cleaning.py`, `analytics/taxonomy.py` |
| 4 | [ESCO skill extraction](#4-esco-skill-extraction) | Silver | `analytics/taxonomy.py` |
| 5 | [Near-duplicate detection](#5-near-duplicate-detection) | Silver | `analytics/duplicates.py` |
| 6 | [TF-IDF representation](#6-tf-idf-representation) | Silver | `analytics/features.py` |
| 7 | [Topics (NMF)](#7-topics-nmf) | Gold | `analytics/features.py` |
| 8 | [Occupational segments](#8-occupational-segments) | Gold | `analytics/features.py`, `analytics/comparison.py` |
| 9 | [Salary band model](#9-salary-band-model) | Gold | `analytics/supervised.py` |
| 10 | [Skills graph and transition routes](#10-skills-graph-and-transition-routes) | Gold | `analytics/graph.py` |
| 11 | [CV matching, niches, pivots and gaps](#11-cv-matching-niches-pivots-and-gaps) | Serving | `api/cv.py`, `api/insights.py` |
| 12 | [Validation](#12-validation) | Review | `analytics/validation.py` |

---

## 1. Capture and canonical schema

**Why.** Each source names and formats its fields differently; every later
stage must read one contract.

**How.** The SPE source downloads the portal's official CSV export; the
JobSpy source runs a general search for Colombia on the active boards
(`ACTIVE_SITES`). Both rename their fields to the 17 canonical columns
(`LEGACY_RENAME` covers the original Spanish names), then `normalize()` puts
them in order and `validate()` checks them. `captured_at` is stamped as
`%Y-%m-%d %H:%M:%S`; `published_at` is kept as the source gives it.

**Parameters.** SPE every 12 h, JobSpy every 30 min with 100 results per run;
identifiable `sextante.USER_AGENT`; throttled requests; TLS verification is
disabled for the rest of a run after the first SPE `SSLError` (incomplete CA
chain on the portal).

**Output.** In-memory canonical frames handed to the store.

## 2. Append-only store and key dedupe

**Why.** Published files must be immutable and the first-seen date must
never change.

**How.** `store.append()` adds only rows whose key is not already present
(`keep="first"`) and returns the number of *new* rows. Keys: `vacancy_id` for
SPE (several vacancies can share a provider URL), `url` for job boards.
`emit` partitions rows by capture date (ISO week for SPE, calendar day for
JobSpy) and `_stable()` fixes dtypes and row order so identical content gives
identical bytes and `upload_folder` skips unchanged files. `pull` rebuilds the
stores from Hugging Face before each run (runners are ephemeral) and writes
the published baseline that powers `rows_new`.

**Output.** Bronze partitions `data/spe/week-*.parquet`,
`data/jobspy/day-*.parquet` on Hugging Face.

## 3. Text repair and normalization

**Why.** Part of the SPE export is double-encoded ("TÃ©cnico") and the same
department is spelled several ways; job-ad boilerplate would dominate any
text model.

**How.**
- `repair_mojibake`: while the pattern `Ã+byte`, `â€` or `Â+byte` appears,
  re-encode with cp1252 (or latin-1) and decode as UTF-8, at most two rounds;
  clean text passes through unchanged.
- `normalize_departments`: maps Indeed codes (`ANT`, `VAC`…), LinkedIn title
  case and "Capital District" onto the 33 SPE department names; a Bogotá city
  always maps to `BOGOTÁ, D.C.`.
- `normalize_text`: NFKD, casefold, drop diacritics, tokens `[^\W_]+`.
- TF-IDF drops Spanish stop words plus schedule/benefit boilerplate and
  recruiting template words (`features.BOILERPLATE_STOP_WORDS`).

Source rows on Hugging Face are never modified; repairs happen in the run.

## 4. ESCO skill extraction

**Why.** The job title hides what is asked; the skills live in the free-text
description and need a shared vocabulary.

**How.** ESCO v1.2.1 (Spanish, ~13.9k skills) is loaded into a token trie
(`EscoMatcher`). From every token position the matcher walks the trie and
keeps the **longest** match, then jumps past it, so "excel avanzado" wins over
"excel". A curated Colombian synonym list (`analytics/synonyms_es.csv`,
synonym → ESCO preferred label) extends the aliases, and a blocklist
(`analytics/alias_blocklist_es.csv`) removes ambiguous ones ("transporte" is
not logistics).

**Parameters.** ESCO CSV pinned by SHA-256 (release `taxonomy-esco-v1.2.1`);
synonym count and hash recorded in the run manifest.

**Output.** `skill_mentions.parquet` (vacancy, source, URL, ESCO URI and
label, matched phrase), `skill_aliases.parquet`.

## 5. Near-duplicate detection

**Why.** The same vacancy is published on several boards with different keys;
comparing every pair is quadratic.

**How.** Each description becomes 3-word shingles (at most 512, evenly
sampled). MinHash signatures with 64 permutations (seed 42) feed a
locality-sensitive hashing index (threshold 0.70) that proposes candidates;
each candidate pair is confirmed with cosine similarity over word n-gram
TF-IDF. Nothing is deleted or merged automatically: pairs are for review.

**Parameters.** Confirmation threshold 0.90 (`--duplicate-threshold`), up to
20 candidates per posting, at most 500,000 pairs per run.

**Output.** `duplicate_candidates.parquet`; the manifest reports
`duplicate_postings` and `duplicate_groups` (pairs linked transitively; lower
bounds because candidates are capped).

## 6. TF-IDF representation

**Why.** Models need numbers: a word should weigh more when it is frequent in
one posting and rare in the rest.

**How.** Title + " . " + description, `TfidfVectorizer` with 1–2 grams,
L2-normalized rows, so the dot product of two rows is their cosine similarity.
The vocabulary is fitted on a fixed-size sample to bound memory, then every
posting is transformed.

**Parameters.** `ngram_range=(1, 2)`, `min_df=2`, `max_df=0.98`,
`max_features=50,000`, fit sample 120,000 rows.

**Output.** `tfidf_matrix.npz`, `tfidf_vocabulary.json`, `tfidf_idf.npy`,
`tfidf_vectorizer.joblib`, `postings.parquet` (row-aligned metadata).

## 7. Topics (NMF)

**Why.** Groups of words that appear together describe recurring kinds of
work across the corpus.

**How.** Non-negative matrix factorization `X ≈ W · H` of the TF-IDF matrix:
rows of `H` are topics (their top terms), rows of `W` are each posting's mix.

**Parameters.** 12 topics (`--topics`), `random_state=42`.

**Output.** `topics.csv`, `topic_assignments.parquet`.

## 8. Occupational segments

**Why.** Group postings by what they ask for, not by what they are called.

**How.** K-Means on the TF-IDF space, seeded; the cosine silhouette measures
separation. A two-dimensional TruncatedSVD projection (a sparse PCA
approximation) is stored for plotting. Segments are named after their most
common cleaned title when it covers at least 5% of the segment; otherwise
"Varios: <top terms>"; repeated names get a distinctive term. For comparison,
`comparison.py` runs K-Means, Ward hierarchical clustering and DBSCAN on a
3,000-row SVD-50 sample (silhouette, noise share, ARI against the published
K-Means) and a t-SNE projection; K-Means stays the published segmentation.

**Parameters.** 8 clusters (`--clusters`), `n_init=10`, `max_iter=300`,
`random_state=42`; silhouette on at most 5,000 evenly selected rows;
t-SNE perplexity `min(30, (n − 1) / 3)`.

**Output.** `occupational_segments.parquet`, `segment_profiles.csv`,
`segment_projection.parquet`, `clustering_comparison.json`,
`segment_projection_tsne.parquet`.

## 9. Salary band model

**Why.** Postings publish official bands, not exact salaries, and many
publish none; a band can be estimated from the text.

**How.** The midpoint of `salary_min`/`salary_max` (kept only between
500,000 and 60,000,000 COP) only locates the posting inside one of six
bands aligned with the SPE: up to $1.5M, $1.5–2M, $2–3M, $3–4M, $4–6M, more
than $6M. It is never shown as a salary. A multinomial logistic regression
over TF-IDF plus one-hot source, department, contract, modality and
education predicts the band. Stratified K-fold reports accuracy, macro-F1 and
"within one band" next to a majority-class baseline; read them together.

**Parameters.** `LogisticRegression(C=2.0, max_iter=2000)`; 2–5 folds
depending on the smallest class; cross-validation on at most 100,000 seeded
rows, final model on every labeled row; fewer than 30 labeled postings skip
the stage with a reason in the manifest.

**Output.** `supervised_metrics.json`, `salary_estimates.parquet`,
`salary_model.joblib`.

## 10. Skills graph and transition routes

**Why.** Skills asked together reveal families of skills and the paths
between occupations.

**How.** Two skills are linked when the same posting asks for both; the edge
weight is the number of such postings. Louvain finds communities by
maximizing modularity `Q`; PageRank and sampled betweenness rank central and
bridging skills. Each segment gets a skill profile (share and lift of each
skill inside it); segments link to their most similar segments by profile
cosine, and Dijkstra over `1 − similarity` gives the transition routes the CV
flow shows as pivots.

**Parameters.** Top 400 skills as nodes, edges with ≥ 2 shared postings,
3 neighbour segments, Louvain `seed=42`.

**Output.** `segment_skills.parquet`, `skill_graph_nodes.parquet`,
`skill_graph_edges.parquet`, `graph_metrics.json`,
`segment_transitions.parquet`.

## 11. CV matching, niches, pivots and gaps

**Why.** The product question: which vacancies does this profile resemble,
where does it fit and what is missing.

**How.** `api/cv.py` extracts text from PDF, DOCX or TXT in memory (5 MB
limit) and discards it with the response. The CV goes through the same TF-IDF
vectorizer and ESCO matcher. For each posting:

```
match = ½ · cos(cv, v) / max_v cos(cv, ·)  +  ½ · |S_cv ∩ S_v| / |S_v|
```

(text only when the posting has no skills). Segment affinity mixes the
relative centroid cosine with share-weighted skill coverage; the top three
are the niches, other segments with at least half the best affinity are the
pivots, each with its Dijkstra route. Gaps are skills asked by at least 15% of
a segment's postings that the CV does not mention. The salary estimate uses
the band model.

**Parameters.** 20 matches, 3 niches, 3 pivots, gap share ≥ 0.15.

**Output.** The `/api/cv/match` response; nothing is stored.

## 12. Validation

**Why.** ESCO matches, duplicates and segments are analytical signals, not
labels, until people check them.

**How.** `python -m sextante.analytics review <run_dir>` writes review CSVs
(ESCO mentions, duplicate pairs, segment assignments) with an empty
`is_correct` column; reviewers open the URL and fill it.
`python -m sextante.analytics evaluate <run_dir>/review` reports precision
with a Wilson 95% interval.

## Not in the batch

Word2Vec and UMAP stay notebook-only (`notebooks/`); sentence embeddings are
optional (`backend/requirements/embeddings.txt`, `--embeddings`). Apache
Spark is not needed at the current volume.
