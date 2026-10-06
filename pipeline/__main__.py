"""CLI entry point: ``python -m pipeline <command>``.

Commands
--------
probe       Test which JobSpy sites return jobs for Colombia (viability).
pull        Restore the published corpus from Hugging Face into local stores.
capture     Run one capture source (spe | jobspy) and append to its store.
emit        Build the dataset directory and optionally upload it to HF.

A source that fails exits with code 1 — deliberately. The restored store
would still be there and a re-emission would republish the same corpus, so a
silent 0 would let the pipeline *look* healthy while it stopped growing.
"""

from __future__ import annotations

import argparse
import sys


def _cmd_probe(args: argparse.Namespace) -> int:
    from .sources.jobspy_source import ALL_SITES, scrape

    sites = args.sites.split(",") if args.sites else ALL_SITES
    print(f"[probe] sites: {', '.join(sites)} | location={args.location} | results={args.results}")
    ok: list[str] = []
    failed: list[str] = []
    for site in sites:
        try:
            frame = scrape(sites=[site], results=args.results, location=args.location)
        except Exception as exc:  # noqa: BLE001 — probe's job is to survive failures
            print(f"[probe] {site}: FAIL ({type(exc).__name__}: {exc})")
            failed.append(site)
            continue
        if len(frame):
            sample = " | ".join(str(t) for t in frame["title"].head(3))
            print(f"[probe] {site}: OK ({len(frame)} rows) — {sample}")
            ok.append(site)
        else:
            print(f"[probe] {site}: 0 rows")
            failed.append(site)
    print(f"\n[probe] viable: {', '.join(ok) or 'none'}")
    if failed:
        print(f"[probe] not viable: {', '.join(failed)}")
    return 0 if ok else 1


def _cmd_pull(args: argparse.Namespace) -> int:
    from . import env, sync

    datasets = env.DATASETS if args.dataset == "all" else (args.dataset,)
    for dataset in datasets:
        sync.pull(dataset, args.repo)
    return 0


def _cmd_capture(args: argparse.Namespace) -> int:
    if args.source == "spe":
        from pathlib import Path

        from .sources import spe

        csv = Path(args.spe_csv) if args.spe_csv else None
        spe.capture(csv=csv)
        return 0

    from . import store
    from .sources import jobspy_source

    sites = jobspy_source.ACTIVE_SITES if not args.sites else args.sites.split(",")
    try:
        frame = jobspy_source.scrape(sites=sites, results=args.results, location=args.location)
    except RuntimeError as exc:  # every site failed: defined condition, clean exit
        print(f"[jobspy] {exc}", file=sys.stderr)
        return 1
    if len(frame) == 0:
        print("[jobspy] no rows returned by any site", file=sys.stderr)
        return 1
    added = store.append("jobspy", frame)
    print(f"[jobspy] {added} new rows")
    return 0


def _cmd_emit(args: argparse.Namespace) -> int:
    from . import emit as emit_mod
    from . import env

    datasets = env.DATASETS if args.dataset == "all" else (args.dataset,)
    for dataset in datasets:
        out = emit_mod.emit(dataset)
        if args.upload:
            emit_mod.upload(out, dataset, args.repo)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline", description="SEXTANTE capture pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_probe = sub.add_parser("probe", help="test JobSpy site viability for Colombia")
    p_probe.add_argument("--sites", help="comma-separated sites (default: all known)")
    p_probe.add_argument("--location", default="Colombia")
    p_probe.add_argument("--results", type=int, default=8)
    p_probe.set_defaults(func=_cmd_probe)

    p_pull = sub.add_parser("pull", help="restore the published corpus from Hugging Face")
    p_pull.add_argument("--dataset", choices=["spe", "jobspy", "all"], default="all")
    p_pull.add_argument("--repo", default="pxtron/vacantes-colombia")
    p_pull.set_defaults(func=_cmd_pull)

    p_cap = sub.add_parser("capture", help="run one capture source")
    p_cap.add_argument("--source", choices=["spe", "jobspy"], required=True)
    p_cap.add_argument("--sites", help="comma-separated JobSpy sites (default: active list)")
    p_cap.add_argument("--results", type=int, default=100, help="results per site (jobspy)")
    p_cap.add_argument("--location", default="Colombia")
    p_cap.add_argument("--spe-csv", help="reuse an already-downloaded SPE CSV instead of re-downloading")
    p_cap.set_defaults(func=_cmd_capture)

    p_emit = sub.add_parser("emit", help="build the dataset directory and upload")
    p_emit.add_argument("--dataset", choices=["spe", "jobspy", "all"], default="all")
    p_emit.add_argument("--upload", action="store_true", help="upload to Hugging Face (needs HF_TOKEN)")
    p_emit.add_argument("--repo", default="pxtron/vacantes-colombia")
    p_emit.set_defaults(func=_cmd_emit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
