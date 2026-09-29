"""Runs py_actions_expressions_parser on a corpus (executed by compare_incumbent.py in the incumbent's venv)."""

from __future__ import annotations

import importlib
import json
import sys
from typing import Any

sys.setrecursionlimit(10000)
_pkg = "py_actions_expressions_parser"
Lexer: Any = importlib.import_module(f"{_pkg}.lexer").Lexer
Parser: Any = importlib.import_module(f"{_pkg}.parser").Parser
Evaluator: Any = importlib.import_module(f"{_pkg}.evaluator").Evaluator
data: Any = importlib.import_module(f"{_pkg}.data")
from_json_compatible: Any = importlib.import_module(f"{_pkg}.serialization").from_json_compatible
FilteredArray: Any = importlib.import_module(f"{_pkg}.filtered_array").FilteredArray


def enc(r: Any) -> dict[str, Any]:
    if isinstance(r, data.Null):
        return {"k": "Null"}
    if isinstance(r, data.BooleanData):
        return {"k": "Boolean", "v": r.value}
    if isinstance(r, data.NumberData):
        v = float(r.value)
        text = "nan" if v != v else ("-0" if v == 0 and str(v).startswith("-") else repr(v))
        return {"k": "Number", "f": text}
    if isinstance(r, data.StringData):
        return {"k": "String", "v": r.value}
    if isinstance(r, (data.Array, FilteredArray)):
        return {"k": "Array", "v": [enc(x) for x in r.values()]}
    if isinstance(r, data.Dictionary):
        return {"k": "Object", "v": [[p.key, enc(p.value)] for p in r.pairs()]}
    return {"k": "??"}


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as fh:
        d = json.load(fh)
    ctxs = {k: from_json_compatible(v) for k, v in d["contexts"].items()}
    out: list[dict[str, Any]] = []
    for c in d["cases"]:
        ctx = ctxs[c["ctx"]]
        try:
            toks = Lexer(c["expr"]).lex()
            tree = Parser(toks, [p.key for p in ctx.pairs()], []).parse()
            r = Evaluator(tree, ctx).evaluate() if tree is not None else data.Null()
            out.append({"ok": enc(r)})
        except BaseException as e:  # noqa: BLE001
            out.append({"err": str(e)[:80]})
    with open(sys.argv[2], "w", encoding="utf-8") as fh:
        json.dump(out, fh)


main()
