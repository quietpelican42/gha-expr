"""Score another Python implementation against @actions/expressions on the generated corpus.

    python bench/compare_incumbent.py --incumbent-python /path/to/venv/bin/python --seed 1

The incumbent is tomasrollo/py_actions_expressions_parser (git-only, not on PyPI), installed
into its own venv from https://github.com/tomasrollo/py_actions_expressions_parser at commit
b833b39b9bf7e088ff336bcadef59dd8965a7a64. Cases that call runner-only functions (hashFiles,
success, failure, always, cancelled) are excluded because that library does not implement them.
Agreement is on value kind and content, or on both sides failing. Error messages are not compared.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import differential  # noqa: E402
from gen_corpus import generate  # noqa: E402

from gha_expr.values import js_number_to_string  # noqa: E402

RUNNER_ONLY = re.compile(r"hashfiles|success|failure|always|cancelled", re.IGNORECASE)


def same(want: dict[str, Any], got: dict[str, Any]) -> bool:
    if want["k"] != got["k"]:
        return False
    k = want["k"]
    if k == "Number":
        f = got["f"]
        if f == "nan":
            return bool(want["v"] == "NaN")
        if f in ("inf", "-inf"):
            return bool(want["v"] == f.replace("inf", "Infinity"))
        if f == "-0":
            return bool(want["v"] == "-0")
        return bool(want["v"] == js_number_to_string(float(f)))
    if k == "Array":
        return len(want["v"]) == len(got["v"]) and all(same(a, b) for a, b in zip(want["v"], got["v"], strict=True))
    if k == "Object":
        return len(want["v"]) == len(got["v"]) and all(
            a[0] == b[0] and same(a[1], b[1]) for a, b in zip(want["v"], got["v"], strict=True)
        )
    return bool(want.get("v") == got.get("v"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incumbent-python", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--show", type=int, default=8)
    args = ap.parse_args()
    reason = differential.node_available()
    if reason:
        print("cannot run the oracle:", reason, file=sys.stderr)
        return 2
    contexts, cases = generate(args.seed, args.n)
    keep = [c for c in cases if not RUNNER_ONLY.search(c["expr"])]
    want = differential.run_oracle(contexts, keep)
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in.json", Path(tmp) / "out.json"
        src.write_text(json.dumps({"contexts": contexts, "cases": keep}))
        subprocess.run(
            [args.incumbent_python, str(Path(__file__).parent / "incumbent_runner.py"), str(src), str(dst)],
            check=True, timeout=1800, stdin=subprocess.DEVNULL,
        )
        got = json.loads(dst.read_text())
    ours = [differential.run_python(c, contexts) for c in keep]
    agree_inc = agree_ours = 0
    bad = []
    for case, w, g, o in zip(keep, want, got, ours, strict=True):
        ok = ("err" in w) if "err" in g else ("ok" in w and same(w["ok"], g["ok"]))
        agree_inc += ok
        agree_ours += (("err" in w) == ("err" in o)) and ("ok" not in w or w["ok"] == o["ok"])
        if not ok:
            bad.append((case["expr"], w, g))
    n = len(keep)
    print(f"seed={args.seed} cases={n} (of {len(cases)}; runner-only functions excluded)")
    print(f"incumbent: {agree_inc}/{n} = {100 * agree_inc / n:.2f}%")
    print(f"gha-expr:  {agree_ours}/{n} = {100 * agree_ours / n:.2f}%")
    for expr, w, g in bad[: args.show]:
        print("---", repr(expr)[:110], "\n  oracle:   ", json.dumps(w)[:130], "\n  incumbent:", json.dumps(g)[:130])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
