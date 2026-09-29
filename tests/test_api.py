from __future__ import annotations

import math
from typing import Any

import pytest

import gha_expr
from gha_expr import (
    ExpressionEvaluationError,
    ExpressionSyntaxError,
    Function,
    ast,
    evaluate,
    parse,
)

CTX: dict[str, Any] = {
    "github": {
        "ref": "refs/heads/main",
        "event_name": "push",
        "n": 3,
        "labels": [{"name": "bug"}, {"name": "Docs"}],
        "Mixed": {"KeY": 1},
    },
    "env": {"FOO": "bar"},
}


@pytest.mark.parametrize(
    ("expr", "want"),
    [
        ("1 == 1.0", True),
        ("'ABC' == 'abc'", True),
        ("null == 0", True),
        ("'' == false", True),
        ("'1' == 1", True),
        ("null || 'x'", "x"),
        ("'a' && 'b'", "b"),
        ("0 || null", None),
        ("!'' ", True),
        ("github.mixed.key", 1),
        ("github.labels.*.name[0]", []),
        ("toJSON(github.labels.*.name)", '[\n  "bug",\n  "Docs"\n]'),
        ("contains(github.labels.*.name, 'DOCS')", True),
        ("contains(github.ref, 'HEADS')", True),
        ("startsWith(github.ref, 'REFS/')", True),
        ("endsWith(github.ref, 'Main')", True),
        ("format('{0}-{{1}}-{1}', 'a', 2)", "a-{1}-2"),
        ("join(github.labels.*.name, ' | ')", "bug | Docs"),
        ("fromJSON('{\"a\":[1,2]}').a[1]", 2.0),
        ("case(github.n == 1, 'one', github.n == 3, 'three', 'many')", "three"),
        ("1e21", 1e21),
        ("0x1F", 31.0),
        ("'it''s'", "it's"),
        ("toJSON(1e21)", "1e+21"),
        ("toJSON(0.1 == 0.1)", "true"),
        ("format('{0}', 1e-7)", "1e-7"),
        ("format('{0}', 0.30000000000000004)", "0.3"),
        ("''", ""),
        ("", None),
    ],
)
def test_evaluate(expr: str, want: Any) -> None:
    got = evaluate(expr, CTX)
    if isinstance(want, float):
        assert isinstance(got, float)
    assert got == want


def test_number_literals_are_floats() -> None:
    assert evaluate("42") == 42.0
    assert isinstance(evaluate("42"), float)
    assert math.isnan(evaluate("NaN"))
    assert evaluate("-Infinity") == -math.inf
    assert evaluate("1e400") == math.inf


def test_context_values_pass_through() -> None:
    value = {"k": [1, 2]}
    assert evaluate("x", {"x": value}) is value
    assert evaluate("x.k", {"x": value}) is value["k"]


def test_filters_build_new_arrays() -> None:
    ctx = {"a": [{"b": 1}]}
    assert evaluate("a.*.b == a.*.b", ctx) is False
    assert evaluate("a == a", ctx) is True
    assert isinstance(evaluate("a.*", ctx), gha_expr.FilteredArray)


def test_status_functions() -> None:
    assert evaluate("success()") is True
    assert evaluate("failure()") is False
    assert evaluate("failure()", status="failure") is True
    assert evaluate("success() || failure()", status="cancelled") is False
    assert evaluate("cancelled()", status="cancelled") is True
    assert evaluate("always()", status="failure") is True


def test_hash_files_hook() -> None:
    seen: list[list[str]] = []

    def hook(patterns: list[str]) -> str:
        seen.append(patterns)
        return "abc"

    assert evaluate("hashFiles('**/*.lock', 2)", hash_files=hook) == "abc"
    assert seen == [["**/*.lock", "2"]]
    with pytest.raises(ExpressionEvaluationError, match="hash_files="):
        evaluate("hashFiles('x')")
    with pytest.raises(ExpressionSyntaxError, match="Too few parameters"):
        evaluate("hashFiles()", hash_files=hook)


def test_extra_functions() -> None:
    fn = Function("twice", 1, 1, lambda v: v * 2)
    assert evaluate("twice(4)", functions=[fn]) == 8.0
    with pytest.raises(ExpressionSyntaxError, match="Unrecognized function: 'twice'"):
        evaluate("twice(4)")


@pytest.mark.parametrize(
    ("expr", "kind", "message"),
    [
        ("1_0", "lexing", "Unexpected symbol: '1_0'. Located at position 1 within expression: 1_0"),
        ("'abc", "lexing", "Unexpected symbol: ''abc'"),
        ("a = b", "lexing", "Unexpected symbol: '='"),
        ("github.", "parsing", "Unexpected symbol: 'EOF'. Located at position 7"),
        ("nosuch.x", "parsing", "Unrecognized named-value: 'nosuch'. Located at position 1"),
        ("nofunc(1)", "parsing", "Unrecognized function: 'nofunc'"),
        ("contains(1)", "parsing", "Too few parameters supplied: 'contains'"),
        ("contains(1,2,3)", "parsing", "Too many parameters supplied: 'contains'"),
        ("case(true, 1, false, 2)", "parsing", "Even number of parameters supplied, requires an odd number of parameters: 'case'"),
        ("(" * 51 + "1" + ")" * 51, "parsing", "Exceeded max expression depth 50"),
        ("1 2", "parsing", "Unexpected symbol: '2'. Located at position 3 within expression: 1 2"),
        ("'a'[0]", "parsing", "Unexpected symbol: '['"),
        ("format('{0')", "evaluation", "The following format string is invalid: {0"),
        ("format('{1}', 'a')", "evaluation", "references more arguments than were supplied"),
        ("fromJSON('')", "evaluation", "empty input"),
        ("fromJSON('NaN')", "evaluation", "Error parsing JSON when evaluating fromJson"),
        ("fromJSON('[1,]')", "evaluation", "Error parsing JSON when evaluating fromJson"),
        ("case(1, 2, 3)", "evaluation", "case predicate must evaluate to a boolean value"),
        ("github[fromJSON('x')]", "evaluation", "could not evaluate index for index access: Error parsing JSON"),
        ("x" * 21001, "lexing", "ErrorExceededMaxLength"),
    ],
)
def test_errors(expr: str, kind: str, message: str) -> None:
    with pytest.raises(gha_expr.ExpressionError) as info:
        evaluate(expr, CTX)
    assert info.value.kind == kind
    assert message in str(info.value)


def test_position_counts_utf16_units() -> None:
    with pytest.raises(ExpressionSyntaxError) as info:
        parse("'\U0001f600' 1")
    assert info.value.position == 6  # the emoji is two UTF-16 units


def test_multiline_position_is_relative_to_line() -> None:
    with pytest.raises(ExpressionSyntaxError) as info:
        parse("1 ==\n  )")
    assert info.value.position == 3


def test_parse_returns_tree() -> None:
    tree = parse("a.b == 1 && !c", contexts=["a", "c"])
    assert isinstance(tree, ast.Logical)
    assert tree.operator == "&&"
    left, right = tree.args
    assert isinstance(left, ast.Binary) and left.operator == "=="
    assert isinstance(left.left, ast.IndexAccess)
    assert left.left.index == ast.Literal("b")
    assert right == ast.Unary("!", ast.ContextAccess("c"))
    assert parse("") is None
    assert evaluate(tree, {"a": {"b": 1}, "c": ""}) is True


def test_parse_without_contexts_accepts_any_name() -> None:
    assert parse("anything.at.all") is not None
    with pytest.raises(ExpressionSyntaxError):
        parse("anything", contexts=["other"])


def test_deep_equality_chain_does_not_overflow() -> None:
    # The JavaScript reference can overflow its stack on a chain this long; this evaluates it.
    assert evaluate("1" + "==1" * 3000) is True
    assert evaluate("!" * 40 + "true") is True


def test_short_circuit_still_evaluates_function_arguments() -> None:
    with pytest.raises(ExpressionEvaluationError):
        evaluate("contains('a', fromJSON('x'))")
    assert evaluate("false && fromJSON('x')") is False
    assert evaluate("true || fromJSON('x')") is True


def test_dictionary_keys_first_wins_and_reserved_names() -> None:
    assert evaluate("o.key", {"o": {"Key": 1, "KEY": 2}}) == 1
    assert evaluate("o.constructor", {"o": {"constructor": 1}}) is None
    assert evaluate("toJSON(fromJSON('{\"2\":1,\"1\":2,\"b\":3}'))", {}) == '{\n  "1": 2,\n  "2": 1,\n  "b": 3\n}'


def test_bad_context_types() -> None:
    with pytest.raises(TypeError):
        evaluate("x == 1", {"x": {1, 2}})
    with pytest.raises(TypeError):
        evaluate("x.a", {"x": {1: "a"}})


def test_string_comparison_uses_utf16_order() -> None:
    # U+FF5E sorts below U+1F600 by code point but above it by UTF-16 code unit (0xD83D).
    assert evaluate("'～' > '\U0001f600'") is True
    assert evaluate("'\U0001f600' < '～'") is True


def test_dotless_i_is_not_uppercased() -> None:
    assert evaluate("'ı' == 'I'") is False
    assert evaluate("'i' == 'I'") is True
    assert evaluate("startsWith('ıx', 'I')") is False
