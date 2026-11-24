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
| 10 | [Skills graph and transition routes](#10-skills-graph-and-transition-routes) | Gold | `analytics/graph.py`, `api/skill_insights.py` |
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

The dashboard (`api/insights.py`) summarizes the whole skill graph (`N` nodes,
`E` edges): density `2E / (N(N − 1))`, average degree `2E / N` and unweighted
average clustering (networkx); the 10 skills with most neighbours (degree,
ties by weighted degree) as *transversal*, the 10 with highest betweenness as
*bridges*, and each community's size and 3 most demanded skills.

**Skill insights** (`api/skill_insights.py` and `api/skill_cooccurrence.py`,
dashboard `skill_insights`, `community_validation` and the extended `topics`).
Computed over the full run when the dashboard is built, on a posting × skill
incidence of the graph nodes. They are associations between skills, segments
and salary bands, never causal effects. Three corrections come first, because
on the real corpus raw co-occurrence was dominated by synonyms, by templates
posted thousands of times and by rare skills:

- *Label merge*: graph skills whose labels normalize to the same text
  (casefold, accents and punctuation dropped, spaces collapsed; the ESCO
  matcher's `normalize_text`) are one skill, represented by the URI with most
  postings. A posting asking for two merged URIs counts once.
- *Posting dedupe*: `postings.parquet` has no description and the run's
  duplicate pairs are a capped sample, so postings are collapsed on stable keys
  (first occurrence kept). With ≥ 4 skills (`TEMPLATE_MIN_SKILLS`), a posting
  is a copy of any earlier one with the identical skill set, whatever its title
  or company: an exact combination of four or more skills repeated is a
  reposted template, not independent demand (on the real corpus one template
  was reposted ~971 times with changing title *and* company, and its skills
  filled the pair list). With 3 skills a copy needs the same skill set and the
  same normalized title, or the same skill set and the same known company;
  with fewer skills a copy needs the same title, company and skill set (short
  profiles are too common to collapse on skills alone). Pairs, salary, niches,
  pivots, kinds, focus segments and communities use the deduplicated postings
  (`N` of them, `n_A` asking for skill `A`, `n_AB` for both); the table's
  demand (`postings`, `share`) and topic profiles count every posting.
- *Generic skills*: asked by ≥ 5% of the deduplicated postings
  (`GENERIC_MIN_SHARE`; on the real corpus: técnicas de venta, servicio al
  cliente, comunicación, trabajar en equipos, gestionar el inventario,
  logística, hojas de cálculo). They are left out of pivots and of the PMI
  community graph.
- *Redundant pairs*: two skills are the same concept, and never form a pair, a
  niche partner, a salary complement or a PMI-graph edge, when one normalized
  label contains the other as whole words (`dermatología` / `dermatología y
  venereología`) or they share an alias in the API matcher (one phrase matched
  both, e.g. `CSS`).

Definitions:

- *Lift* `= P(A∩B) / (P(A)·P(B)) = n_AB · N / (n_A · n_B)`; *PMI* `= log₂(lift)`
  (0 = independent, > 0 = asked together more than chance); *NPMI* `= PMI /
  −log₂ P(A∩B)`, in `[−1, 1]` (1 = always together). Raw PMI favours rare
  skills (a pair seen 159 times reached lift 3,504); NPMI corrects that.
  `pairs` lists the 15 pairs with highest NPMI (ties: more postings together)
  among those with `n_AB ≥ 50`, `n_A, n_B ≥ 200` and NPMI > 0; each keeps
  `lift` and `pmi = log₂(lift)`.
- *Segment share* of a skill = share of a segment's deduplicated postings
  asking for it; *segment lift* = segment share / share in all deduplicated
  postings (the `segment_skills.lift` definition, on deduplicated postings and
  merged skills). *Top segment share* = share of the skill's deduplicated
  postings inside its most common K-Means segment. *Breadth* = number of
  segments where the skill's segment lift is ≥ 1 (asked at least as often as in
  the corpus). *Kind*: `especializada` when the top segment share is ≥ 0.60;
  otherwise `transversal` when breadth ≥ 0.40 × number of segments
  (`TRANSVERSAL_MIN_SEGMENT_FRACTION`); `intermedia` otherwise. Graph degree is
  not used: the co-occurrence graph is dense and degree mostly tracks
  frequency, which labelled spread-out but profile-specific skills (payroll,
  social security law) as transversal. `table` shows the 30 most demanded
  merged skills with their kind; `core` ("núcleo duro") the 10 with highest
  PageRank.
- *Pivots*: for every direct segment link (both directions), over non-generic
  skills only. `missing` = up to 5 skills with target share ≥ 0.05
  (`PIVOT_MIN_SHARE`), target lift ≥ 1.5 (`PIVOT_MIN_LIFT`) and origin share
  ≤ 0.5 × target share (`PIVOT_MISSING_MAX_RATIO`), ranked by target share.
  `shared` = up to 5 skills with share ≥ 0.05 in both segments that are not
  `missing`, ranked by the smaller of the two shares (no lift requirement:
  the earlier "distinctive in both" rule left `shared` empty for every pair on
  the real corpus). The old exclusion (transversal + core + 20 most frequent)
  is replaced by the generic share rule; it dropped contabilidad,
  electricidad, mecánica or nóminas, which tell profiles apart.
- *High salary* = band lower bound ≥ $2M (the dashboard's "$2M o más"), over
  deduplicated postings (so `overall_high_share` can differ slightly from the
  salary panels, which count every posting). For skills with ≥ 100 banded
  postings, high share = high / banded and lift = high share / overall high
  share; `top` and `bottom` show 8 each (disjoint). *Salary boost*: anchors
  are skills with ≥ 300 banded postings and a high share below the overall
  one; for each, the complement `B` (≥ 150 banded postings with both, not a
  synonym) whose combination has the largest high share, kept when it beats
  the anchor alone by ≥ 5 points; up to 8, largest anchors first.
- *Niche*: skills with ≥ 100 deduplicated postings, degree at or below the
  25th percentile and top segment share ≥ 0.60 (up to 10, most concentrated
  first), each with the partner of highest NPMI among skills with `n_AB ≥ 20`
  (`NICHE_PARTNER_MIN_TOGETHER`), partner in ≥ 50 deduplicated postings
  (`NICHE_PARTNER_MIN_MARGINAL`), not redundant and NPMI > 0; `partner_lift`
  is that pair's lift. These floors are lower than the pair list's (50 / 200)
  because a niche skill rarely reaches them: with the pair floors
  neonatología, pediatría or medicina intensiva had no partner.
- *Community validation*: Louvain (`seed=42`) on a sparse NPMI graph over the
  merged, non-generic skills. Generic skills are removed before building the
  graph, the usual step in co-occurrence community detection (frequent,
  context-free terms are the noise the PMI filter targets): they are asked
  together with every family, so they form one hub that absorbed 12 of 16
  segments and gave Q ≈ 0.076. `Q` is reported as it comes out, not tuned. An
  edge needs NPMI ≥ 0.10, `n_AB ≥ 30` and two distinct
  concepts, and is kept when it is among the 10 strongest qualifying edges of
  either endpoint; skills with no edge are left out. Weight = NPMI: counts
  would let frequent skills dominate again (that is the co-occurrence graph
  this one validates), while NPMI is bounded and frequency-free. NPMI ≥ 0.10
  is a clearly positive association: lift ≥ ~2.6 for a pair seen 30 times in
  ~400k postings, ≥ ~1.5 for one seen 5,000 times. The top-k cap keeps the
  graph sparse (a positive-PMI graph over 400 skills was nearly complete,
  ~59k edges, Q ≈ 0.005, one community of 279 skills). Thresholds are fixed
  by these rules, not tuned to a target `Q`. It reports edges, communities
  (size, 3 skills with most postings) and modularity; each segment's skill
  mass (sum over the community's skills of their share of the segment's
  postings) is spread over those communities, giving the dominant one, its
  share and how many hold ≥ 10%. A segment concentrated in one PMI community
  is coherent in skills; a spread one mixes skill families.
- *Topic profiles* (needs `topic_assignments.parquet`): postings and share per
  NMF topic, its 3 most common cleaned titles, 2 most common segments and the 4
  skills with highest lift inside the topic among those in ≥ 10% of its
  postings (`TOPIC_SKILL_MIN_SHARE`; at 5% rare skills with huge lift, such as
  aprendizaje automático in a management topic, took the list). A title counts
  only if it reads as a job title: no template placeholder (`$`, `{`, `}`), at
  least 3 characters, at least half of its non-space characters letters, and
  one word of ≥ 3 letters. This drops `$hno codigo vacante$obrero` or
  `12345-678`; a wordy non-title such as `Firma contrato al día 3` still
  passes (no general rule tells it apart without a blacklist).

**Parameters.** Top 400 skills as nodes, edges with ≥ 2 shared postings,
3 neighbour segments, Louvain `seed=42`; skill-insight thresholds are the
named constants at the top of `api/skill_insights.py` and
`api/skill_cooccurrence.py` (values above).

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

At runtime no ESCO file is needed: the matcher is rebuilt from the aliases
seen in the corpus (`matcher_from_mentions`). The match % is a ranking
heuristic, not a calibrated probability; the salary estimate returns a band
and the model's probability, never an exact amount. Every match carries the
posting `url` so the person can apply at the source.

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

## Limitations

- ESCO extraction is exact phrase/alias matching, extended with a curated
  Colombian synonym list (`backend/src/sextante/analytics/synonyms_es.csv`: synonym →
  ESCO preferred label, resolved against the loaded CSV; unknown labels are
  skipped). Count and hash are recorded in the manifest. On a sample
  posting it raised detected skills from 4 to 10; extend the list as manual
  review finds misses.
- Without the synonyms, ESCO extraction is exact phrase/alias matching. It is transparent and
  inexpensive, but does not resolve context, abbreviations, or Colombian
  terminology absent from ESCO.
- ESCO matches, topics, and clusters are analytical signals, not validated
  labels. Evaluate them against a manually reviewed sample before product
  decisions.
- The first version recomputes one full snapshot in memory. Measure peak
  memory and duration on the private corpus before adding a schedule or
  incremental feature store.
- Word2Vec and UMAP remain notebook-only. Hierarchical clustering, DBSCAN and
  t-SNE run in batch on a bounded sample for comparison; K-Means stays the
  published segmentation.
- Salary models only see postings that publish a salary (mostly SPE); their
  estimates for other sources are extrapolations.

## Not in the batch

Word2Vec and UMAP stay notebook-only (`notebooks/`); sentence embeddings are
optional (`backend/requirements/embeddings.txt`, `--embeddings`). Apache
Spark is not needed at the current volume.
