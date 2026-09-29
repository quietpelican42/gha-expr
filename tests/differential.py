"""Run generated cases through gha_expr and @actions/expressions and compare.

    python tests/differential.py --n 20000 --seed 1 [--write-fixture N]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import gha_expr
from gha_expr import ExpressionError
from gha_expr.values import (
    ARRAY,
    BOOLEAN,
    NULL,
    NUMBER,
    STRING,
    dict_items,
    js_number_to_string,
    kind_of,
)

sys.path.insert(0, str(Path(__file__).parent))
from gen_corpus import generate  # noqa: E402

ORACLE_DIR = Path(__file__).parent / "oracle"


def node_available() -> str | None:
    """Return a reason the oracle cannot run, or None if it can."""
    if shutil.which("node") is None:
        return "node is not on PATH"
    if not (ORACLE_DIR / "node_modules" / "@actions" / "expressions").exists():
        return f"run `npm ci` in {ORACLE_DIR} to install @actions/expressions"
    return None


def encode(v: Any) -> dict[str, Any]:
    k = kind_of(v)
    if k == NULL:
        return {"k": "Null"}
    if k == BOOLEAN:
        return {"k": "Boolean", "v": v}
    if k == NUMBER:
        f = float(v)
        return {"k": "Number", "v": "-0" if f == 0 and str(f).startswith("-") else js_number_to_string(f)}
    if k == STRING:
        return {"k": "String", "v": v}
    if k == ARRAY:
        return {"k": "Array", "v": [encode(x) for x in v]}
    return {"k": "Object", "v": [[key, encode(x)] for key, x in dict_items(v)]}


def run_python(case: dict[str, Any], contexts: dict[str, Any]) -> dict[str, Any]:
    try:
        value = gha_expr.evaluate(
            case["expr"],
            contexts[case["ctx"]],
            hash_files=lambda pats: "hash:" + "|".join(pats),
            status=case["status"],
        )
    except ExpressionError as exc:
        return {"err": {"kind": exc.kind, "msg": str(exc)}}
    except Exception as exc:  # a crash is a failure to compare equal
        return {"err": {"kind": "python-crash", "msg": f"{type(exc).__name__}: {exc}"}}
    return {"ok": encode(value)}


def run_oracle(contexts: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cases.json"
        path.write_text(json.dumps({"contexts": contexts, "cases": cases}), encoding="utf-8")
        proc = subprocess.run(
            ["node", str(ORACLE_DIR / "oracle.mjs"), str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            cwd=ORACLE_DIR,
            stdin=subprocess.DEVNULL,
            check=True,
        )
    out: list[dict[str, Any]] = json.loads(proc.stdout)
    return out


def compare(
    contexts: dict[str, Any], cases: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> tuple[int, list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]]:
    bad = []
    for case, want in zip(cases, expected, strict=True):
        got = run_python(case, contexts)
        if got != want:
            bad.append((case, want, got))
    return len(cases) - len(bad), bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--show", type=int, default=15)
    ap.add_argument("--write-fixture", type=int, default=0, help="write a stratified fixture of this size")
    args = ap.parse_args()
    reason = node_available()
    if reason:
        print("cannot run the oracle:", reason, file=sys.stderr)
        return 2
    contexts, cases = generate(args.seed, args.n)
    expected = run_oracle(contexts, cases)
    ok, bad = compare(contexts, cases, expected)
    kinds = Counter("err:" + e["err"]["kind"] if "err" in e else "value" for e in expected)
    print(f"seed={args.seed} n={args.n} agree={ok}/{len(cases)} ({100 * ok / len(cases):.3f}%) oracle outcomes={dict(kinds)}")
    for case, want, got in bad[: args.show]:
        print("---", repr(case["expr"]), case["ctx"], case["status"])
        print("  oracle:", json.dumps(want, ensure_ascii=False)[:300])
        print("  python:", json.dumps(got, ensure_ascii=False)[:300])
    if args.write_fixture:
        write_fixture(contexts, cases, expected, args.write_fixture)
    return 0 if not bad else 1


def write_fixture(
    contexts: dict[str, Any], cases: list[dict[str, Any]], expected: list[dict[str, Any]], size: int
) -> None:
    """Keep a diverse subset: cap how many cases share an outcome shape and function set."""
    import random
    import re

    def shape(case: dict[str, Any], e: dict[str, Any]) -> str:
        funcs = ",".join(sorted(set(re.findall(r"([A-Za-z]+)\(", case["expr"].lower()))))
        if "err" in e:
            head = re.sub(r"'.*", "", e["err"]["msg"])[:40]
            return f"E:{e['err']['kind']}:{head}:{funcs}"
        return f"V:{e['ok']['k']}:{funcs}"

    rng = random.Random(0)
    order = list(range(len(cases)))
    rng.shuffle(order)
    seen: Counter[str] = Counter()
    chosen: list[int] = []
    for i in order:
        s = shape(cases[i], expected[i])
        if seen[s] < 3:
            seen[s] += 1
            chosen.append(i)
    rest = [i for i in order if i not in set(chosen)]
    chosen = chosen[:size] + rest[: max(0, size - len(chosen))]
    chosen.sort()
    out = {
        "note": "Generated by tests/gen_corpus.py; expected values recorded from @actions/expressions 0.3.61.",
        "contexts": contexts,
        "cases": [{**cases[i], "expected": expected[i]} for i in chosen],
    }
    path = Path(__file__).parent / "data" / "differential.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(chosen)} cases, {path.stat().st_size} bytes)")


if __name__ == "__main__":
    raise SystemExit(main())
