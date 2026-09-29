# Derived from actions/languageservices (expressions/), MIT License, Copyright GitHub.
# See LICENSE-actions-languageservices.
"""Tokenizer, a port of the lexer in @actions/expressions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

from .errors import MAX_EXPRESSION_LENGTH, ExpressionSyntaxError
from .values import JS_WHITESPACE, js_to_number


class T(IntEnum):
    LEFT_PAREN = 1
    RIGHT_PAREN = 2
    LEFT_BRACKET = 3
    RIGHT_BRACKET = 4
    COMMA = 5
    DOT = 6
    BANG = 7
    BANG_EQUAL = 8
    EQUAL_EQUAL = 9
    GREATER = 10
    GREATER_EQUAL = 11
    LESS = 12
    LESS_EQUAL = 13
    AND = 14
    OR = 15
    STAR = 16
    NUMBER = 17
    STRING = 18
    IDENTIFIER = 19
    TRUE = 20
    FALSE = 21
    NULL = 22
    EOF = 23


@dataclass(frozen=True, slots=True)
class Token:
    type: T
    lexeme: str
    value: float | str | None
    # Start offset and the offset of the current line, as code point indexes.
    start: int
    line_start: int

    def text(self) -> str:
        """How the token is quoted in error messages."""
        if self.type == T.EOF:
            return "EOF"
        if self.type == T.STRING:
            assert isinstance(self.value, str)
            return self.value
        return self.lexeme


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def _is_boundary(c: str) -> bool:
    return c in "([)],.!><=&|" or c in JS_WHITESPACE


def _is_legal_identifier(s: str) -> bool:
    if s == "":
        return False
    first = s[0]
    if not (("a" <= first <= "z") or ("A" <= first <= "Z") or first == "_"):
        return False
    for c in s[1:]:
        if not (("a" <= c <= "z") or ("A" <= c <= "Z") or ("0" <= c <= "9") or c in "_-"):
            return False
    return True


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.start = 0
        self.offset = 0
        self.line_start = 0
        self.tokens: list[Token] = []

    def column(self, tok: Token) -> int:
        """0-based column of the token start, in UTF-16 code units."""
        if tok.line_start > tok.start:  # EOF after a trailing newline: the column is -1
            return -utf16_len(self.source[tok.start : tok.line_start])
        return utf16_len(self.source[tok.line_start : tok.start])

    def _err(self, lexeme: str) -> ExpressionSyntaxError:
        pos = utf16_len(self.source[: self.start]) + 1
        return ExpressionSyntaxError(
            f"Unexpected symbol: '{lexeme}'. Located at position {pos} within expression: {self.source}",
            "lexing",
            pos,
        )

    def lex(self) -> list[Token]:
        src = self.source
        if utf16_len(src) > MAX_EXPRESSION_LENGTH:
            raise ExpressionSyntaxError("ErrorExceededMaxLength", "lexing")
        n = len(src)
        while self.offset < n:
            self.start = self.offset
            c = src[self.offset]
            self.offset += 1
            if c == "(":
                self._add(T.LEFT_PAREN)
            elif c == ")":
                self._add(T.RIGHT_PAREN)
            elif c == "[":
                self._add(T.LEFT_BRACKET)
            elif c == "]":
                self._add(T.RIGHT_BRACKET)
            elif c == ",":
                self._add(T.COMMA)
            elif c == ".":
                if self._previous() not in (T.IDENTIFIER, T.RIGHT_BRACKET, T.RIGHT_PAREN, T.STAR):
                    self._number()
                else:
                    self._add(T.DOT)
            elif c == "-" or c == "+":
                self._number()
            elif c == "!":
                self._add(T.BANG_EQUAL if self._match("=") else T.BANG)
            elif c == "=":
                if not self._match("="):
                    self._identifier()
                else:
                    self._add(T.EQUAL_EQUAL)
            elif c == "<":
                self._add(T.LESS_EQUAL if self._match("=") else T.LESS)
            elif c == ">":
                self._add(T.GREATER_EQUAL if self._match("=") else T.GREATER)
            elif c == "&":
                if not self._match("&"):
                    self._identifier()
                else:
                    self._add(T.AND)
            elif c == "|":
                if not self._match("|"):
                    self._identifier()
                else:
                    self._add(T.OR)
            elif c == "*":
                self._add(T.STAR)
            elif c == " " or c == "\r" or c == "\t":
                pass
            elif c == "\n":
                self.line_start = self.offset
            elif c == "'":
                self._string()
            elif "0" <= c <= "9":
                self._number()
            else:
                self._identifier()
        self._add(T.EOF)
        return self.tokens

    def _add(self, typ: T, value: float | str | None = None) -> None:
        self.tokens.append(
            Token(typ, self.source[self.start : self.offset], value, self.start, self.line_start)
        )

    def _previous(self) -> T:
        return self.tokens[-1].type if self.tokens else T.EOF

    def _match(self, expected: str) -> bool:
        if self.offset >= len(self.source) or self.source[self.offset] != expected:
            return False
        self.offset += 1
        return True

    def _number(self) -> None:
        src = self.source
        n = len(src)
        while self.offset < n and (not _is_boundary(src[self.offset]) or src[self.offset] == "."):
            self.offset += 1
        lexeme = src[self.start : self.offset]
        value = js_to_number(lexeme)
        if math.isnan(value):
            raise self._err(lexeme)
        self._add(T.NUMBER, value)

    def _string(self) -> None:
        src = self.source
        n = len(src)
        while self.offset < n and not (
            src[self.offset] == "'" and not (self.offset + 1 < n and src[self.offset + 1] == "'")
        ):
            if src[self.offset] == "'" and self.offset + 1 < n and src[self.offset + 1] == "'":
                self.offset += 1
            self.offset += 1
        if self.offset >= n:
            raise self._err(src[self.start :])
        self.offset += 1
        value = src[self.start + 1 : self.offset - 1]
        # The reference implementation replaces only the first '' pair.
        value = value.replace("''", "'", 1)
        self._add(T.STRING, value)

    def _identifier(self) -> None:
        src = self.source
        n = len(src)
        while self.offset < n and not _is_boundary(src[self.offset]):
            self.offset += 1
        typ = T.IDENTIFIER
        value: float | None = None
        lexeme = src[self.start : self.offset]
        if self._previous() != T.DOT:
            if lexeme == "true":
                typ = T.TRUE
            elif lexeme == "false":
                typ = T.FALSE
            elif lexeme == "null":
                typ = T.NULL
            elif lexeme == "NaN":
                typ, value = T.NUMBER, math.nan
            elif lexeme == "Infinity":
                typ, value = T.NUMBER, math.inf
        if not _is_legal_identifier(lexeme):
            raise self._err(lexeme)
        self._add(typ, value)
