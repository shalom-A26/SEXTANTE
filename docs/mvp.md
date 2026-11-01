# Stage 8 — MVP (API + web app)

> [README](../README.md) · [Analytics](analytics.md) · [Roadmap](roadmap.md)

## Components

| Part | Path | Role |
|---|---|---|
| API | `sextante_api/` (FastAPI) | Loads one analytics run into memory; serves dashboard aggregates and scores CVs |
| Web | `web/` (Next.js 16, React 19, no UI framework) | Landing, dashboard with three perspectives, CV flow |

## Running locally

```bash
uv pip install -r requirements-api.txt
python -m sextante_analysis demo          # or a real run, or SEXTANTE_HF_REPO
uvicorn sextante_api.main:app --port 8000
cd web && cp .env.example .env.local && npm install && npm run dev
```

The API picks its run from `SEXTANTE_RUN_DIR`, else the newest run under
`SEXTANTE_RUNS_ROOT` (default `data/analysis/runs`), else downloads
`derived/latest.json` from `SEXTANTE_HF_REPO` (needs `HF_TOKEN`).
`SEXTANTE_CORS_ORIGINS` (comma-separated, default `http://localhost:3000`)
must list the web origin. The web app reads `NEXT_PUBLIC_API_URL` at build
time.

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | Run ID and posting count |
| GET | `/api/dashboard` | Overview KPIs, segments (salary, skills, modality, cities), top skills, skills by education level, salary by department and model metrics, skills graph, segment links, 2D projection, clustering comparison |
| GET | `/api/segments/{id}/postings` | Sample postings of a segment, with links |
| POST | `/api/cv/match` | Multipart: `file` (PDF/DOCX/TXT ≤ 5 MB) or `text`; optional `city`, `modality`, `limit` |

## CV matching method

1. Text is extracted **in memory**; the CV is never written, logged or stored.
2. ESCO skills are read with a matcher rebuilt from the aliases seen in the
   corpus (`matcher_from_mentions`), so no ESCO file is needed at runtime.
3. The CV is projected with the run's fitted TF-IDF vectorizer.
4. **Match %** per posting = 50% TF-IDF cosine relative to the best posting
   for this CV + 50% share of the posting's ESCO skills covered by the CV
   (text only when the posting has no detected skills). It is a ranking
   heuristic, not a calibrated probability.
5. **Segment affinity** = 50% relative cosine to the segment centroid + 50%
   share-weighted coverage of the segment's skills. The top three are
   "niches"; other segments with at least half the best affinity are
   "pivots", shown with their transition route and **skill gaps** (segment
   skills present in ≥ 15% of its postings that the CV lacks).
6. The salary estimate uses the Stage 5 models on the CV vector.

Every match carries the posting `url` so the person can apply at the source.

## Deployment (not done yet)

- Web: Vercel (root `web/`, env `NEXT_PUBLIC_API_URL`).
- API: any container host with ~1–2 GB RAM for the full corpus run (Render,
  Fly.io, Railway, a university VM). Start command
  `uvicorn sextante_api.main:app --host 0.0.0.0 --port $PORT`, env
  `SEXTANTE_HF_REPO`, `HF_TOKEN` (read-only token), `SEXTANTE_CORS_ORIGINS`.
