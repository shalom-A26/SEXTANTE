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
| Quality | `tests/`, `tests.yml` | 80 tests + ruff in CI; demo run for end-to-end checks |

Verified on a synthetic demo run only (tests, `next build`, manual browser
check of dashboard and CV flow). **No run on the real corpus yet.**

## Pending (in order)

1. **Real corpus run** — download the ESCO v1.2.1 Spanish skills CSV
   (official portal) and run
   `HF_TOKEN=... python -m sextante_analysis run --esco-csv skills_es.csv --upload`.
   Record duration and peak memory (`/usr/bin/time -v`) in this file.
   Needs the token and the CSV (not in the repo).
2. **Tune on real data** — check `supervised_metrics.json` beats baselines,
   pick `--clusters` from silhouette/`clustering_comparison.json`, read the
   segment terms and adjust cluster count/stop words if segments are noisy.
3. **Manual validation** — `python -m sextante_analysis review <run_dir>`,
   have the team label the CSVs (≈ 450 rows), then `evaluate`; report
   precision ± CI in the course document. Human work.
4. **Deploy** — API + web as described in [mvp.md](mvp.md#deployment-not-done-yet).
   Needs hosting accounts and a read-only HF token.
5. **Optional improvements**
   - Spanish synonyms/abbreviations for ESCO matching (e.g. "BI", "NIIF").
   - Use sentence embeddings in CV matching when `--embeddings` was run.
   - Schedule the analytics run (weekly workflow) once (1) shows it fits a
     GitHub runner's time/memory.
   - Stage 7 (Spark): not needed while a full run fits in memory; revisit
     only if (1) shows otherwise.
   - Word2Vec/UMAP into batch if the course evaluation requires them there.
