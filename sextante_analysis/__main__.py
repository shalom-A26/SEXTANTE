"""Command line interface for SEXTANTE analytics."""

from __future__ import annotations

import argparse
import sys

from .config import AnalysisConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sextante-analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="analyze one Hugging Face corpus revision")
    run.add_argument("--repo", default="pxtron/vacantes-colombia")
    run.add_argument("--esco-csv", required=True, help="official Spanish ESCO skills CSV")
    run.add_argument("--output", default="data/analysis/runs")
    run.add_argument("--limit", type=int, help="deterministic prefix limit for demos")
    run.add_argument("--duplicate-threshold", type=float, default=0.90)
    run.add_argument("--topics", type=int, default=12)
    run.add_argument("--clusters", type=int, default=8)
    run.add_argument(
        "--embeddings",
        action="store_true",
        help="also compute pinned multilingual embeddings",
    )
    run.add_argument(
        "--upload",
        action="store_true",
        help="publish under derived/runs/ in the same private HF dataset",
    )
    demo = subparsers.add_parser("demo", help="run every stage on a synthetic corpus")
    demo.add_argument("--output", default="data/analysis/runs")
    demo.add_argument("--rows", type=int, default=600)
    review = subparsers.add_parser("review", help="export manual-review CSV samples of a run")
    review.add_argument("run_dir")
    evaluate = subparsers.add_parser("evaluate", help="score filled manual-review CSVs")
    evaluate.add_argument("review_dir")
    args = parser.parse_args(argv)
    if args.command == "review":
        from .validation import export_review_samples

        for path in export_review_samples(args.run_dir):
            print(f"[review] {path}")
        return 0
    if args.command == "evaluate":
        import json

        from .validation import evaluate_reviews

        print(json.dumps(evaluate_reviews(args.review_dir), indent=2))
        return 0
    if sys.version_info < (3, 12):
        parser.error("SEXTANTE analytics requires Python 3.12 or newer")
    if args.command == "demo":
        from .demo import run_demo

        print(f"[analysis] synthetic demo written to {run_demo(args.output, args.rows)}")
        return 0
    try:
        from .run import run_analysis

        run_dir = run_analysis(
            AnalysisConfig(
                repo=args.repo,
                output_root=args.output,
                esco_csv=args.esco_csv,
                limit=args.limit,
                duplicate_threshold=args.duplicate_threshold,
                topic_count=args.topics,
                cluster_count=args.clusters,
                embeddings=args.embeddings,
                upload=args.upload,
            )
        )
    except Exception as exc:  # CLI boundary: keep source failures visible and concise
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"[analysis] artifacts written to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
