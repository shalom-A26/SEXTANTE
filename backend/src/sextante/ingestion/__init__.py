"""Stage 1: Colombian job-posting capture.

Extracts job postings from the SPE official export and JobSpy job boards,
normalizes them to the canonical schema (see ``sextante.core.schema``) and
publishes parquet partitions to Hugging Face, which acts as the pipeline's
persistent memory (GitHub Actions runners are ephemeral).

Entry point: ``python -m sextante.ingestion <command>``.
"""
