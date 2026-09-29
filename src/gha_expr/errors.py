"""Exception types raised while lexing, parsing and evaluating expressions."""

from __future__ import annotations

MAX_PARSER_DEPTH = 50
MAX_EXPRESSION_LENGTH = 21000


class ExpressionError(Exception):
    """Base class. ``kind`` is ``"lexing"``, ``"parsing"`` or ``"evaluation"``."""

    kind: str = "evaluation"


class ExpressionSyntaxError(ExpressionError):
    """The expression could not be tokenized or parsed.

    ``message`` mirrors @actions/expressions, including the trailing
    ``Located at position N within expression: ...`` text.
    ``position`` is the 1-based column in UTF-16 code units, or ``None``.
    """

    def __init__(self, message: str, kind: str, position: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.position = position


class ExpressionEvaluationError(ExpressionError):
    """The expression parsed but failed while being evaluated."""

    kind = "evaluation"


class TemplateError(ExpressionError):
    """A ``${{ }}`` template could not be split into expressions."""

    kind = "template"
