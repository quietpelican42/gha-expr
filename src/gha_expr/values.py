# Derived from actions/languageservices (expressions/), MIT License, Copyright GitHub.
# See LICENSE-actions-languageservices.
"""Value model: JavaScript-compatible coercions used by @actions/expressions.

Values are plain Python objects: ``None``, ``bool``, ``int``/``float``,
``str``, ``list`` and ``dict``. Numbers are treated as IEEE doubles.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping
from typing import Any, Final

NULL: Final = 0
BOOLEAN: Final = 1
NUMBER: Final = 2
STRING: Final = 3
ARRAY: Final = 4
OBJECT: Final = 5

# Keys that cannot exist in a JS Dictionary because the reference
# implementation stores them in a plain object (`key in {}`).
_INHERITED = frozenset({"constructor", "__proto__"})

# JavaScript WhiteSpace + LineTerminator code points (String.prototype.trim, \s).
JS_WHITESPACE: Final = (
    "\t\n\v\f\r          "
    "        　﻿"
)

_DECIMAL_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_HEX_RE = re.compile(r"0[xX][0-9a-fA-F]+")
_OCT_RE = re.compile(r"0[oO][0-7]+")
_BIN_RE = re.compile(r"0[bB][01]+")


class FilteredArray(list[Any]):
    """Result of a ``*`` filter. Compares by identity, like any array."""

    __hash__ = None


def kind_of(v: object) -> int:
    if v is None:
        return NULL
    if isinstance(v, bool):
        return BOOLEAN
    if isinstance(v, (int, float)):
        return NUMBER
    if isinstance(v, str):
        return STRING
    if isinstance(v, (list, tuple)):
        return ARRAY
    if isinstance(v, Mapping):
        return OBJECT
    raise TypeError(f"unsupported value type in expression context: {type(v).__name__}")


def kind_name(k: int) -> str:
    return ("Null", "Boolean", "Number", "String", "Array", "Object")[k]


def as_float(v: int | float) -> float:
    try:
        return float(v)
    except OverflowError:
        return math.inf if v > 0 else -math.inf


def js_to_number(s: str) -> float:
    """``Number(string)`` from ECMAScript."""
    t = s.strip(JS_WHITESPACE)
    if t == "":
        return 0.0
    if _DECIMAL_RE.fullmatch(t):
        return float(t)
    if t == "Infinity" or t == "+Infinity":
        return math.inf
    if t == "-Infinity":
        return -math.inf
    base = 0
    if _HEX_RE.fullmatch(t):
        base = 16
    elif _OCT_RE.fullmatch(t):
        base = 8
    elif _BIN_RE.fullmatch(t):
        base = 2
    if base:
        n = int(t[2:], base)
        return as_float(n)
    return math.nan


def to_number(v: object) -> float:
    k = kind_of(v)
    if k == NULL:
        return 0.0
    if k == BOOLEAN:
        return 1.0 if v else 0.0
    if k == NUMBER:
        return as_float(v)  # type: ignore[arg-type]
    if k == STRING:
        return js_to_number(v)  # type: ignore[arg-type]
    return math.nan


def _digits_exponent(x: float) -> tuple[str, int]:
    """Shortest round-trip digits of ``abs(x)`` and the decimal point position n."""
    r = repr(abs(x))
    if "e" in r:
        m, e = r.split("e")
        exp = int(e)
    else:
        m, exp = r, 0
    if "." in m:
        ip, fp = m.split(".")
    else:
        ip, fp = m, ""
    digits = ip + fp
    n = len(ip) + exp
    stripped = digits.lstrip("0")
    n -= len(digits) - len(stripped)
    digits = stripped.rstrip("0")
    return digits, n


def js_number_to_string(x: float) -> str:
    """ECMAScript ``Number::toString(x)`` (radix 10)."""
    if x != x:
        return "NaN"
    if x == 0:
        return "0"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    sign = "-" if x < 0 else ""
    digits, n = _digits_exponent(x)
    k = len(digits)
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    es = ("+" if e >= 0 else "-") + str(abs(e))
    if k == 1:
        return sign + digits + "e" + es
    return sign + digits[0] + "." + digits[1:] + "e" + es


_SCALE = 10**15


def _to_fixed_15(x: float) -> float:
    """``+x.toFixed(15)`` for finite ``abs(x) < 1e21``."""
    if x == math.floor(x) and abs(x) < 2.0**53:
        return x
    num, den = abs(x).as_integer_ratio()
    n = (num * _SCALE * 2 + den) // (2 * den)  # round half up on the exact value
    y = float(f"{n // _SCALE}.{n % _SCALE:015d}")
    return -y if x < 0 else y


def number_to_string(x: float) -> str:
    """The string an expression number becomes (limited to 15 fractional digits)."""
    if x == 0:
        return "0"
    if x == x and not math.isinf(x) and abs(x) < 1e21:
        x = _to_fixed_15(x)
    return js_number_to_string(x)


def coerce_string(v: object) -> str:
    k = kind_of(v)
    if k == STRING:
        return v  # type: ignore[return-value]
    if k == NULL:
        return ""
    if k == BOOLEAN:
        return "true" if v else "false"
    if k == NUMBER:
        return number_to_string(as_float(v))  # type: ignore[arg-type]
    return "Array" if k == ARRAY else "Object"


def is_primitive(v: object) -> bool:
    return kind_of(v) <= STRING


def is_falsy(v: object) -> bool:
    k = kind_of(v)
    if k == NULL:
        return True
    if k == BOOLEAN:
        return not v
    if k == NUMBER:
        f = as_float(v)  # type: ignore[arg-type]
        return f == 0 or f != f
    if k == STRING:
        return len(v) == 0  # type: ignore[arg-type]
    return False


def is_truthy(v: object) -> bool:
    return not is_falsy(v)


# --- objects -----------------------------------------------------------------


def dict_items(d: Mapping[str, Any]) -> Iterator[tuple[str, Any]]:
    """Entries of a Dictionary: first key wins case-insensitively; inherited names dropped."""
    seen: set[str] = set()
    for k, v in d.items():
        if not isinstance(k, str):
            raise TypeError("object keys in an expression context must be strings")
        lk = k.lower()
        if lk in seen or lk in _INHERITED:
            continue
        seen.add(lk)
        yield k, v


def dict_get(d: Mapping[str, Any], key: str) -> tuple[bool, Any]:
    lk = key.lower()
    if lk in _INHERITED:
        return False, None
    for k, v in d.items():
        if not isinstance(k, str):
            raise TypeError("object keys in an expression context must be strings")
        if k.lower() == lk:
            return True, v
    return False, None


# --- comparison --------------------------------------------------------------


def upper_special(s: str) -> str:
    """``toUpperCase`` that leaves the dotless i alone."""
    if "ı" not in s:
        return s.upper()
    return "ı".join(p.upper() for p in s.split("ı"))


def _coerce(li: object, ri: object) -> tuple[object, object]:
    lk, rk = kind_of(li), kind_of(ri)
    if lk == rk:
        return li, ri
    if lk == NUMBER:
        if rk == STRING:
            return li, to_number(ri)
    elif lk == STRING:
        if rk == NUMBER:
            return to_number(li), ri
    elif lk == NULL or lk == BOOLEAN:
        return _coerce(to_number(li), ri)
    if rk == NULL or rk == BOOLEAN:
        return _coerce(li, to_number(ri))
    return li, ri


def loose_equals(lhs: object, rhs: object) -> bool:
    lv, rv = _coerce(lhs, rhs)
    lk = kind_of(lv)
    if lk != kind_of(rv):
        return False
    if lk == NULL:
        return True
    if lk == NUMBER:
        a, b = as_float(lv), as_float(rv)  # type: ignore[arg-type]
        return a == b
    if lk == STRING:
        return upper_special(lv) == upper_special(rv)  # type: ignore[arg-type]
    if lk == BOOLEAN:
        return lv == rv
    return lv is rv


def _u16(s: str) -> bytes:
    return s.encode("utf-16-be", "surrogatepass")


def _string_order(a: str, b: str) -> int:
    """Compare in UTF-16 code unit order, like JavaScript's relational operators."""
    a, b = upper_special(a), upper_special(b)
    if not (a.isascii() and b.isascii()):
        ua, ub = _u16(a), _u16(b)
        return (ua > ub) - (ua < ub)
    return (a > b) - (a < b)


def greater_than(lhs: object, rhs: object) -> bool:
    lv, rv = _coerce(lhs, rhs)
    lk = kind_of(lv)
    if lk != kind_of(rv):
        return False
    if lk == NUMBER:
        return as_float(lv) > as_float(rv)  # type: ignore[arg-type]
    if lk == STRING:
        return _string_order(lv, rv) > 0  # type: ignore[arg-type]
    if lk == BOOLEAN:
        return bool(lv) and not rv
    return False


def less_than(lhs: object, rhs: object) -> bool:
    lv, rv = _coerce(lhs, rhs)
    lk = kind_of(lv)
    if lk != kind_of(rv):
        return False
    if lk == NUMBER:
        return as_float(lv) < as_float(rv)  # type: ignore[arg-type]
    if lk == STRING:
        return _string_order(lv, rv) < 0  # type: ignore[arg-type]
    if lk == BOOLEAN:
        return not lv and bool(rv)
    return False


