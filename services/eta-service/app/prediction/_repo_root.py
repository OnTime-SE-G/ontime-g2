"""Resolve monorepo root for `ml` imports in local dev and container images."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    bundled = Path("/opt/ontime")
    if (bundled / "ml").is_dir():
        return bundled
    try:
        candidate = Path(__file__).resolve().parents[4]
    except IndexError:
        candidate = bundled
    if (candidate / "ml").is_dir():
        return candidate
    return bundled
