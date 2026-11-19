# CLAUDE.md

Read [`AGENTS.md`](AGENTS.md) first: it holds the rules, commands, known traps and the
docs-sync table, and wins if anything here disagrees. This file adds stack and library notes
for Claude Code; keep both consistent when either changes.

## Stack decisions

- **Python** ≥ 3.10 (CI and Docker use 3.12), managed with `uv`. Dependencies are pinned in
  `backend/requirements/*.txt` (`base` ⊂ `analysis` ⊂ `api`; `dev`, `notebooks`, `embeddings`
  on top); `backend/pyproject.toml` only makes `sextante` installable and configures ruff.
  Tests use `unittest` (not pytest). Imports are absolute (`from sextante.core import env`).
- **Capture**: `python-jobspy` for job boards (LinkedIn, Indeed, Bayt), the SPE async CSV
  export through `requests`. Parquet with pandas + pyarrow.
- **Analytics**: scikit-learn (TF-IDF, NMF, TruncatedSVD, K-Means, Ward, DBSCAN, t-SNE,
  LogisticRegression), `datasketch` MinHash LSH, networkx (Louvain, PageRank, betweenness),
  ESCO v1.2.1 Spanish CSV from the `taxonomy-esco-v1.2.1` GitHub release (SHA-256 checked).
- **API**: FastAPI + uvicorn; loads one run in memory. On Render it downloads only the
  `serving/` bundle (`SEXTANTE_SERVING=1`) to fit 512 MB; Arrow uses the system allocator.
- **Frontend**: Next.js 16 (App Router, Turbopack) + React 19 + TypeScript, Tailwind v4 with
  shadcn/ui, GSAP (ScrollTrigger, SplitText, DrawSVG; registered once in
  `components/motion/gsap.ts`) and three.js (`components/world/`).

## Library notes

- **Next.js 16** differs from older versions: check `frontend/node_modules/next/dist/docs/`
  before using an API. `next dev` writes a `frontend/AGENTS.md` with the same hint; it is
  gitignored, do not commit it. `next build` may stop once to print a security advisory;
  rerunning continues.
- **GSAP**: wrap animations in `gsap.matchMedia().add(MOTION_OK, …)` so reduced motion gets the
  static page. In development `window.gsap` is exposed for browser automation; slow headless
  WebGL (~2 fps) stalls GSAP's lag smoothing, so call `gsap.ticker.lagSmoothing(0)` when testing.
- **three.js**: the world is client-only (`dynamic(..., { ssr: false })`) and pauses off
  screen; fixed overlays (intro) are portaled to `<body>` because the page transition must not
  transform fixed layers.
- **Fonts**: Boska and Switzer come from the Fontshare CDN (`<link>` in `app/layout.tsx`);
  Fragment Mono from `next/font/google`.
- **Web guide** (`components/guide/pipeline.ts`): a TypeScript mirror of the Python techniques;
  if you change a technique in `backend/`, update the mirror and run
  `node frontend/scripts/check-guide.ts`.
- **Hugging Face**: the dataset is private; scripts read `HF_TOKEN` from `.env` at the repo root
  (exported values win). Never print it.
