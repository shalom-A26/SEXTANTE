"""SEXTANTE — Colombian job-posting capture pipeline.

Extracts job postings from the SPE official export and JobSpy job boards,
normalizes them to a canonical schema (see ``pipeline.schema``), and publishes
parquet partitions to Hugging Face, which acts as the pipeline's persistent
memory (GitHub Actions runners are ephemeral).

Entry point: ``python -m pipeline <command>``.
"""

# Identifiable User-Agent (ethical requirement: no anonymous scraping).
USER_AGENT = (
    "SEXTANTE-UTB-university-research/1.0 "
    "(university data-mining research; respects robots.txt)"
)
