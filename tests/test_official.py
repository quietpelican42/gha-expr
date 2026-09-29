"""Every case from actions/languageservices expressions/testdata (pinned SHA)."""

from __future__ import annotations

from typing import Any


import gha_expr
from gha_expr import ExpressionError
from gha_expr.values import js_number_to_string


def _same(got: Any, want: Any) -> bool:
    if isinstance(want, bool) or want is None or isinstance(got, bool) or got is None:
        return bool(got is want)
    if isinstance(want, (int, float)):
        if isinstance(got, bool) or not isinstance(got, (int, float)):
            return False
        return js_number_to_string(float(got)) == js_number_to_string(float(want))
    if isinstance(want, str):
        return isinstance(got, str) and got == want
    if isinstance(want, list):
        return isinstance(got, list) and len(got) == len(want) and all(_same(a, b) for a, b in zip(got, want))
    if isinstance(want, dict):
        if not isinstance(got, dict) or len(got) != len(want):
            return False
        lower = {k.lower(): v for k, v in got.items()}
        return all(k.lower() in lower and _same(lower[k.lower()], v) for k, v in want.items())
    return False


def _kind(v: Any) -> str:
    if v is None:
        return "Null"
    if isinstance(v, bool):
        return "Boolean"
    if isinstance(v, (int, float)):
        return "Number"
    if isinstance(v, str):
        return "String"
    return "Array" if isinstance(v, list) else "Object"


def _run(case: dict[str, Any]) -> tuple[bool, str]:
    err = case.get("err")
    try:
        got = gha_expr.evaluate(case["expr"], case.get("contexts") or {})
    except ExpressionError as exc:
        if err is None:
            return False, f"unexpected {exc.kind} error: {exc}"
        if err["kind"] != exc.kind:
            return False, f"expected {err['kind']} error, got {exc.kind}: {exc}"
        text = str(exc)
        if exc.kind == "evaluation":
            text += f". Located within expression: {case['expr']}"
        return err["value"] in text, f"message {text!r} lacks {err['value']!r}"
    if err is not None:
        return False, f"expected {err['kind']} error, got value {got!r}"
    want = case["result"]
    if _kind(got) != want["kind"] or not _same(got, want["value"]):
        return False, f"got {got!r}, want {want['value']!r} ({want['kind']})"
    return True, ""


def test_official_fixtures(upstream_cases: list[dict[str, Any]]) -> None:
    assert len(upstream_cases) == 1020
    failures: list[str] = []
    skipped = 0
    for case in upstream_cases:
        if "typescript" in case.get("options", {}).get("skip", []):
            skipped += 1
            continue
        ok, why = _run(case)
        if not ok:
            failures.append(f"{case['id']} {case['expr']!r}: {why}")
    assert skipped == 5
    assert not failures, f"{len(failures)} of {1020 - skipped} failed:\n" + "\n".join(failures[:30])


def test_typescript_skipped_cases_reported(upstream_cases: list[dict[str, Any]]) -> None:
    """The five cases upstream skips for TypeScript are informational, not asserted."""
    for case in upstream_cases:
        if "typescript" in case.get("options", {}).get("skip", []):
            _run(case)


