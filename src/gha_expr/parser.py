# Derived from actions/languageservices (expressions/), MIT License, Copyright GitHub.
# See LICENSE-actions-languageservices.
"""Recursive-descent parser, a port of the parser in @actions/expressions."""

from __future__ import annotations

from collections.abc import Iterable

from .ast import (
    Binary,
    ContextAccess,
    FunctionCall,
    Grouping,
    IndexAccess,
    Literal,
    Logical,
    Node,
    Star,
    Unary,
)
from .errors import MAX_PARSER_DEPTH, ExpressionSyntaxError
from .lexer import T, Lexer, Token

# name (lowercase) -> (min args, max args)
BUILTIN_ARITY: dict[str, tuple[int, int]] = {
    "case": (3, 9007199254740991),
    "contains": (2, 2),
    "endswith": (2, 2),
    "format": (1, 255),
    "fromjson": (1, 1),
    "join": (1, 2),
    "startswith": (2, 2),
    "tojson": (1, 1),
}

# Functions the runner adds on top of the built-ins.
RUNNER_ARITY: dict[str, tuple[int, int]] = {
    "hashfiles": (1, 255),
    "success": (0, 0),
    "failure": (0, 0),
    "always": (0, 0),
    "cancelled": (0, 0),
}

_DESCRIPTIONS = {
    "end": "Unexpected end of expression",
    "symbol": "Unexpected symbol",
    "context": "Unrecognized named-value",
    "depth": f"Exceeded max expression depth {MAX_PARSER_DEPTH}",
    "few": "Too few parameters supplied",
    "many": "Too many parameters supplied",
    "even": "Even number of parameters supplied, requires an odd number of parameters",
    "function": "Unrecognized function",
}


class Parser:
    def __init__(
        self,
        source: str,
        tokens: list[Token],
        lexer: Lexer,
        contexts: Iterable[str] | None,
        functions: dict[str, tuple[int, int]],
    ) -> None:
        self.source = source
        self.tokens = tokens
        self.lexer = lexer
        self.offset = 0
        self.depth = 0
        self.contexts = None if contexts is None else {c.lower() for c in contexts}
        self.functions = functions

    def parse(self) -> Node | None:
        if self._at_end():
            return None
        result = self._expression()
        if not self._at_end():
            raise self._error("symbol", self._peek())
        return result

    def _expression(self) -> Node:
        self._incr()
        try:
            return self._logical_or()
        finally:
            self.depth -= 1

    def _logical_or(self) -> Node:
        expr = self._logical_and()
        if self._check(T.OR):
            self._incr()
            try:
                args = [expr]
                while self._match(T.OR):
                    args.append(self._logical_and())
                expr = Logical("||", tuple(args))
            finally:
                self.depth -= 1
        return expr

    def _logical_and(self) -> Node:
        expr = self._equality()
        if self._check(T.AND):
            self._incr()
            try:
                args = [expr]
                while self._match(T.AND):
                    args.append(self._equality())
                expr = Logical("&&", tuple(args))
            finally:
                self.depth -= 1
        return expr

    def _equality(self) -> Node:
        expr = self._comparison()
        while self._match(T.BANG_EQUAL, T.EQUAL_EQUAL):
            op = self._previous().lexeme
            expr = Binary(expr, op, self._comparison())
        return expr

    def _comparison(self) -> Node:
        expr = self._unary()
        while self._match(T.GREATER, T.GREATER_EQUAL, T.LESS, T.LESS_EQUAL):
            op = self._previous().lexeme
            expr = Binary(expr, op, self._unary())
        return expr

    def _unary(self) -> Node:
        if self._match(T.BANG):
            self._incr()
            operand = self._unary()
            self.depth -= 1
            return Unary("!", operand)
        return self._index()

    def _index(self) -> Node:
        expr = self._call()
        raised = 0
        if isinstance(expr, (Grouping, FunctionCall, ContextAccess)):
            while True:
                if self._match(T.LEFT_BRACKET):
                    index: Node
                    if self._match(T.STAR):
                        index = Star()
                    else:
                        index = self._expression()
                    self._consume(T.RIGHT_BRACKET)
                    self._incr()
                    raised += 1
                    expr = IndexAccess(expr, index)
                elif self._match(T.DOT):
                    self._incr()
                    raised += 1
                    if self._match(T.IDENTIFIER):
                        expr = IndexAccess(expr, Literal(self._previous().lexeme))
                    elif self._match(T.STAR):
                        expr = IndexAccess(expr, Star())
                    else:
                        raise self._error("symbol", self._peek())
                else:
                    break
        self.depth -= raised
        return expr

    def _call(self) -> Node:
        if not self._check(T.IDENTIFIER):
            return self._primary()
        identifier = self._next()
        if not self._match(T.LEFT_PAREN):
            if self.contexts is not None and identifier.lexeme.lower() not in self.contexts:
                raise self._error("context", identifier)
            return ContextAccess(identifier.lexeme)
        args: list[Node] = []
        while not self._match(T.RIGHT_PAREN):
            args.append(self._expression())
            if not self._check(T.RIGHT_PAREN):
                self._consume(T.COMMA)
        self._validate_function(identifier, len(args))
        return FunctionCall(identifier.lexeme, tuple(args))

    def _validate_function(self, identifier: Token, argc: int) -> None:
        name = identifier.lexeme.lower()
        arity = self.functions.get(name)
        if arity is None:
            raise self._error("function", identifier)
        if argc < arity[0]:
            raise self._error("few", identifier)
        if argc > arity[1]:
            raise self._error("many", identifier)
        if name == "case" and argc % 2 == 0:
            raise self._error("even", identifier)

    def _primary(self) -> Node:
        if self._match(T.FALSE):
            return Literal(False)
        if self._match(T.TRUE):
            return Literal(True)
        if self._match(T.NULL):
            return Literal(None)
        if self._match(T.NUMBER):
            v = self._previous().value
            assert isinstance(v, float)
            return Literal(v)
        if self._match(T.STRING):
            v2 = self._previous().value
            assert isinstance(v2, str)
            return Literal(v2)
        if self._match(T.LEFT_PAREN):
            expr = self._expression()
            if self._at_end():
                raise self._error("end", self._previous())
            self._consume(T.RIGHT_PAREN)
            return Grouping(expr)
        if self._at_end():
            raise self._error("end", self._previous())
        raise self._error("symbol", self._peek())

    def _match(self, *types: T) -> bool:
        for t in types:
            if self._check(t):
                self._next()
                return True
        return False

    def _check(self, t: T) -> bool:
        if self._at_end():
            return False
        return self.tokens[self.offset].type == t

    def _at_end(self) -> bool:
        return self.tokens[self.offset].type == T.EOF

    def _next(self) -> Token:
        if not self._at_end():
            self.offset += 1
        return self._previous()

    def _peek(self) -> Token:
        return self.tokens[self.offset]

    def _previous(self) -> Token:
        return self.tokens[self.offset - 1]

    def _consume(self, t: T) -> None:
        if self._check(t):
            self._next()
            return
        raise self._error("symbol", self._peek())

    def _incr(self) -> None:
        self.depth += 1
        if self.depth > MAX_PARSER_DEPTH:
            raise self._error("depth", self._peek())

    def _error(self, code: str, tok: Token) -> ExpressionSyntaxError:
        col = self.lexer.column(tok) + 1
        return ExpressionSyntaxError(
            f"{_DESCRIPTIONS[code]}: '{tok.text()}'. Located at position {col} within expression: {self.source}",
            "parsing",
            col,
        )


def parse(
    expression: str,
    contexts: Iterable[str] | None = None,
    *,
    extra_functions: dict[str, tuple[int, int]] | None = None,
) -> Node | None:
    """Parse ``expression`` into a syntax tree, or ``None`` for an empty expression.

    ``contexts`` lists the allowed top-level names (case-insensitive). ``None``
    accepts any name. Functions are the built-ins plus the runner's
    ``hashFiles``, ``success``, ``failure``, ``always`` and ``cancelled``.
    """
    lexer = Lexer(expression)
    tokens = lexer.lex()
    functions = {**(extra_functions or {}), **RUNNER_ARITY, **BUILTIN_ARITY}
    return Parser(expression, tokens, lexer, contexts, functions).parse()


