"""Artifact manifests and Hugging Face publication for completed runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    """Write a manifest with hashes for every artifact already in ``run_dir``."""
    manifest["artifacts"] = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(run_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    path = run_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def publish_run(run_dir: Path, repo: str, run_id: str, token: str | None) -> None:
    """Upload a complete run, then move the latest pointer in a second commit."""
    if not token:
        raise RuntimeError("HF_TOKEN is required to publish analytics artifacts")
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.upload_folder(
        folder_path=str(run_dir),
        repo_id=repo,
        repo_type="dataset",
        path_in_repo=f"derived/runs/{run_id}",
        token=token,
        commit_message=f"Add analytics run {run_id}",
    )
    api.upload_file(
        path_or_fileobj=str(run_dir / "manifest.json"),
        path_in_repo="derived/latest.json",
        repo_id=repo,
        repo_type="dataset",
        token=token,
        commit_message=f"Point latest analytics run to {run_id}",
    )
