"""Random expression generator for the differential test against @actions/expressions.

Deterministic for a given seed. ``generate(seed, n)`` returns
``(contexts, cases)`` in the input format of ``oracle/oracle.mjs``.
"""

from __future__ import annotations

import random
from typing import Any

CONTEXTS: dict[str, Any] = {
    "main": {
        "github": {
            "event_name": "push",
            "ref": "refs/heads/Main",
            "run_number": 42,
            "n": 1.5,
            "neg": -3,
            "flag": True,
            "off": False,
            "none": None,
            "empty": "",
            "zero": 0,
            "list": [1, "two", None, True, {"a": 1}, [7, 8]],
            "numlist": [3, 1, 2],
            "strlist": ["Alpha", "beta", "GAMMA"],
            "emptylist": [],
            "emptyobj": {},
            "nested": {"a": {"b": [{"c": 1}, {"c": 2}, {"d": 3}]}, "A": "dup-first", "z": [[1, 2], [3]]},
            "dup": {"Key": "first", "KEY": "second", "key": "third"},
            "constructor": "hidden",
            "Mixed": {"KeY": "v", "other-key": 5, "under_score": 6},
            "num_str": "12",
            "ws": " 12 ",
            "hex": "0x10",
            "exp": "1e3",
            "big": 1e300,
            "tiny": 5e-324,
            "frac": 0.1,
            "third": 0.30000000000000004,
            "unicode": "Straße Σ İ ı \U0001f600",
            "objs": [{"n": "x", "v": 1}, {"n": "y", "v": 2}, {"n": "z"}],
            "bools": [True, False, True],
            "event": {"head_commit": {"message": "fix: thing\n\nbody", "id": "abc123"}, "labels": [{"name": "bug"}, {"name": "Docs"}]},
        },
        "env": {"FOO": "bar", "Empty": "", "NUM": "7", "PATH": "/usr/bin"},
        "inputs": {"debug": True, "level": "warn", "count": 3, "tags": ["a", "b"], "opt": None, "n": 2.5},
        "matrix": {"os": "ubuntu-latest", "node": [14, 16, 18], "include": [{"os": "win", "v": 1}]},
        "steps": {"build": {"outputs": {"result": "ok", "n": "5"}, "conclusion": "success"}},
        "runner": {"os": "Linux", "arch": "X64", "temp": "/tmp"},
        "job": {"status": "success"},
        "vars": {},
    },
    "one": {"github": {"a": 1, "b": [1, 2], "c": {"d": "e"}}},
    "empty": {},
}

_PATHS = [
    "github", "github.event_name", "github.ref", "github.run_number", "github.n", "github.neg", "github.flag",
    "github.off", "github.none", "github.empty", "github.zero", "github.list", "github.list[0]", "github.list[1]",
    "github.list[2]", "github.list[4].a", "github.list[5][1]", "github.list.*", "github.list[*]", "github.numlist",
    "github.strlist", "github.emptylist", "github.emptyobj", "github.nested", "github.nested.a", "github.nested.a.b",
    "github.nested.a.b.*.c", "github.nested.a.b[*].c", "github.nested.a.b[*].d", "github.nested.a.b[1].c",
    "github.nested.z[*][0]", "github.nested.z.*", "github.nested.z[*][*]", "github.nested.*", "github.nested.a",
    "github.nested.A", "github.nested.a.*", "github.nested.*.b", "github.dup", "github.dup.key", "github.dup.KEY",
    "github.constructor", "github.Mixed.key", "github.mixed.OTHER-KEY", "github.mixed.under_score",
    "github.num_str", "github.ws", "github.hex", "github.exp", "github.big", "github.tiny", "github.frac",
    "github.third", "github.unicode", "github.objs", "github.objs.*.n", "github.objs[*].v", "github.objs[2].n",
    "github.bools", "github.event.head_commit.message", "github.event.labels.*.name", "github.event.labels[*].name",
    "github['event_name']", "github['nested']['a']['b'][0]['c']", "github[github.event_name]",
    "github['list'][1.9]", "github.list[-1]", "github.list[' 1 ']", "github.list[true]", "github.list[null]",
    "github.list['x']", "github.list[github.run_number]", "github.numlist[github.numlist[1]]",
    "github.numlist[github.numlist[0]]", "github.nested[github.nonexistent]", "github.list[github.list]",
    "env", "env.FOO", "env.foo", "env.Empty", "env.NUM", "env.MISSING", "inputs", "inputs.debug", "inputs.level",
    "inputs.count", "inputs.tags", "inputs.tags[0]", "inputs.opt", "inputs.n", "matrix", "matrix.os",
    "matrix.node", "matrix.node[*]", "matrix.node[1]", "matrix.include.*.os", "steps.build.outputs.result",
    "steps.build.outputs.n", "steps.build.conclusion", "steps.*.conclusion", "runner.os", "runner.arch",
    "runner.temp", "job.status", "vars", "vars.x", "Github.EVENT_NAME", "GITHUB.REF", "(github).ref",
    "(github.list)[0]", "(github.nested.a.b)[*].c", "github.event_name.foo", "github.event_name[0]",
    "github.flag.x", "github.run_number.*", "github.none.*", "github.none.x", "github.empty[*]", "toJSON(github).x",
    "fromJSON('{\"a\":[1,2]}').a[1]", "fromJSON('[{\"x\":1},{\"x\":2}]')[*].x", "fromJSON('{\"a\":{\"b\":3}}').*.b",
    "nosuch", "nosuch.x", "github.", "github..x", "github.*.", ".github", "github.list.[0]",
]

_NUMBERS = [
    "0", "1", "2", "10", "42", "-1", "+1", "-0", "0.5", ".5", "5.", "-.5", "+.5e1", "1.5", "0.1", "0.2", "3.14159",
    "100", "1e3", "1E3", "1e+3", "1e-3", "1e21", "1e20", "1e-6", "1e-7", "1e400", "-1e400", "1e-400", "0x0", "0x1F",
    "0XfF", "0xFFFFFFFFFFFFFFFFFF", "0b101", "0B11", "0o17", "0O7", "0b2", "0x", "0xg", "0o8", "1_0", "1__0", "1.2.3",
    "--1", "-+1", "+-1", "1e", "1e+", "e5", "123456789012345678901234567890", "9007199254740993", "9007199254740992",
    "1.7976931348623157e308", "1.7976931348623159e308", "5e-324", "2e-324", "1e-16", "0.000001", "0.0000001",
    "0.30000000000000004", "999999999999999999999", "1000000000000000000000", "123456789.123456789",
    "0.000000000000001", "0.0000000000000005", "0.0000000000000004", "4.35", "1.005", "2.5e-15", "1.1e-15",
    "Infinity", "-Infinity", "+Infinity", "NaN", "-NaN", "infinity", "nan", "0.1e1", "00", "007", "08", "-0x10",
    "0.0", "-0.0", "1.0", "100.0", "1e1", "12345678901234567890", "0.1234567890123456789", "3.0000000000000004",
    "1e15", "1e16", "123456789012345.6", "99999999999999.99", "0.99999999999999999", "4.5e-16", "6.5e-16",
]

_STRINGS = [
    "", "a", "abc", "ABC", "AbC", "true", "false", "null", "NaN", "Infinity", "-Infinity", " 12 ", "12", "0x10",
    "0b11", "0o7", "1e3", "12abc", "-1", "1.5", ".5", "5.", "+3", "1_0", "  ", "\\t7\\n", "Straße", "STRASSE",
    "İ", "ı", "i", "I", "\U0001f600", "é", "É", "Σ", "σ", "ς", "abé",
    "{0}", "{{", "}}", "a''b", "''", "'''", "x''y''z", "hello world", "Hello", "HELLO", "hello", "he", "lo", "o w",
    "å", "K", "K", "k", "ẞ", "z", "￿", "\U0001d11e", "a b", "0", "1", "2", "-0", "00", "1.0",
    "refs/heads/main", "refs/heads/Main", "refs/tags/v1", "push", "pull_request", " 12 ", "﻿5",
    " ", "-", "--", "+", "0x", "0e0", "1e1000", "1e-1000", "9007199254740993", "0.1", "0.30000000000000004",
]

_JSON_STRINGS = [
    '{"a":1}', "[1,2,3]", '"s"', "null", "true", "false", "1", "-0", "1.5", "1e400", "-1e400", "1e-400",
    '{"B":1,"b":2}', '{"2":1,"1":2,"x":3,"0":4}', '{"__proto__":1,"a":2}', '{"constructor":1,"b":2}', "NaN", "Infinity",
    "-Infinity", "[1,]", "[,1]", "{}", "[]", "", " ", "\\n", '{"a":{"b":[1,{"c":null}]}}', '"\\ud800"', '"\\u00e9\\ud83d\\ude00"',
    "01", "1 2", "[NaN]", '{"a":1,"a":2}', '{"a":1,"A":2}', '"\\u0000"', "  [1]  ", "\\t1\\n", "'a'", '{"a":}', '{a:1}',
    '"unterminated', "[1,2", '{"k":[1,2,{"z":[]}],"K":0}', "0x10", "1.", ".5", "+1", "1e5", "1E+5", "-", "\\u00a01",
    '[1.0,2.50,3e2,1e21,1e-7,0.1,123456789012345680000]', '"\\/"', '"\\x"', '"tab\\there"', '["a",null,true,{"x":[]}]',
    '{"deep":{"deeper":{"deepest":[[],{}]}}}', '{"":1}', '{" ":1}', '[[[[1]]]]', '"\\u2028"', '"é"', "12345678901234567890",
    '{"b":1,"a":{"d":2,"c":3}}', '{"10":"a","9":"b","a":"c","-1":"d","4294967295":"e","4294967294":"f"}',
]

_FORMATS = [
    "{0}", "{0} {1}", "{1} {0}", "{{0}}", "{{", "}}", "{", "}", "a{0", "{0}}", "{ 0}", "{0:x}", "{00}", "{01}",
    "{1}", "{2}", "{3}", "x{0}y{1}z", "{abc}", "{}", "{0abc}", "{{{0}}}", "{{{{0}}}}", "a}b{0}", "{0}{0}{0}",
    "{99999999999999999999999}", "no braces", "", "{0", "0}", "{{0}", "}{0}", "{0}{", "{{}}", "{0 }", "{-1}",
    "{0}\\n{1}", "%s", "{0}'{1}", "{ }", "a{{b}}c{0}", "}}{{", "{{{", "}}}", "{0}}}", "{0}{{",
]


class Gen:
    def __init__(self, rng: random.Random) -> None:
        self.r = rng

    def num(self) -> str:
        return self.r.choice(_NUMBERS)

    def string(self) -> str:
        s = self.r.choice(_STRINGS)
        return "'" + s.replace("\\t", "\t").replace("\\n", "\n") + "'"

    def json_string(self) -> str:
        s = self.r.choice(_JSON_STRINGS).replace("\\t", "\t").replace("\\n", "\n").replace("\\u00a0", " ")
        # backslash escapes in the pool are JSON escapes and must stay as written.
        return "'" + s.replace("'", "''") + "'"

    def fmt(self) -> str:
        s = self.r.choice(_FORMATS).replace("\\n", "\n")
        return "'" + s.replace("'", "''") + "'"

    def path(self) -> str:
        return self.r.choice(_PATHS)

    def leaf(self) -> str:
        c = self.r.random()
        if c < 0.22:
            return self.num()
        if c < 0.42:
            return self.string()
        if c < 0.50:
            return self.r.choice(["null", "true", "false", "TRUE", "Null", "nan"])
        return self.path()

    def expr(self, depth: int) -> str:
        if depth <= 0:
            return self.leaf()
        c = self.r.random()
        if c < 0.18:
            return self.leaf()
        if c < 0.30:
            return f"!{self.expr(depth - 1)}"
        if c < 0.58:
            op = self.r.choice(["==", "!=", "<", "<=", ">", ">=", "==", "!="])
            return f"{self.expr(depth - 1)}{self._sp()}{op}{self._sp()}{self.expr(depth - 1)}"
        if c < 0.70:
            op = self.r.choice(["&&", "||"])
            n = self.r.choice([2, 2, 3])
            return f" {op} ".join(self.expr(depth - 1) for _ in range(n))
        if c < 0.75:
            return f"({self.expr(depth - 1)})"
        return self.call(depth - 1)

    def _sp(self) -> str:
        return self.r.choice(["", " ", " ", " ", "  ", "\n", "\t"])

    def call(self, depth: int) -> str:
        r = self.r
        name = r.choice(
            ["contains", "startsWith", "endsWith", "format", "join", "toJSON", "fromJSON", "case", "hashFiles",
             "success", "failure", "always", "cancelled", "contains", "format", "toJSON", "fromJSON", "join",
             "startsWith", "endsWith", "case"]
        )
        if r.random() < 0.05:
            name = r.choice(["CONTAINS", "StartsWith", "TOJSON", "fromjson", "Format", "JOIN", "unknown", "hashfiles",
                             "toString", "len", "toJson", "endswith", "SUCCESS", "Always"])
        def e() -> str:
            return self.expr(depth)

        args: list[str]
        if name.lower() in ("success", "failure", "always", "cancelled"):
            args = [] if r.random() < 0.9 else [e()]
        elif name.lower() == "hashfiles":
            args = [e() for _ in range(r.choice([1, 1, 2, 3, 0]))]
        elif name.lower() == "format":
            args = [self.fmt() if r.random() < 0.85 else e()] + [e() for _ in range(r.choice([0, 1, 1, 2, 3]))]
        elif name.lower() == "fromjson":
            args = [self.json_string() if r.random() < 0.8 else e()]
            if r.random() < 0.04:
                args.append(e())
        elif name.lower() == "tojson":
            args = [e()]
            if r.random() < 0.03:
                args.append(e())
        elif name.lower() == "join":
            args = [self.path() if r.random() < 0.5 else e()] + ([e()] if r.random() < 0.6 else [])
            if r.random() < 0.03:
                args.append(e())
        elif name.lower() == "case":
            n = r.choice([3, 3, 5, 5, 7, 2, 4, 1])
            args = []
            for i in range(n):
                if i % 2 == 0 and i < n - 1:
                    args.append(r.choice(["true", "false", self.expr(depth) if r.random() < 0.4 else f"({e()}) == ({e()})"]))
                else:
                    args.append(e())
        else:
            args = [e() for _ in range(r.choice([2, 2, 2, 2, 1, 3]))]
        sep = r.choice([", ", ",", " , "])
        text = f"{name}({sep.join(args)})"
        if r.random() < 0.03:
            text = text[:-1] + ",)"
        return text

    def mutate(self, s: str) -> str:
        r = self.r
        pieces = ["(", ")", "[", "]", ".", ",", "'", "!", "=", "&", "|", "*", "<", ">", " ", "\n", "-", "+", "0", "a",
                  "é", "\U0001f600", "\t", " ", "$", "{", "}", "1e", "..", "==", "&&", "||", "!=", "#", "\\", "\0"]
        for _ in range(r.choice([1, 1, 2, 3])):
            if not s:
                break
            i = r.randrange(len(s) + 1)
            k = r.random()
            if k < 0.4:
                s = s[:i] + r.choice(pieces) + s[i:]
            elif k < 0.7 and i < len(s):
                s = s[:i] + s[i + 1 :]
            elif i < len(s):
                s = s[:i] + r.choice(pieces) + s[i + 1 :]
        return s

    def raw_junk(self) -> str:
        alphabet = list("ab_-.0123456789()[]'!=&|*<> \n\t,+") + ["true", "null", "github", "env", "1e5", "0x", "''", "&&", "||", "==", "!="]
        return "".join(self.r.choice(alphabet) for _ in range(self.r.randrange(1, 12)))


_ALPHABET = list(
    "aAbBzZ0 9-_iIkK\u00df\u1e9e\u0131\u0130\u00e9\u00c9\u03c3\u03a3\u03c2\u01c6\u01c5\u01c4\u0149\ufb01\ufb03"
    "\u212a\u017f\ufb00\uff5e\ue000\uffff\U00010000\U0001f600\U0001d11e\U00010400\U00010428\u0345\u1f80\u1fb3"
    "\u00b5\u039c\u03bc\u0587\u1e96\u0390\u2126\u03a9\u03c9\u10d0\u1c90\u0131\u0069\u0307"
)


def _double(rng: random.Random) -> str:
    import struct

    k = rng.random()
    if k < 0.45:
        bits = rng.getrandbits(64)
        f = struct.unpack("<d", struct.pack("<Q", bits))[0]
        if f != f or f in (float("inf"), float("-inf")):
            f = 1.5
        return repr(f)
    if k < 0.75:
        return f"{rng.random() * 10 ** rng.randint(-20, 25):.{rng.randint(1, 19)}g}"
    if k < 0.9:
        # near the toFixed(15) rounding boundary
        digits = "".join(rng.choice("0123456789") for _ in range(rng.randint(1, 4)))
        return f"0.{'0' * rng.randint(9, 14)}{digits}{rng.choice(['5', '4', '6', '49', '51', '500000001'])}"
    ip = "".join(rng.choice("0123456789") for _ in range(rng.randint(1, 24)))
    return f"{ip}.{''.join(rng.choice('0123456789') for _ in range(rng.randint(0, 20)))}"


def _numfmt(rng: random.Random) -> str:
    x = _double(rng)
    if rng.random() < 0.2:
        x = "-" + x if not x.startswith("-") else x
    return rng.choice(
        [f"format('{{0}}', {x})", f"toJSON({x})", f"'{x}' == {x}", f"join(fromJSON('[{x}]'), '')", f"contains({x}, '.')",
         f"toJSON(fromJSON('{x}'))", f"{x} < {_double(rng)}", f"toJSON(fromJSON('[{x}]'))", f"{x} == fromJSON('{x}')"]
    )


def _strcmp(rng: random.Random) -> str:
    def s() -> str:
        return "'" + "".join(rng.choice(_ALPHABET) for _ in range(rng.randint(0, 4))) + "'"

    a, b = s(), s()
    if rng.random() < 0.3:
        b = a.upper() if rng.random() < 0.5 else a.lower()
    op = rng.choice(["==", "!=", "<", ">", "<=", ">="])
    return rng.choice(
        [f"{a} {op} {b}", f"contains({a}, {b})", f"startsWith({a}, {b})", f"endsWith({a}, {b})",
         f"contains(fromJSON('[{a.replace(chr(39), chr(34))}]'), {b})", f"toJSON({a})", f"format('{{0}}', {a})"]
    )


def generate(seed: int, n: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rng = random.Random(seed)
    g = Gen(rng)
    cases: list[dict[str, Any]] = []
    for _ in range(n):
        k = rng.random()
        if k < 0.10:
            expr = _numfmt(rng)
        elif k < 0.17:
            expr = _strcmp(rng)
        elif k < 0.80:
            expr = g.expr(rng.choice([0, 1, 1, 2, 2, 3, 3, 4]))
        elif k < 0.92:
            expr = g.mutate(g.expr(rng.choice([1, 2, 3])))
        elif k < 0.97:
            expr = g.raw_junk()
        else:
            expr = g.expr(rng.choice([1, 2])) + g._sp()
        if rng.random() < 0.08:
            expr = g._sp() + expr + g._sp()
        ctx = "main" if rng.random() < 0.9 else rng.choice(["one", "empty"])
        cases.append({"expr": expr, "ctx": ctx, "status": rng.choice(["success", "failure", "cancelled"])})
    return CONTEXTS, cases
