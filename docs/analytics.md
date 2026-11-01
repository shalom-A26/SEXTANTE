# Batch analytics

> [README](../README.md) · [System architecture](architecture.md)

The analysis package reads a fixed revision of the private Hugging Face
corpus and writes derived artifacts separately from the canonical 17-column
partitions. It never edits or republishes source rows. Capture remains
independent and does not install the scientific dependencies.

## Setup

Use Python 3.12, as configured in the capture workflows, and install the
analysis and development stack:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

Download the **ESCO v1.2.1 classification** in Spanish and CSV format from
the [official ESCO download portal](https://esco.ec.europa.eu/en/use-esco/download).
The CSV should include `conceptUri`, `preferredLabel`, and, when available,
`altLabels` and `conceptType`. Keep the taxonomy file out of Git and record
its SHA-256 in every analysis manifest.

Run the complete batch analysis with access to `pxtron/vacantes-colombia`:

```bash
export HF_TOKEN=...
python -m sextante_analysis run --esco-csv /path/to/skills_es.csv
```

The run pins the Hugging Face revision before downloading partitions. Use
`--limit 3000` for a deterministic demonstration capped at 3,000 rows from
each dataset, `--upload` to publish
results, or `--embeddings` to additionally compute multilingual sentence
embeddings. Embeddings require the optional dependencies:

```bash
uv pip install -r requirements-embeddings.txt
```

The embedding model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
at revision `b8ef00830037f9868450f778081ea683e900fe39`; it is multilingual and
Apache-2.0 licensed. Embeddings are disabled by default because they add model
downloads, compute time, and storage. `notebooks/01_text_mining_and_segments.ipynb`
is the mini demonstration for the course presentation. It includes optional
small-sample Word2Vec, UMAP, t-SNE, hierarchical, and DBSCAN comparisons.
It runs on synthetic data by default; set `SEXTANTE_USE_HF=1` to use a
private-corpus sample. The full dependency set is installed by
`requirements-dev.txt`.

Execute the complete notebook offline; it uses a generated synthetic sample
unless `SEXTANTE_USE_HF=1` is set:

```bash
.venv/bin/jupyter nbconvert --to notebook --execute \
  --output-dir /tmp/sextante-notebook-run notebooks/01_text_mining_and_segments.ipynb
```

### Running on GitHub Actions

`.github/workflows/analytics.yml` (manual, `workflow_dispatch`) runs the same
command on a GitHub runner with the repository's `HF_TOKEN` secret and
reports wall time and peak memory in the step summary. The ESCO CSV comes
from the GitHub release
[`taxonomy-esco-v1.2.1`](https://github.com/shalom-A26/SEXTANTE/releases/tag/taxonomy-esco-v1.2.1)
(unmodified official files with EU attribution, verified by SHA-256); set
`esco_source=hf` to read it from the dataset instead.

```bash
gh workflow run analytics.yml -f limit=3000 -f upload=false   # trial
gh workflow run analytics.yml                                 # full run + upload
```

Locally: `gh release download taxonomy-esco-v1.2.1 -p skills_es.csv`.

## Batch behavior and outputs

The CLI reads all SPE and JobSpy Parquet partitions from one repository
revision. It creates `data/analysis/runs/<run_id>/` locally. With `--upload`,
the run is uploaded to `derived/runs/<run_id>/` in the same private dataset;
`derived/latest.json` is updated only after the complete run upload succeeds.
The existing capture workflow uploads only `data/spe/`, `data/jobspy/`, and
the dataset card, so it does not overwrite derived outputs.

Each run includes:

| Artifact | Contents |
|---|---|
| `manifest.json` | Corpus revision, input partitions, ESCO version/hash, parameters, counts, model identifiers, artifact hashes |
| `eda.json` | Missingness, description coverage and length, source/category counts, salary quantiles, date coverage |
| `skill_mentions.parquet` | Vacancy/source/URL, ESCO concept URI and label, matched phrase |
| `duplicate_candidates.parquet` | Similarity-ranked review pairs; no automatic deletion or merging |
| `topics.csv`, `topic_assignments.parquet` | NMF topic terms and per-posting topic assignment/weight |
| `occupational_segments.parquet`, `segment_profiles.csv` | K-Means group assignments and representative terms |
| `segment_projection.parquet` | Two-dimensional TruncatedSVD coordinates (sparse PCA approximation) and group ID |
| `tfidf_matrix.npz`, `tfidf_vocabulary.json`, `tfidf_idf.npy` | TF-IDF representation and vocabulary information for later consumers |
| `sentence_embeddings.npy` | Optional normalized multilingual embeddings |
| `postings.parquet`, `tfidf_vectorizer.joblib` | Posting metadata row-aligned with the TF-IDF matrix (no description) and the fitted vectorizer, used by the API to score CVs |
| `clustering_comparison.json`, `segment_projection_tsne.parquet` | Stage 4: K-Means vs Ward hierarchical vs DBSCAN on a 3,000-row SVD-50 sample (silhouette, noise, ARI vs published K-Means) and a t-SNE projection |
| `supervised_metrics.json`, `salary_estimates.parquet`, `salary_model.joblib` | Stage 5: Ridge regression on log monthly salary and a salary-tertile classifier, K-fold metrics next to naive baselines; per-posting estimates |
| `segment_skills.parquet` | Share and lift of each ESCO skill inside each segment |
| `skill_graph_nodes.parquet`, `skill_graph_edges.parquet`, `graph_metrics.json` | Stage 6: skill co-occurrence graph (top 400 skills, edges ≥ 2 shared postings), Louvain communities, PageRank, sampled betweenness |
| `segment_transitions.parquet` | Segment graph (3 nearest neighbours by skill-profile cosine) and all-pairs shortest transition routes |

TF-IDF and NMF use title plus description. K-Means is seeded and its
cosine silhouette is computed on at most 5,000 evenly selected rows. The
duplicate search uses MinHash locality-sensitive hashing to generate a
bounded candidate set (up to 20 candidates per posting), followed by exact
word n-gram TF-IDF cosine similarity. The default review threshold is 0.90;
pair generation is capped at 500,000 pairs per run.
This approximation can miss pairs and its output requires human review.

## Stages 5 and 6

**Salary models.** The target is the midpoint of `salary_min`/`salary_max`,
kept only inside 500,000–60,000,000 COP/month (outside that range values are
parsing artifacts). Features are the run's TF-IDF plus one-hot `source`,
`department`, `contract_type`, `work_modality` and `education_level`.
`Ridge` is fitted on log salary; `LogisticRegression` predicts the salary
tertile (bajo/medio/alto). Both report K-fold metrics next to a naive
baseline (median / majority class) — read them together. Fewer than 30
labeled postings skip the stage with a reason in the manifest.

**Graph.** Skills are linked when they appear in the same posting; Louvain
(seed 42) finds communities and PageRank/betweenness rank central skills.
Segments are linked to their three most similar segments by skill profile;
shortest paths on `1 − similarity` are the transition routes that the CV
flow shows as "pivots".

## Demo run and manual validation

`python -m sextante_analysis demo` generates a synthetic corpus (flagged as
`synthetic-demo` in the manifest, never uploaded) and runs every stage, so
the API and web app work in a clean clone.

`python -m sextante_analysis review <run_dir>` writes review CSVs (ESCO
mentions, duplicate pairs, segment assignments) with an empty `is_correct`
column; reviewers open the `url` and fill it (`sí`/`no`).
`python -m sextante_analysis evaluate <run_dir>/review` reports precision
with a Wilson 95% interval.

## Current limitations

- ESCO extraction is exact phrase/alias matching, extended with a curated
  Colombian synonym list (`sextante_analysis/synonyms_es.csv`: synonym →
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
- The API and web app consume these artifacts; see [mvp.md](mvp.md).

