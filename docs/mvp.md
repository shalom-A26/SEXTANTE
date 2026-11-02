# Stage 8 — MVP (API + web app)

> [README](../README.md) · [Analytics](analytics.md) · [Roadmap](roadmap.md)

## Components

| Part | Path | Role |
|---|---|---|
| API | `sextante_api/` (FastAPI) | Loads one analytics run into memory; serves dashboard aggregates and scores CVs |
| Web | `web/` (Next.js 16, React 19, Tailwind v4 + shadcn/ui, GSAP) | Landing, dashboard with three perspectives, CV flow |

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

## Docker

```bash
docker build -t sextante-api .
docker run -p 8000:8000 -e SEXTANTE_HF_REPO=pxtron/vacantes-colombia \
  -e HF_TOKEN=<read-only token> -e SEXTANTE_CORS_ORIGINS=https://<web-domain> sextante-api
```

Without `SEXTANTE_HF_REPO` the container builds and serves a synthetic demo
run.

## Web: components and motion

- **shadcn/ui** (`web/components/ui/`, radix-nova style). Its CSS variables are
  mapped to the dusk palette in `app/globals.css`. The page's own tokens are
  prefixed `--sx-*` so they don't collide with shadcn's `--muted`,
  `--accent` and `--radius`. The hand-written CSS stays unlayered so it wins
  over Tailwind's preflight.
- **GSAP** (`web/components/motion/`). It registers ScrollTrigger,
  ScrollToPlugin, ScrambleText, SplitText and DrawSVG once and exports these primitives:
  `Reveal`, `SplitHeading`, `CountUp` and `Magnetic`.
- **Landing.** One orchestrated entrance: the dusk settles, the grass grows,
  the title rises word by word, the sextant draws itself and the figure
  lights up. After that the grass sways in the wind, the needle drifts and
  the scene follows the mouse with depth. On scroll, the statement lights up
  word by word.
- **"Cómo funciona"** (`web/components/how-it-works/`). A scroll walkthrough
  of the nine real stages: capture, cleaning, ESCO skills, duplicates,
  TF-IDF, segments, salary, graph and CV. `steps.ts` holds each stage's
  explanation, what happens inside, its algorithm (formula or pseudocode) and
  live figures read from `/api/dashboard`. `visuals.tsx` holds one animated
  scene per stage. The scene sits in a sticky frame on wide screens and
  changes as each step crosses the viewport. On narrow screens, or with
  reduced motion, each static scene sits above its text.
- **System backdrop** (`web/components/system-backdrop.tsx`). A fixed, faint
  layer behind every page: rows of top skills, segment names and pipeline
  terms drifting by, plus a skill-graph constellation with scroll parallax.
  It is decorative (`aria-hidden`, no pointer events) and pauses while the
  tab is hidden.
- **One dashboard request.** `getDashboard()` memoizes its promise, so the
  hero, backdrop, walkthrough and dashboard share a single fetch.
- **Logo:** `docs/assets/logo.svg`, also used as the favicon
  (`web/app/icon.svg`).
- **Dashboard and CV.**
  - KPIs count up and bars grow.
  - The graph draws its edges.
  - Tabs have a sliding indicator.
  - Results cascade in and meters fill up.
- **Page transitions:** a veil in `app/template.tsx`.
- **Reduced motion:** everything runs inside
  `gsap.matchMedia("(prefers-reduced-motion: no-preference)")`. With reduced
  motion the page is static and complete. Mouse parallax runs only with a
  fine pointer.

## Deployment

Free hosting has ~512 MB of RAM; the API over the full run needs ~2.5 GB.
Each analytics run therefore also writes a **serving bundle**
(`derived/runs/<run_id>/serving/`, ~32 MB, built by `sextante_api/serving.py`;
for an existing run: `python -m sextante_api.serving <run_dir>`):

- the dashboard payload precomputed over the whole corpus (all figures stay
  corpus-wide), segment names/sizes/median salaries and centroids;
- every ESCO alias seen, so CV skill detection keeps the full vocabulary;
- the 40,000 most recently captured postings for CV matching (recent ones
  are the most likely to still accept applications).

With `SEXTANTE_SERVING=1` the API downloads only that bundle: ~390 MB peak
RSS, CV match in ~30 ms. Arrow uses the system allocator
(`ARROW_DEFAULT_MEMORY_POOL=system`, set in the `Dockerfile`); its default
pools keep ~150 MB of freed buffers.

- **API: Render** (free web service, `render.yaml` blueprint): New →
  Blueprint → this repo; enter `HF_TOKEN` (read access to the dataset) when
  asked. CORS allows `http://localhost:3000` and any `https://*.vercel.app`
  (`SEXTANTE_CORS_ORIGINS`, `SEXTANTE_CORS_ORIGIN_REGEX`). The free instance
  sleeps after 15 min idle; the first request then takes ~1 min.
- **Web: Vercel**, root directory `web/`, env `NEXT_PUBLIC_API_URL` = the
  Render URL (build-time variable: redeploy after changing it).
- Hugging Face Docker Spaces were the first choice but now require a PRO
  subscription.
