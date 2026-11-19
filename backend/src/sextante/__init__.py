"""SEXTANTE: skill extraction, occupational segmentation, salary estimation and
risk signals in Colombian labor demand.

Subpackages:
- ``sextante.core``: the shared contract (17-column schema) and environment/paths.
- ``sextante.ingestion``: Stage 1 capture (SPE export + JobSpy) into append-only
  stores published on Hugging Face (``python -m sextante.ingestion``).
- ``sextante.analytics``: Stages 2–6 batch analytics (``python -m sextante.analytics``).
- ``sextante.api``: Stage 8 FastAPI backend (``uvicorn sextante.api.main:app``).
"""


# Identifiable User-Agent (ethical requirement: no anonymous scraping).
USER_AGENT = (
    "SEXTANTE-UTB-university-research/1.0 "
    "(university data-mining research; respects robots.txt)"
)
