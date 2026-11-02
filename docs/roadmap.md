# Roadmap — done and pending

> [README](../README.md) · Last update: 2026-11-01

## Done

| Stage | Where | Notes |
|---|---|---|
| 1 · Capture | `pipeline/`, workflows | SPE every 12 h, JobSpy every 30 min → HF |
| 2 · Text mining | `sextante_analysis/` | EDA, ESCO exact matching, MinHash duplicate candidates |
| 3 · Representations | `features.py` | TF-IDF, NMF topics, optional multilingual embeddings |
| 4 · Segmentation | `features.py`, `comparison.py` | K-Means published; Ward/DBSCAN/t-SNE compared |
| 5 · Supervised | `supervised.py` | Salary regression + salary-band classifier, CV vs baselines |
| 6 · Graph | `graph.py` | Skill communities/centrality, segment transition routes |
| 8 · MVP | `sextante_api/`, `web/` | Dashboard (3 perspectives + market map), CV matching with links, niches, pivots, gaps |
| Quality | `tests/`, `tests.yml` | 81 tests + ruff in CI; demo run for end-to-end checks |

Verified on a synthetic demo run only (tests, `next build`, manual browser
check of dashboard and CV flow). **No run on the real corpus yet.**

## Status 2026-11-01

- ESCO v1.2.1 Spanish skills CSV downloaded and validated locally
  (13,939 skills, sha256 `30b1271f…`). Curated synonym list added.
- ESCO published as GitHub release `taxonomy-esco-v1.2.1`; the analytics
  workflow downloads and verifies it, so the real run is unblocked.

### Trial runs on the real corpus (GitHub runner, `upload=false`)

| Limit/dataset | Rows | Wall time | Peak RSS | Skill mentions | Salary MAE (baseline) | Band accuracy (baseline) | K-Means silhouette (SVD-50 sample) |
|---|---|---|---|---|---|---|---|
| 3,000 | 6,000 | 1 min 16 s | 7.7 GB | 19,470 | 0.70 M (1.06 M) COP | 0.80 (0.49) | 0.18 |
| 30,000 | 33,039 | 4 min 00 s | 8.0 GB | 83,729 | 0.45 M (0.66 M) COP | 0.84 (0.60) | 0.15 |
| **full (published)** | **481,597** | **29 min 51 s** | **13.0 GB** | **1,195,358** | **0.39 M (0.61 M) COP** | **0.87 (0.61)** | **0.13** |

First published run: `derived/runs/20261101T170836441392Z-cd50c976`
(corpus revision `cd50c976`, 2026-11-01), `derived/latest.json` points to it.
Salary regression median absolute error is 9%; 372,660 postings have a
usable salary. Peak memory (13.0 GB) uses ~80% of the 16 GB runner: the
corpus grows daily, so reduce memory (stream partitions, drop descriptions
after vectorizing, cap bigram vocabulary) before scheduling the run. Silhouette on the full
sparse TF-IDF is ~0.01 (normal for high-dimensional sparse text); segment
quality must be judged by reading segment terms and manual review.

## Pending (in order)

1. ~~**Real corpus run**~~ — done 2026-11-01 (see table above). Re-run with
   **Actions → Analytics run (manual)** after tuning. The step summary reports duration
   and peak memory: copy them here. (Locally:
   `HF_TOKEN=... python -m sextante_analysis run --esco-csv skills_es.csv --upload`.)
2. **Tune on real data** — check `supervised_metrics.json` beats baselines,
   pick `--clusters` from silhouette/`clustering_comparison.json`, read the
   segment terms and adjust cluster count/stop words if segments are noisy.
3. **Manual validation** — `python -m sextante_analysis review <run_dir>`,
   have the team label the CSVs (≈ 450 rows), then `evaluate`; report
   precision ± CI in the course document. Human work.
4. **Deploy** — API on Render (free, `render.yaml`, serving bundle) + web on
   Vercel (root `web/`), see [mvp.md](mvp.md#deployment). Serving bundle of
   run `20261101T170836441392Z-cd50c976` is published; Render service and
   Vercel project are being set up.
5. **Optional improvements**
   - Grow `synonyms_es.csv` with misses found in manual review.
   - Use sentence embeddings in CV matching when `--embeddings` was run.
   - Schedule the analytics run (weekly workflow) once (1) shows it fits a
     GitHub runner's time/memory.
   - Stage 7 (Spark): not needed while a full run fits in memory; revisit
     only if (1) shows otherwise.
   - Word2Vec/UMAP into batch if the course evaluation requires them there.
