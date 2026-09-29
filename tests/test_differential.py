"""Compare against @actions/expressions: a recorded fixture, and a live run when node is present."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import pytest

import differential
from gen_corpus import generate

FIXTURE = Path(__file__).parent / "data" / "differential.json"
LIVE_SEEDS = [1, 2, 3]
LIVE_N = 20000


def test_recorded_fixture() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = data["cases"]
    expected = [c.pop("expected") for c in cases]
    ok, bad = differential.compare(data["contexts"], cases, expected)
    assert len(cases) >= 1000
    assert not bad, f"{len(bad)} of {len(cases)} differ, first: {bad[0]}"
    assert ok == len(cases)


def test_fixture_covers_outcome_kinds() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    kinds = {("err:" + c["expected"]["err"]["kind"]) if "err" in c["expected"] else "value" for c in data["cases"]}
    assert kinds == {"value", "err:lexing", "err:parsing", "err:evaluation"}


@pytest.mark.parametrize("seed", LIVE_SEEDS)
def test_live_differential(seed: int) -> None:
    reason = differential.node_available()
    if reason:
        msg = f"SKIPPED live differential ({LIVE_N} random expressions vs @actions/expressions): {reason}"
        warnings.warn(msg, stacklevel=1)
        pytest.skip(msg)
    contexts, cases = generate(seed, LIVE_N)
    expected = differential.run_oracle(contexts, cases)
    ok, bad = differential.compare(contexts, cases, expected)
    assert not bad, f"{len(bad)} of {LIVE_N} differ; first: {bad[0]}"
    assert ok == LIVE_N


def test_generator_is_deterministic() -> None:
    assert generate(5, 200) == generate(5, 200)
    assert generate(5, 200) != generate(6, 200)
