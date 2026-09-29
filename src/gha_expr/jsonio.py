# Derived from actions/languageservices (expressions/), MIT License, Copyright GitHub.
# See LICENSE-actions-languageservices.
"""``JSON.stringify`` and ``JSON.parse`` as the reference implementation uses them."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from .errors import ExpressionEvaluationError
from .values import (
    ARRAY,
    BOOLEAN,
    NULL,
    NUMBER,
    STRING,
    as_float,
    dict_items,
    js_number_to_string,
    kind_of,
)

_ARRAY_INDEX = re.compile(r"(?:0|[1-9][0-9]*)")
_ESC = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_NEEDS_ESCAPE = re.compile('["\\\\\x00-\x1f\ud800-\udfff]')


def _quote_char(m: re.Match[str]) -> str:
    c = m.group()
    e = _ESC.get(c)
    return e if e is not None else f"\\u{ord(c):04x}"


def quote(s: str) -> str:
    return '"' + _NEEDS_ESCAPE.sub(_quote_char, s) + '"'


def _is_array_index(k: str) -> bool:
    return bool(_ARRAY_INDEX.fullmatch(k)) and int(k) < 4294967295


def js_key_order(pairs: list[tuple[str, Any]]) -> list[tuple[str, Any]]:
    """Own-property order of a JS object: array indexes ascending, then insertion order."""
    ints = sorted((p for p in pairs if _is_array_index(p[0])), key=lambda p: int(p[0]))
    rest = [p for p in pairs if not _is_array_index(p[0])]
    return ints + rest


def to_json(value: Any) -> str:
    """``JSON.stringify(value, replacer, "  ")`` over expression data."""
    out: list[str] = []
    _write(value, 0, out)
    return "".join(out)


def _write(v: Any, level: int, out: list[str]) -> None:
    k = kind_of(v)
    if k == NULL:
        out.append("null")
    elif k == BOOLEAN:
        out.append("true" if v else "false")
    elif k == NUMBER:
        f = as_float(v)
        out.append(js_number_to_string(f) if math.isfinite(f) else "null")
    elif k == STRING:
        out.append(quote(v))
    elif k == ARRAY:
        if len(v) == 0:
            out.append("[]")
            return
        ind = "\n" + "  " * (level + 1)
        out.append("[")
        for i, item in enumerate(v):
            out.append(("," if i else "") + ind)
            _write(item, level + 1, out)
        out.append("\n" + "  " * level + "]")
    else:
        pairs = js_key_order(list(dict_items(v)))
        if not pairs:
            out.append("{}")
            return
        ind = "\n" + "  " * (level + 1)
        out.append("{")
        for i, (key, item) in enumerate(pairs):
            out.append(("," if i else "") + ind + quote(key) + ": ")
            _write(item, level + 1, out)
        out.append("\n" + "  " * level + "}")


def _reject_constant(name: str) -> Any:
    raise ValueError(f"invalid JSON constant {name}")


def _object_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # JSON.parse: a repeated key keeps its first position and takes the last value.
    merged: dict[str, Any] = {}
    for k, v in pairs:
        merged[k] = v
    ordered = js_key_order(list(merged.items()))
    # Dictionary construction: first key wins case-insensitively, inherited names dropped.
    return dict(dict_items(dict(ordered)))


def from_json(text: str) -> Any:
    """``JSON.parse`` followed by the reference reviver (objects become Dictionaries)."""
    try:
        return json.loads(
            text,
            parse_int=float,
            parse_float=float,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_hook,
        )
    except (ValueError, RecursionError) as exc:
        raise ExpressionEvaluationError("Error parsing JSON when evaluating fromJson") from exc


__all__ = ["from_json", "to_json"]
