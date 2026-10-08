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

TF-IDF and NMF use title plus description. K-Means is seeded and its
cosine silhouette is computed on at most 5,000 evenly selected rows. The
duplicate search uses MinHash locality-sensitive hashing to generate a
bounded candidate set (up to 20 candidates per posting), followed by exact
word n-gram TF-IDF cosine similarity. The default review threshold is 0.90;
pair generation is capped at 500,000 pairs per run.
This approximation can miss pairs and its output requires human review.

## Current limitations

- ESCO extraction is exact phrase/alias matching. It is transparent and
  inexpensive, but does not resolve context, abbreviations, or Colombian
  terminology absent from ESCO.
- ESCO matches, topics, and clusters are analytical signals, not validated
  labels. Evaluate them against a manually reviewed sample before product
  decisions.
- The first version recomputes one full snapshot in memory. Measure peak
  memory and duration on the private corpus before adding a schedule or
  incremental feature store.
- Word2Vec, t-SNE, UMAP, hierarchical clustering, and DBSCAN are limited to
  small notebook comparisons. The batch contract uses the smaller
  reproducible baseline until corpus evaluation supports more methods.
- The batch command is the backend foundation. It does not expose an API or
  dashboard yet.

