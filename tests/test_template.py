from __future__ import annotations

from typing import Any

import pytest

from gha_expr import TemplateError, evaluate_template, interpolate

CTX: dict[str, Any] = {
    "github": {"sha": "abc", "n": 3, "flag": True, "list": [1], "obj": {"a": 1}, "none": None},
    "env": {"NAME": "world"},
}


@pytest.mark.parametrize(
    ("template", "want"),
    [
        ("plain text", "plain text"),
        ("", ""),
        ("hello ${{ env.name }}!", "hello world!"),
        ("${{ github.sha }}-${{github.n}}", "abc-3"),
        ("${{ github.flag }}", "true"),
        ("${{ github.none }}|", "|"),
        ("[${{ github.list }}] [${{ github.obj }}]", "[Array] [Object]"),
        ("${{ 1.50 }} ${{ 1e21 }}", "1.5 1e+21"),
        ("a {b} }c{ ${{ 'x' }}", "a {b} }c{ x"),
        ("${{ 'a''b' }}", "a'b"),
        ("${{ 'a}}b' }} tail", "a}}b tail"),
        ("${{ format('{0}}}', 1) }}", "1}"),
        ("$${{ 1 }}", "$1"),
        ("${{ 1 }}${{ 2 }}", "12"),
        ("${ { 1 } }", "${ { 1 } }"),
    ],
)
def test_interpolate(template: str, want: str) -> None:
    assert interpolate(template, CTX) == want


def test_single_expression_keeps_type() -> None:
    assert evaluate_template("${{ github.n }}", CTX) == 3
    assert evaluate_template("  ${{ github.n }}", CTX) == "  3"
    assert evaluate_template("${{ github.obj }}", CTX) == {"a": 1}
    assert evaluate_template("${{ 1 == 1 }}", CTX) is True


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("${{ 1", "not closed"),
        ("${{ 'a }}", "not closed"),
        ("${{ }}", "expression was expected"),
        ("x ${{   }} y", "expression was expected"),
    ],
)
def test_template_errors(template: str, message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        interpolate(template, CTX)


def test_expression_errors_propagate() -> None:
    from gha_expr import ExpressionSyntaxError

    with pytest.raises(ExpressionSyntaxError):
        interpolate("a ${{ nosuch.x }}", CTX)


def test_status_and_hash_files_reach_expressions() -> None:
    out = interpolate(
        "${{ success() }}/${{ failure() }}/${{ hashFiles('a', 'b') }}",
        {},
        status="failure",
        hash_files=lambda p: "+".join(p),
    )
    assert out == "false/true/a+b"
