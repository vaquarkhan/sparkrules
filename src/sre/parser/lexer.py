from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    EOF = auto()
    RULE = auto()
    END = auto()
    WHEN = auto()
    THEN = auto()
    SALIENCE = auto()
    AGENDA_GROUP = auto()
    ACTIVATION_GROUP = auto()
    PASS = auto()
    GROUP_BY = auto()
    REASON_CODES = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IN = auto()
    TRUE = auto()
    FALSE = auto()
    NULL = auto()
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()
    DOLLAR = auto()
    COLON = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACK = auto()
    RBRACK = auto()
    COMMA = auto()
    SEMI = auto()
    DOT = auto()
    EQ = auto()
    ASSIGN = auto()
    NE = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()
    CONTAINS = auto()
    MATCHES = auto()


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    col: int


_KEYWORDS: dict[str, TokenKind] = {
    "rule": TokenKind.RULE,
    "end": TokenKind.END,
    "when": TokenKind.WHEN,
    "then": TokenKind.THEN,
    "salience": TokenKind.SALIENCE,
    "agenda_group": TokenKind.AGENDA_GROUP,
    "activation_group": TokenKind.ACTIVATION_GROUP,
    "pass": TokenKind.PASS,
    "group_by": TokenKind.GROUP_BY,
    "reason_codes": TokenKind.REASON_CODES,
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
    "in": TokenKind.IN,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
    "null": TokenKind.NULL,
    "contains": TokenKind.CONTAINS,
    "matches": TokenKind.MATCHES,
}


def tokenize(text: str) -> list[Token]:
    toks: list[Token] = []
    n = len(text)
    i = 0
    line, col = 1, 1
    r_number = re.compile(r"-?\d+(\.\d+)?")
    r_ident = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    r_string_dq = re.compile(r'"(\\.|[^"\\])*"')
    r_string_sq = re.compile(r"'(\\.|[^'\\])*'")

    while i < n:
        c = text[i]
        if c in " \t\r\n":
            if c == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1
            continue
        if c == "/":
            if i + 1 < n and text[i + 1] == "/":
                j = i + 2
                while j < n and text[j] != "\n":
                    j += 1
                i = j
                line += 1
                col = 1
                continue
        if c == "$":
            toks.append(Token(TokenKind.DOLLAR, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == ":":
            toks.append(Token(TokenKind.COLON, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == ",":
            toks.append(Token(TokenKind.COMMA, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == ";":
            toks.append(Token(TokenKind.SEMI, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == ".":
            toks.append(Token(TokenKind.DOT, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == "(":
            toks.append(Token(TokenKind.LPAREN, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == ")":
            toks.append(Token(TokenKind.RPAREN, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == "[":
            toks.append(Token(TokenKind.LBRACK, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == "]":
            toks.append(Token(TokenKind.RBRACK, c, line, col))
            i, col = i + 1, col + 1
            continue
        if c == '"':
            m = r_string_dq.match(text, i)
            if not m:
                raise ValueError(f"unclosed string at {line}:{col}")
            raw = m.group(0)
            toks.append(Token(TokenKind.STRING, raw, line, col))
            nlines = raw.count("\n")
            if nlines:
                line += nlines
                col = 1
            i = m.end()
            col = col + len(m.group(0))
            continue
        if c == "'":
            m = r_string_sq.match(text, i)
            if not m:
                raise ValueError("unclosed string", line, col)  # noqa: EM102
            raw = m.group(0)
            toks.append(Token(TokenKind.STRING, raw, line, col))
            nlines = raw.count("\n")
            if nlines:
                line += nlines
                col = 1
            i = m.end()
            col = col + len(m.group(0))
            continue
        if c in "=!<>":
            if c == "=" and i + 1 < n and text[i + 1] == "=":
                toks.append(Token(TokenKind.EQ, "==", line, col))
                i, col = i + 2, col + 2
                continue
            if c == "=":
                toks.append(Token(TokenKind.ASSIGN, "=", line, col))
                i, col = i + 1, col + 1
                continue
            if c == "!" and i + 1 < n and text[i + 1] == "=":
                toks.append(Token(TokenKind.NE, "!=", line, col))
                i, col = i + 2, col + 2
                continue
            if c == "<" and i + 1 < n and text[i + 1] == "=":
                toks.append(Token(TokenKind.LE, "<=", line, col))
                i, col = i + 2, col + 2
                continue
            if c == ">" and i + 1 < n and text[i + 1] == "=":
                toks.append(Token(TokenKind.GE, ">=", line, col))
                i, col = i + 2, col + 2
                continue
            if c == "<":
                toks.append(Token(TokenKind.LT, "<", line, col))
            elif c == ">":
                toks.append(Token(TokenKind.GT, ">", line, col))
            i, col = i + 1, col + 1
            continue
        m = r_number.match(text, i)
        if m:
            t = m.group(0)
            toks.append(Token(TokenKind.NUMBER, t, line, col))
            nchars = len(t)
            i = m.end()
            col = col + nchars
            continue
        m = r_ident.match(text, i)
        if m:
            word = m.group(0)
            k = _KEYWORDS.get(word, TokenKind.IDENT)
            toks.append(Token(k, word, line, col))
            nchars = len(word)
            i = m.end()
            col = col + nchars
            continue
        raise ValueError(f"Unexpected character {c!r} at {line}:{col}")
    toks.append(Token(TokenKind.EOF, "", line, col))
    return toks