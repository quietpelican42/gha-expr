# Derived from actions/languageservices (expressions/), MIT License, Copyright GitHub.
# See LICENSE-actions-languageservices.
"""Tree-walking evaluator, a port of the evaluator and built-in functions in @actions/expressions."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal as LiteralType

from . import ast
from .errors import ExpressionEvaluationError
from .jsonio import from_json, to_json
from .parser import parse
from .values import (
    ARRAY,
    BOOLEAN,
    JS_WHITESPACE,
    OBJECT,
    FilteredArray,
    coerce_string,
    dict_get,
    dict_items,
    greater_than,
    is_falsy,
    is_primitive,
    is_truthy,
    kind_of,
    less_than,
    loose_equals,
    to_number,
    upper_special,
)

Status = LiteralType["success", "failure", "cancelled"]


@dataclass(frozen=True, slots=True)
class Function:
    """An extra function: ``call`` receives the evaluated arguments."""

    name: str
    min_args: int
    max_args: int
    call: Callable[..., Any]


class _Fail(Exception):
    pass


# --- built-in functions ---------------------------------------------------------


def _contains(left: Any, right: Any) -> bool:
    if is_primitive(left):
        if is_primitive(right):
            return coerce_string(right).lower() in coerce_string(left).lower()
    elif kind_of(left) == ARRAY:
        return any(loose_equals(right, v) for v in left)
    return False


def _starts_with(left: Any, right: Any) -> bool:
    if not is_primitive(left) or not is_primitive(right):
        return False
    return upper_special(coerce_string(left)).startswith(upper_special(coerce_string(right)))


def _ends_with(left: Any, right: Any) -> bool:
    if not is_primitive(left) or not is_primitive(right):
        return False
    return upper_special(coerce_string(left)).endswith(upper_special(coerce_string(right)))


def _format(fmt: Any, *args: Any) -> str:
    fs = coerce_string(fmt)
    out: list[str] = []
    index = 0
    n = len(fs)
    while index < n:
        lbrace = fs.find("{", index)
        rbrace = fs.find("}", index)
        if lbrace >= 0 and (rbrace < 0 or rbrace > lbrace):
            if fs[lbrace + 1 : lbrace + 2] == "{":
                out.append(fs[index : lbrace + 1])
                index = lbrace + 2
                continue
            if rbrace > lbrace + 1:
                j = lbrace + 1
                while j < n and "0" <= fs[j] <= "9":
                    j += 1
                if j > lbrace + 1:
                    arg_index = int(fs[lbrace + 1 : j]) if j - lbrace - 1 < 30 else 10**30
                    if arg_index + 1 > len(args):
                        raise ExpressionEvaluationError(
                            f"The following format string references more arguments than were supplied: {fs}"
                        )
                    if lbrace > index:
                        out.append(fs[index:lbrace])
                    out.append(coerce_string(args[arg_index]))
                    index = rbrace + 1
                    continue
            raise ExpressionEvaluationError(f"The following format string is invalid: {fs}")
        if rbrace >= 0:
            if fs[rbrace + 1 : rbrace + 2] == "}":
                out.append(fs[index : rbrace + 1])
                index = rbrace + 2
            else:
                raise ExpressionEvaluationError(f"The following format string is invalid: {fs}")
        else:
            out.append(fs[index:])
            break
    return "".join(out)


def _join(value: Any, *rest: Any) -> str:
    if is_primitive(value):
        return coerce_string(value)
    if kind_of(value) == ARRAY:
        sep = ","
        if rest and is_primitive(rest[0]):
            sep = coerce_string(rest[0])
        return sep.join(coerce_string(v) for v in value)
    return ""


def _from_json(value: Any) -> Any:
    text = coerce_string(value)
    if text.strip("\t\n\v\f\r          "
                  "        　﻿") == "":
        raise ExpressionEvaluationError("empty input")
    return from_json(text)


def _case(*args: Any) -> Any:
    for i in range(0, len(args) - 1, 2):
        predicate = args[i]
        if kind_of(predicate) != BOOLEAN:
            raise ExpressionEvaluationError("case predicate must evaluate to a boolean value")
        if predicate:
            return args[i + 1]
    return args[-1]


_BUILTINS: dict[str, Callable[..., Any]] = {
    "case": _case,
    "contains": _contains,
    "endswith": _ends_with,
    "format": _format,
    "fromjson": _from_json,
    "join": _join,
    "startswith": _starts_with,
    "tojson": lambda v: to_json(v),
}


# --- evaluation -------------------------------------------------------------------


class _Idx:
    __slots__ = ("star", "text", "num")

    def __init__(self, star: bool, value: Any = None) -> None:
        self.star = star
        self.text: str | None = None
        self.num: int | None = None
        if star:
            return
        if is_primitive(value):
            self.text = coerce_string(value)
        f = to_number(value)
        if not math.isnan(f) and math.isfinite(f) and f >= 0:
            self.num = math.floor(f)


class Evaluator:
    def __init__(
        self,
        context: Mapping[str, Any],
        functions: Mapping[str, Callable[..., Any]],
    ) -> None:
        self.context = context
        self.functions = functions

    def eval(self, n: ast.Node) -> Any:
        if isinstance(n, ast.Literal):
            return n.value
        if isinstance(n, ast.Binary):
            return self._binary(n)
        if isinstance(n, ast.Logical):
            return self._logical(n)
        if isinstance(n, ast.IndexAccess):
            return self._index(n)
        if isinstance(n, ast.FunctionCall):
            args = [self.eval(a) for a in n.args]
            name = n.name.lower()
            f = self.functions.get(name) or _BUILTINS[name]
            return f(*args)
        if isinstance(n, ast.ContextAccess):
            found, v = dict_get(self.context, n.name)
            if not found:
                raise ExpressionEvaluationError(f"Unrecognized named-value: '{n.name}'")
            return v
        if isinstance(n, ast.Grouping):
            return self.eval(n.expr)
        if isinstance(n, ast.Unary):
            return is_falsy(self.eval(n.expr))
        raise ExpressionEvaluationError(f"cannot evaluate {type(n).__name__}")

    def _binary(self, n: ast.Binary) -> Any:
        # Left-nested chains (a == b == c ...) are unrolled to keep recursion shallow.
        chain: list[ast.Binary] = []
        node: ast.Node = n
        while isinstance(node, ast.Binary):
            chain.append(node)
            node = node.left
        left = self.eval(node)
        for b in reversed(chain):
            right = self.eval(b.right)
            left = _compare(b.operator, left, right)
        return left

    def _logical(self, n: ast.Logical) -> Any:
        result: Any = None
        is_and = n.operator == "&&"
        for arg in n.args:
            result = self.eval(arg)
            if (is_and and is_falsy(result)) or (not is_and and is_truthy(result)):
                break
        return result

    def _index(self, n: ast.IndexAccess) -> Any:
        if isinstance(n.index, ast.Star):
            idx = _Idx(True)
        else:
            try:
                idx_value = self.eval(n.index)
            except ExpressionEvaluationError as exc:
                raise ExpressionEvaluationError(
                    f"could not evaluate index for index access: {exc}"
                ) from exc
            idx = _Idx(False, idx_value)
        obj = self.eval(n.expr)
        k = kind_of(obj)
        if k == ARRAY:
            if isinstance(obj, FilteredArray):
                return _filtered_access(obj, idx)
            return _array_access(obj, idx)
        if k == OBJECT:
            return _object_access(obj, idx)
        return FilteredArray() if idx.star else None


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "==":
        return loose_equals(left, right)
    if op == "!=":
        return not loose_equals(left, right)
    if op == ">":
        return greater_than(left, right)
    if op == ">=":
        return loose_equals(left, right) or greater_than(left, right)
    if op == "<":
        return less_than(left, right)
    return loose_equals(left, right) or less_than(left, right)


def _filtered_access(fa: list[Any], idx: _Idx) -> FilteredArray:
    result = FilteredArray()
    for item in fa:
        k = kind_of(item)
        if k == OBJECT:
            if idx.star:
                result.extend(x for _, x in dict_items(item))
            elif idx.text is not None:
                found, v = dict_get(item, idx.text)
                if found:
                    result.append(v)
        elif k == ARRAY:
            if idx.star:
                result.extend(item)
            elif idx.num is not None and idx.num < len(item):
                result.append(item[idx.num])
    return result


def _array_access(a: Any, idx: _Idx) -> Any:
    if idx.star:
        return FilteredArray(a)
    if idx.num is not None and idx.num < len(a):
        return a[idx.num]
    return None


def _object_access(obj: Mapping[str, Any], idx: _Idx) -> Any:
    if idx.star:
        return FilteredArray(x for _, x in dict_items(obj))
    if idx.text is not None:
        found, v = dict_get(obj, idx.text)
        if found:
            return v
    return None


def evaluate(
    expression: str | ast.Node | None,
    context: Mapping[str, Any] | None = None,
    *,
    hash_files: Callable[[list[str]], str] | None = None,
    status: Status = "success",
    functions: Iterable[Function] = (),
) -> Any:
    """Evaluate one expression (the text between ``${{`` and ``}}``).

    ``context`` maps context names (``github``, ``env``, ...) to values.
    ``hash_files`` receives the pattern arguments of ``hashFiles``. ``status``
    drives ``success()``, ``failure()`` and ``cancelled()``; ``always()`` is
    always true. ``functions`` adds or overrides functions by name.

    Numbers the evaluator produces are ``float``. Values read from ``context``
    are returned as given, including containers.
    """
    ctx: Mapping[str, Any] = context if context is not None else {}
    extra = {f.name.lower(): f for f in functions}
    if isinstance(expression, str):
        tree = parse(
            expression,
            [k for k, _ in dict_items(ctx)],
            extra_functions={name: (f.min_args, f.max_args) for name, f in extra.items()},
        )
    else:
        tree = expression
    if tree is None:
        return None

    def hash_files_fn(*patterns: Any) -> str:
        if hash_files is None:
            raise ExpressionEvaluationError("hashFiles is unavailable: pass hash_files= to evaluate()")
        return hash_files([coerce_string(p) for p in patterns])

    funcs: dict[str, Callable[..., Any]] = {
        "hashfiles": hash_files_fn,
        "success": lambda: status == "success",
        "failure": lambda: status == "failure",
        "cancelled": lambda: status == "cancelled",
        "always": lambda: True,
    }
    for name, f in extra.items():
        funcs[name] = f.call
    try:
        return Evaluator(ctx, funcs).eval(tree)
    except RecursionError as exc:
        raise ExpressionEvaluationError("expression is nested too deeply to evaluate") from exc


__all__ = ["Evaluator", "Function", "Status", "evaluate"]
