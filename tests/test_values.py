from __future__ import annotations

import math

import pytest

from gha_expr import coerce_string, js_number_to_string, number_to_string
from gha_expr.values import js_to_number


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (0.0, "0"), (-0.0, "0"), (1.0, "1"), (-1.5, "-1.5"), (0.1, "0.1"), (1e21, "1e+21"), (1e-7, "1e-7"),
        (1e-6, "0.000001"), (123456789012345680000.0, "123456789012345680000"), (1.5e300, "1.5e+300"),
        (5e-324, "5e-324"), (math.inf, "Infinity"), (-math.inf, "-Infinity"), (math.nan, "NaN"),
        (0.30000000000000004, "0.30000000000000004"), (1e20, "100000000000000000000"),
    ],
)
def test_js_number_to_string(x: float, want: str) -> None:
    assert js_number_to_string(x) == want


@pytest.mark.parametrize(
    ("x", "want"),
    [
        (0.30000000000000004, "0.3"),  # limited to 15 fractional digits
        (1e-16, "0"),
        (-1e-16, "0"),
        (0.0000000000000005, "1e-15"),  # half rounds up on the exact value
        (1e21, "1e+21"),
        (2.5, "2.5"),
        (-2.5, "-2.5"),
        (1234567.891, "1234567.891"),
    ],
)
def test_number_to_string_limits_precision(x: float, want: str) -> None:
    assert number_to_string(x) == want


@pytest.mark.parametrize(
    ("s", "want"),
    [
        ("", 0.0), ("  ", 0.0), (" 12 ", 12.0), ("0x10", 16.0), ("0b11", 3.0), ("0o17", 15.0), ("1e3", 1000.0),
        ("+5", 5.0), ("-.5", -0.5), ("5.", 5.0), ("Infinity", math.inf), ("-Infinity", -math.inf),
        ("1e400", math.inf), (" 7﻿", 7.0),
    ],
)
def test_js_to_number(s: str, want: float) -> None:
    assert js_to_number(s) == want


@pytest.mark.parametrize(
    "s", ["1_0", "0x", "0xg", "-0x10", "1e", "1.2.3", "inf", "nan", "infinity", "0b2", "abc", "1 2", "١٢"]
)
def test_js_to_number_rejects(s: str) -> None:
    assert math.isnan(js_to_number(s))


def test_coerce_string_kinds() -> None:
    assert coerce_string(None) == ""
    assert coerce_string(True) == "true"
    assert coerce_string(3) == "3"
    assert coerce_string([1]) == "Array"
    assert coerce_string({"a": 1}) == "Object"


def test_huge_int_from_context_is_infinity() -> None:
    assert coerce_string(10**400) == "Infinity"
