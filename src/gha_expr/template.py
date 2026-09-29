# Segmenting logic derived from actions/runner TemplateReader.ParseScalar, MIT License,
# Copyright (c) 2019 GitHub. See LICENSE-actions-runner.
"""Interpolation of ``${{ }}`` expressions inside strings, following the Actions runner."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .errors import TemplateError
from .evaluator import Function, Status, evaluate
from .values import JS_WHITESPACE, coerce_string

_OPEN = "${{"


def _split(raw: str) -> list[tuple[bool, str]]:
    """Split into (is_expression, text) segments like the runner's TemplateReader."""
    segments: list[tuple[bool, str]] = []
    i = 0
    start = raw.find(_OPEN)
    while i < len(raw):
        if i == start:
            end = -1
            in_string = False
            j = i + len(_OPEN)
            while j < len(raw):
                ch = raw[j]
                if ch == "'":
                    in_string = not in_string
                elif not in_string and ch == "}" and raw[j - 1] == "}":
                    end = j
                    j += 1
                    break
                j += 1
            if end < start:
                raise TemplateError(
                    "The expression is not closed. An unescaped ${{ sequence was found, "
                    "but the closing }} sequence was not found."
                )
            body = raw[start + len(_OPEN) : end - 1].strip(JS_WHITESPACE)
            if body == "":
                raise TemplateError("An expression was expected")
            segments.append((True, body))
            i = j
            start = raw.find(_OPEN, i)
        elif i < start:
            _add_text(segments, raw[i:start])
            i = start
        else:
            _add_text(segments, raw[i:])
            break
    return segments


def _add_text(segments: list[tuple[bool, str]], text: str) -> None:
    if segments and not segments[-1][0]:
        segments[-1] = (False, segments[-1][1] + text)
    else:
        segments.append((False, text))


def _string_literal(expr: str) -> str | None:
    """The runner's IsExpressionString: an expression made only of quoted strings."""
    out: list[str] = []
    in_string = False
    for i, c in enumerate(expr):
        if c == "'":
            in_string = not in_string
            if in_string and i != 0:
                out.append(c)
        elif not in_string:
            return None
        else:
            out.append(c)
    return "".join(out)


def evaluate_template(
    template: str,
    context: Mapping[str, Any] | None = None,
    *,
    hash_files: Callable[[list[str]], str] | None = None,
    status: Status = "success",
    functions: Iterable[Function] = (),
) -> Any:
    """Evaluate a template string.

    A string without ``${{`` is returned unchanged. A string that is exactly one
    expression returns that expression's value with its type. Anything else is
    the concatenation of the text and each expression converted to a string.
    """
    if _OPEN not in template:
        return template
    segments = _split(template)

    def run(expr: str) -> Any:
        return evaluate(expr, context, hash_files=hash_files, status=status, functions=functions)

    if len(segments) == 1 and segments[0][0]:
        literal = _string_literal(segments[0][1])
        if literal is not None:
            return literal
        return run(segments[0][1])
    return "".join(coerce_string(run(t)) if is_expr else t for is_expr, t in segments)


def interpolate(
    template: str,
    context: Mapping[str, Any] | None = None,
    *,
    hash_files: Callable[[list[str]], str] | None = None,
    status: Status = "success",
    functions: Iterable[Function] = (),
) -> str:
    """Like :func:`evaluate_template` but always returns a string."""
    return coerce_string(
        evaluate_template(template, context, hash_files=hash_files, status=status, functions=functions)
    )
