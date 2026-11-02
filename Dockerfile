# SEXTANTE API (Stage 8). Serves the latest analytics run from Hugging Face.
#   docker build -t sextante-api .
#   docker run -p 8000:8000 -e SEXTANTE_HF_REPO=pxtron/vacantes-colombia \
#     -e HF_TOKEN=<read-only token> -e SEXTANTE_CORS_ORIGINS=https://<web-domain> sextante-api
# Without SEXTANTE_HF_REPO it builds a synthetic demo run at startup.
FROM python:3.12-slim

WORKDIR /app
# System allocator for Arrow: its default pools keep ~150 MB of freed parquet
# buffers, which matters on 512 MB hosts (see sextante_api/serving.py).
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 SEXTANTE_PRELOAD=1 \
    ARROW_DEFAULT_MEMORY_POOL=system MALLOC_ARENA_MAX=2

COPY requirements.txt requirements-analysis.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

COPY pipeline/ pipeline/
COPY sextante_analysis/ sextante_analysis/
COPY sextante_api/ sextante_api/

RUN useradd --create-home --uid 1000 sextante && mkdir -p data/analysis/runs && chown -R sextante /app
USER sextante

CMD ["sh", "-c", "if [ -z \"$SEXTANTE_HF_REPO\" ] && [ -z \"$SEXTANTE_RUN_DIR\" ]; then python -m sextante_analysis demo; fi && exec uvicorn sextante_api.main:app --host 0.0.0.0 --port $PORT"]
