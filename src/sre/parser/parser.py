from __future__ import annotations

from sre.model.rule import DEFAULT_AGENDA_GROUP
from sre.parser.ast import (
    Action,
    BinaryOp,
    BinaryOperator,
    CallExpr,
    FactPattern,
    Identifier,
    InExpr,
    ListExpr,
    Literal,
    Not,
    ParseError,
    RuleAst,
    Expr,
)
from sre.parser.lexer import Token, TokenKind, tokenize


def _unquote(s: str) -> str:
    if len(s) < 2:
        return s
    q = s[0]
    if q not in '"\'':
        return s
    body = s[1:-1]
    return bytes(body, "utf-8").decode("unicode_escape")


def _collect_idents(expr: Expr) -> set[str]:
    from sre.parser import ast as A

    out: set[str] = set()

    def visit(e: Expr) -> None:
        if isinstance(e, A.Identifier):
            out.add(e.name)
        elif isinstance(e, A.BinaryOp):
            visit(e.left)
            visit(e.right)
        elif isinstance(e, A.Not):
            visit(e.expr)
        elif isinstance(e, A.ListExpr):
            for it in e.items:
                visit(it)
        elif isinstance(e, A.InExpr):
            visit(e.left)
            visit(e.right)
        elif isinstance(e, A.CallExpr):
            for a in e.args:
                visit(a)
        elif isinstance(e, A.Literal):
            pass
        else:
            pass

    visit(expr)
    return out


def _bind_root(n: str) -> str:
    if n.startswith("$"):
        return n[1:].split(".", 1)[0]
    return n.split(".", 1)[0]


def _check_resolve(expr: Expr | None, bindings: set[str], *, err_tok: Token) -> None:
    if expr is None:
        return
    for n in _collect_idents(expr):
        if n == "result" or n.startswith("result."):
            continue
        if _bind_root(n) in bindings:
            continue
        raise ParseError(
            f"unresolved identifier: {n}", err_tok.line, err_tok.col
        )


class DrlParser:
    def __init__(self) -> None:
        self._toks: list[Token] = []
        self._i: int = 0

    def _peek(self) -> Token:
        return self._toks[self._i]

    def _advance(self) -> Token:
        t = self._toks[self._i]
        if self._i < len(self._toks) - 1:
            self._i += 1
        return t

    def _match(self, *kinds: TokenKind) -> bool:
        return self._peek().kind in kinds

    def _expect(self, *kinds: TokenKind) -> Token:
        t = self._peek()
        if t.kind not in kinds:
            raise ParseError(
                f"expected {kinds} got {t.kind} {t.text!r}",
                t.line,
                t.col,
            )
        return self._advance()

    def parse(self, text: str) -> RuleAst:
        self._toks = tokenize(text)
        self._i = 0
        return self._parse_rule()

    def _parse_rule(self) -> RuleAst:
        rule_tok = self._expect(TokenKind.RULE)
        if self._match(TokenKind.STRING):
            name = _unquote(self._expect(TokenKind.STRING).text)
        else:
            name = self._expect(TokenKind.IDENT).text
        salience = 0
        agenda = DEFAULT_AGENDA_GROUP
        act_group: str | None = None
        pass_name: str | None = None
        group_by: tuple[str, ...] = ()
        reason_codes: tuple[str, ...] = ()
        while self._match(
            TokenKind.SALIENCE,
            TokenKind.AGENDA_GROUP,
            TokenKind.ACTIVATION_GROUP,
            TokenKind.PASS,
            TokenKind.GROUP_BY,
            TokenKind.REASON_CODES,
        ):
            k = self._advance()
            if k.kind == TokenKind.SALIENCE:
                salience = int(self._expect(TokenKind.NUMBER).text)
            elif k.kind == TokenKind.AGENDA_GROUP:
                s = self._expect(TokenKind.STRING, TokenKind.IDENT)
                agenda = _unquote(s.text) if s.kind == TokenKind.STRING else s.text
            elif k.kind == TokenKind.ACTIVATION_GROUP:
                s = self._expect(TokenKind.STRING, TokenKind.IDENT)
                act_group = _unquote(s.text) if s.kind == TokenKind.STRING else s.text
            elif k.kind == TokenKind.PASS:
                s = self._expect(TokenKind.IDENT)
                pass_name = s.text
            elif k.kind == TokenKind.GROUP_BY:
                group_by = self._parse_string_list()
            elif k.kind == TokenKind.REASON_CODES:
                reason_codes = self._parse_string_list()
        self._expect(TokenKind.WHEN)
        when = self._parse_when()
        bset: set[str] = {p.bind_name for p in when}
        for p in when:
            _check_resolve(p.constraint, bset, err_tok=rule_tok)
        self._expect(TokenKind.THEN)
        then = self._parse_then()
        self._expect(TokenKind.END)
        self._expect(TokenKind.EOF)
        return RuleAst(
            name=name,
            salience=salience,
            agenda_group=agenda,
            activation_group=act_group,
            pass_name=pass_name,
            group_by=group_by,
            reason_codes=reason_codes,
            when=when,
            then=then,
        )

    def _parse_string_list(self) -> tuple[str, ...]:
        self._expect(TokenKind.LBRACK)
        out: list[str] = []
        if not self._match(TokenKind.RBRACK):
            while True:
                s = self._expect(TokenKind.STRING, TokenKind.IDENT)
                out.append(
                    _unquote(s.text) if s.kind == TokenKind.STRING else s.text
                )
                if self._match(TokenKind.RBRACK):
                    break
                self._expect(TokenKind.COMMA)
        self._expect(TokenKind.RBRACK)
        return tuple(out)

    def _parse_when(self) -> tuple[FactPattern, ...]:
        pats: list[FactPattern] = [self._parse_pattern()]
        while self._match(TokenKind.AND):
            self._advance()
            pats.append(self._parse_pattern())
        return tuple(pats)

    def _parse_pattern(self) -> FactPattern:
        self._expect(TokenKind.DOLLAR)
        bind = self._expect(TokenKind.IDENT).text
        self._expect(TokenKind.COLON)
        ftype = self._expect(TokenKind.IDENT).text
        self._expect(TokenKind.LPAREN)
        expr: Expr | None
        if self._match(TokenKind.RPAREN):
            self._advance()
            expr = None
        else:
            expr = self._parse_or()
            self._expect(TokenKind.RPAREN)
        return FactPattern(bind, ftype, expr)

    def _parse_then(self) -> tuple[Action, ...]:
        actions: list[Action] = []
        while not self._match(TokenKind.END, TokenKind.EOF):
            path = self._parse_result_path()
            self._expect(TokenKind.ASSIGN)
            e = self._parse_or()
            if self._match(TokenKind.SEMI):
                self._advance()
            actions.append(Action(field_path=path, expr=e))
        return tuple(actions)

    def _parse_result_path(self) -> str:
        t = self._expect(TokenKind.IDENT)
        if t.text != "result":
            raise ParseError("actions must start with result.", t.line, t.col)
        parts = [t.text]
        while self._match(TokenKind.DOT):
            self._advance()
            parts.append(self._expect(TokenKind.IDENT).text)
        return ".".join(parts)

    def _parse_or(self) -> Expr:
        l = self._parse_and()
        while self._match(TokenKind.OR):
            self._advance()
            l = BinaryOp(BinaryOperator.OR, l, self._parse_and())
        return l

    def _parse_and(self) -> Expr:
        l = self._parse_not()
        while self._match(TokenKind.AND):
            self._advance()
            l = BinaryOp(BinaryOperator.AND, l, self._parse_not())
        return l

    def _parse_not(self) -> Expr:
        if self._match(TokenKind.NOT):
            self._advance()
            return Not(self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> Expr:
        l = self._parse_add()
        while True:
            t = self._peek()
            if t.kind in (
                TokenKind.EQ,
                TokenKind.NE,
                TokenKind.LT,
                TokenKind.LE,
                TokenKind.GT,
                TokenKind.GE,
            ):
                self._advance()
                op = {
                    TokenKind.EQ: BinaryOperator.EQ,
                    TokenKind.NE: BinaryOperator.NE,
                    TokenKind.LT: BinaryOperator.LT,
                    TokenKind.LE: BinaryOperator.LE,
                    TokenKind.GT: BinaryOperator.GT,
                    TokenKind.GE: BinaryOperator.GE,
                }[t.kind]
                l = BinaryOp(op, l, self._parse_add())
                continue
            if t.kind == TokenKind.IN:
                self._advance()
                r = self._parse_add()
                l = InExpr(l, r, negated=False)
                continue
            if t.kind == TokenKind.NOT and self._i + 1 < len(self._toks) and self._toks[
                self._i + 1
            ].kind == TokenKind.IN:
                self._advance()
                self._expect(TokenKind.IN)
                r = self._parse_add()
                l = InExpr(l, r, negated=True)
                continue
            if t.kind == TokenKind.CONTAINS:
                self._advance()
                l = BinaryOp(BinaryOperator.CONTAINS, l, self._parse_add())
                continue
            if t.kind == TokenKind.MATCHES:
                self._advance()
                l = BinaryOp(BinaryOperator.MATCHES, l, self._parse_add())
                continue
            break
        return l

    def _parse_add(self) -> Expr:
        return self._parse_primary()  # no +-

    def _parse_primary(self) -> Expr:
        t = self._peek()
        if t.kind == TokenKind.STRING:
            self._advance()
            return Literal(_unquote(t.text))
        if t.kind == TokenKind.NUMBER:
            self._advance()
            s = t.text
            v: object = float(s) if "." in s or "e" in s.lower() else int(s)
            return Literal(v)
        if t.kind == TokenKind.TRUE:
            self._advance()
            return Literal(True)
        if t.kind == TokenKind.FALSE:
            self._advance()
            return Literal(False)
        if t.kind == TokenKind.NULL:
            self._advance()
            return Literal(None)
        if t.kind == TokenKind.LPAREN:
            self._advance()
            e = self._parse_or()
            self._expect(TokenKind.RPAREN)
            return e
        if t.kind == TokenKind.LBRACK:
            self._advance()
            items: list[Expr] = []
            if not self._match(TokenKind.RBRACK):
                while True:
                    items.append(self._parse_or())
                    if self._match(TokenKind.RBRACK):
                        break
                    self._expect(TokenKind.COMMA)
            self._expect(TokenKind.RBRACK)
            return ListExpr(tuple(items))
        if t.kind == TokenKind.DOLLAR:
            self._advance()
            rest = self._expect(TokenKind.IDENT).text
            name = f"${rest}"
            return self._ident_suffix(Identifier(name))
        if t.kind == TokenKind.IDENT:
            self._advance()
            name = t.text
            if self._match(TokenKind.LPAREN):
                self._advance()
                args: list[Expr] = []
                if not self._match(TokenKind.RPAREN):
                    while True:
                        args.append(self._parse_or())
                        if self._match(TokenKind.RPAREN):
                            break
                        self._expect(TokenKind.COMMA)
                self._expect(TokenKind.RPAREN)
                return CallExpr(name, tuple(args))
            return self._ident_suffix(Identifier(name))
        raise ParseError(f"Unexpected token {t.kind} {t.text!r}", t.line, t.col)

    def _ident_suffix(self, first: Expr) -> Expr:
        if not isinstance(first, Identifier):
            return first
        name = first.name
        while self._match(TokenKind.DOT):
            self._advance()
            sub = self._expect(TokenKind.IDENT).text
            name = f"{name}.{sub}"
        return Identifier(name)


def parse(text: str) -> RuleAst:
    return DrlParser().parse(text)
