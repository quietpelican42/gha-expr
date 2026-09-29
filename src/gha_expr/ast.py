# Derived from actions/languageservices (expressions/), MIT License, Copyright GitHub.
# See LICENSE-actions-languageservices.
"""Syntax tree returned by :func:`gha_expr.parse`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Literal:
    """null, true, false, a number or a string."""

    value: Any


@dataclass(frozen=True, slots=True)
class ContextAccess:
    """A bare context name such as ``github``. Names are case-insensitive."""

    name: str


@dataclass(frozen=True, slots=True)
class Star:
    """The ``*`` in ``a.*`` and ``a[*]``."""


@dataclass(frozen=True, slots=True)
class IndexAccess:
    """``expr.name``, ``expr[index]`` or a filter (``index`` is a :class:`Star`)."""

    expr: Node
    index: Node


@dataclass(frozen=True, slots=True)
class FunctionCall:
    name: str
    args: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Grouping:
    expr: Node


@dataclass(frozen=True, slots=True)
class Unary:
    operator: str
    expr: Node


@dataclass(frozen=True, slots=True)
class Binary:
    """A comparison or equality operator: ``== != < <= > >=``."""

    left: Node
    operator: str
    right: Node


@dataclass(frozen=True, slots=True)
class Logical:
    """A flat ``&&`` or ``||`` chain. Evaluates to an operand, not a boolean."""

    operator: str
    args: tuple[Node, ...]


Node = Literal | ContextAccess | Star | IndexAccess | FunctionCall | Grouping | Unary | Binary | Logical
