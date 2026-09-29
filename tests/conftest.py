from __future__ import annotations

import hashlib
import json
import urllib.request
import warnings
from pathlib import Path
from typing import Any

import pytest

from upstream import BASE, SHA, SHA256

CACHE = Path(__file__).parent / "_cache" / SHA


def _fetch(name: str) -> bytes | None:
    path = CACHE / name
    if path.exists():
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() == SHA256[name]:
            return data
    try:
        with urllib.request.urlopen(BASE + name, timeout=30) as resp:  # noqa: S310
            data = bytes(resp.read())
    except OSError:
        return None
    if hashlib.sha256(data).hexdigest() != SHA256[name]:
        raise AssertionError(f"sha256 mismatch for pinned upstream file {name}")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


@pytest.fixture(scope="session")
def upstream_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for name in SHA256:
        data = _fetch(name)
        if data is None:
            msg = (
                f"SKIPPED official fixtures: cannot download {BASE}{name} and no cached copy. "
                f"Run once with network access; files are cached in tests/_cache."
            )
            warnings.warn(msg, stacklevel=1)
            pytest.skip(msg)
        for group, group_cases in json.loads(data).items():
            for i, case in enumerate(group_cases):
                case["id"] = f"{name}:{group}:{i}"
                cases.append(case)
    return cases
