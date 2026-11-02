"""FastAPI app: ``uvicorn sextante_api.main:app``.

Endpoints are read-only over one analytics run, except ``POST /api/cv/match``,
which scores an uploaded CV in memory and stores nothing.
"""

from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .cv import CvError, extract_text
from .data import RunData, load_run, resolve_run_dir
from .insights import dashboard, match_cv, segment_names


def create_app(run_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="SEXTANTE API", version=__version__)
    origins = os.environ.get("SEXTANTE_CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins],
                       allow_origin_regex=os.environ.get("SEXTANTE_CORS_ORIGIN_REGEX") or None,
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    loaded: list[RunData] = []
    lock = threading.Lock()

    def run() -> RunData:
        # One load at a time: the preload thread and the first requests (e.g. the
        # host's health check) must not each load a copy, or a 512 MB host OOMs.
        if not loaded:
            with lock:
                if not loaded:
                    loaded.append(load_run(run_dir or resolve_run_dir()))
        return loaded[0]

    @lru_cache(maxsize=1)
    def cached_dashboard() -> dict[str, Any]:
        return dashboard(run())

    if os.environ.get("SEXTANTE_PRELOAD") == "1":
        # Load the run (and warm the dashboard) while the server already answers.
        threading.Thread(target=cached_dashboard, daemon=True).start()

    preload = os.environ.get("SEXTANTE_PRELOAD") == "1"

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        if preload and not loaded:  # answer the host's health check while loading
            return {"status": "loading"}
        data = run()
        return {"status": "ok", "run_id": data.manifest.get("run_id"),
                "postings": len(data.postings)}

    @app.get("/api/dashboard")
    def get_dashboard() -> dict[str, Any]:
        return cached_dashboard()

    @app.get("/api/segments/{segment_id}/postings")
    def segment_postings(segment_id: int, limit: int = 20) -> dict[str, Any]:
        data = run()
        if segment_id not in data.segment_ids:
            raise HTTPException(404, "Segmento no encontrado")
        rows = data.postings[data.postings["cluster_id"] == segment_id].head(min(limit, 100))
        columns = ["vacancy_id", "source", "url", "title", "company", "city", "work_modality"]
        return {"segment": segment_id, "name": segment_names(data).get(segment_id),
                "postings": rows[columns].astype(object).where(rows[columns].notna(), None)
                .to_dict(orient="records")}

    @app.post("/api/cv/match")
    async def cv_match(
        file: Annotated[UploadFile | None, File()] = None,
        text: Annotated[str | None, Form()] = None,
        city: Annotated[str | None, Form()] = None,
        modality: Annotated[str | None, Form()] = None,
        limit: Annotated[int, Form()] = 20,
    ) -> dict[str, Any]:
        try:
            if file is not None:
                content = await file.read()
                cv_text = extract_text(file.filename or "", content)
            elif text and len(text.strip()) >= 30:
                cv_text = text.strip()[:60_000]
            else:
                raise CvError("Sube un CV (PDF, DOCX o TXT) o pega al menos 30 caracteres.")
        except CvError as exc:
            raise HTTPException(422, str(exc)) from exc
        return match_cv(run(), cv_text, limit=max(1, min(limit, 50)),
                        city=city or None, modality=modality or None)

    return app


app = create_app()
