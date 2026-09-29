# gha-expr

Pure-Python evaluator for GitHub Actions `${{ }}` expressions, following the official `@actions/expressions` implementation.

```python
import gha_expr

ctx = {"github": {"ref": "refs/heads/main", "run_number": 7}, "matrix": {"node": [18, 20]}}

gha_expr.evaluate("startsWith(github.ref, 'refs/heads/') && matrix.node[1] >= 20", ctx)  # True
gha_expr.interpolate("build-${{ github.run_number }}-${{ join(matrix.node, '.') }}", ctx)  # 'build-7-18.20'
```

## Why

No package on PyPI evaluates these expressions. The reference implementation is TypeScript
(`@actions/expressions`, in `actions/languageservices`) and the runner is C#. Python projects that
need to evaluate `if:` conditions, `matrix` includes or `format()` calls offline either shell out to
Node or embed a small subset evaluator.

The reference is JavaScript, so its behavior includes JavaScript details: `Number()` string parsing
(hex, `1e400`, whitespace), `Number::toString` formatting (`1e+21`, `1e-7`), UTF-16 string ordering,
`JSON.stringify` and `JSON.parse` rules, and case-insensitive object keys with first-key-wins.
An evaluator that does not reproduce them agrees on ordinary workflows and disagrees on edge cases.

Measured: `python bench/compare_incumbent.py --incumbent-python <venv>/bin/python --seed N`, which
generates 20,000 random expressions, evaluates them with `@actions/expressions` 0.3.61 and with each
Python implementation, and counts cases where both give the same value (or both fail). The 2,061 to
2,099 cases per seed that call `hashFiles`, `success`, `failure`, `always` or `cancelled` are excluded because
the incumbent does not implement them.

```
seed=1 cases=17901   incumbent: 17035/17901 = 95.16%   gha-expr: 17901/17901 = 100.00%
seed=2 cases=17939   incumbent: 17087/17939 = 95.25%   gha-expr: 17939/17939 = 100.00%
seed=3 cases=17908   incumbent: 17044/17908 = 95.18%   gha-expr: 17908/17908 = 100.00%
```

Incumbents checked:

| Package | Where | Notes | Agreement with the reference (this repo's generator) |
| --- | --- | --- | --- |
| `py_actions_expressions_parser` (tomasrollo, commit `b833b39`) | git only, 0 stars, not on PyPI | Full port. Accepts `1_0`, errors on `1e400`, prints `1e-07` and `1e21` unlike JS, escapes non-ASCII in `toJSON`, accepts `fromJSON('NaN')`. No `hashFiles` or status functions. | 95.16% to 95.25% |
| Subset evaluators inside other repositories (for example `scszcoder/eCan.ai`, `abicheck/abicheck`) | source files, not installable | Not measured. | not measured |
| PyPI names `gha-*`, `github-actions-expr*`, `actions-expr*`, `ghaexpr*` | PyPI | Name lists and summaries checked. The `gha-*` packages are workflow linters, pinners and runners. `tree-sitter-gh-actions-expressions` is a grammar. None evaluates expressions. | none |

## Installation

```
pip install gha-expr
```

Python 3.11 or newer. No runtime dependencies.

## Usage

### Evaluate an expression

`evaluate` takes the text between `${{` and `}}` and a mapping of context names to values.
Context values are `None`, `bool`, `int`/`float`, `str`, `list` and `dict`.

```python
gha_expr.evaluate("github.event_name == 'push' && !contains(github.ref, 'wip')", ctx)
gha_expr.evaluate("fromJSON(env.MATRIX).include[*].os", {"env": {"MATRIX": '{"include": [{"os": "linux"}]}'}})
```

`&&` and `||` return an operand, not a boolean: `evaluate("null || 'x'")` is `'x'`.

### Status functions and hashFiles

`success()`, `failure()` and `cancelled()` read the `status` argument. `always()` is true. `hashFiles`
calls the `hash_files` hook with its patterns as strings.

```python
gha_expr.evaluate("failure() && github.ref == 'refs/heads/main'", ctx, status="failure")
gha_expr.evaluate("hashFiles('**/package-lock.json')", ctx, hash_files=lambda patterns: "abc123")
```

### Interpolate a string

`interpolate` finds `${{ }}` in a string the way the runner does and converts each result to a string.
`evaluate_template` returns the typed value when the whole string is one expression.

```python
gha_expr.interpolate("v${{ github.run_number }}", ctx)          # 'v7'
gha_expr.evaluate_template("${{ matrix.node }}", ctx)           # [18, 20]
gha_expr.evaluate_template("${{ matrix.node }} x", ctx)         # 'Array x'
```

### Parse without evaluating

```python
tree = gha_expr.parse("github.ref == 'main'", contexts=["github"])
# Binary(left=IndexAccess(expr=ContextAccess(name='github'), index=Literal(value='ref')),
#        operator='==', right=Literal(value='main'))
gha_expr.evaluate(tree, ctx)
```

### Handle errors

```python
try:
    gha_expr.evaluate("format('{0')", ctx)
except gha_expr.ExpressionError as exc:
    exc.kind   # 'evaluation'; 'lexing' and 'parsing' for syntax errors
    str(exc)   # 'The following format string is invalid: {0'
```

Syntax error messages match the reference, including the position suffix:
`Unexpected symbol: ')'. Located at position 5 within expression: 1 < )`.

## Reference

### Functions

| Name | Description |
| --- | --- |
| `evaluate(expression, context=None, *, hash_files=None, status="success", functions=())` | Evaluate an expression string, or a tree from `parse`. An empty expression gives `None`. |
| `parse(expression, contexts=None, *, extra_functions=None)` | Return a syntax tree, or `None` for an empty expression. `contexts` restricts top-level names (case-insensitive); `None` allows any. |
| `evaluate_template(template, context=None, *, hash_files=None, status="success", functions=())` | Evaluate `${{ }}` inside a string. Returns the typed value for a single-expression template, otherwise a string. |
| `interpolate(template, context=None, *, ...)` | Same as `evaluate_template`, always returns `str`. |
| `coerce_string(value)` | The expression string conversion: `None` is `""`, `True` is `"true"`, arrays are `"Array"`, objects are `"Object"`, numbers use the rules below. |
| `number_to_string(x)` | Number to string as expressions do it: at most 15 fractional digits, then JavaScript formatting. |
| `js_number_to_string(x)` | ECMAScript `Number::toString` (used by `toJSON`). |

### Options of `evaluate`

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `context` | `Mapping[str, Any]` | `{}` | Context names and values. Names are case-insensitive. |
| `hash_files` | `Callable[[list[str]], str]` | `None` | Implements `hashFiles`. Without it, calling `hashFiles` raises `ExpressionEvaluationError`. |
| `status` | `"success"`, `"failure"`, `"cancelled"` | `"success"` | Drives `success()`, `failure()`, `cancelled()`. |
| `functions` | `Iterable[Function]` | `()` | Extra functions, `Function(name, min_args, max_args, call)`. Arity is checked at parse time. |

### Supported syntax

- Literals: `null`, `true`, `false`, numbers (decimal, exponent, `0x`, `0o`, `0b`, leading `+`/`-`, `Infinity`, `NaN`), single-quoted strings with `''`.
- Operators: `!`, `<`, `<=`, `>`, `>=`, `==`, `!=`, `&&`, `||`, parentheses.
- Access: `a.b`, `a['b']`, `a[0]`, `a.*`, `a[*]`, case-insensitive keys, `null` for missing values.
- Functions: `contains`, `startsWith`, `endsWith`, `format`, `join`, `toJSON`, `fromJSON`, `case`, `hashFiles`, `success`, `failure`, `always`, `cancelled`.

### Exceptions

| Class | `kind` | Raised when |
| --- | --- | --- |
| `ExpressionSyntaxError` | `"lexing"`, `"parsing"` | The text cannot be tokenized or parsed. `position` is the 1-based column in UTF-16 units. |
| `ExpressionEvaluationError` | `"evaluation"` | Evaluation fails (`format`, `fromJSON`, `case`, missing `hashFiles` hook). |
| `TemplateError` | `"template"` | A `${{` has no closing `}}`, or an expression is empty. |

All three subclass `ExpressionError`.

### Syntax tree

`gha_expr.ast` has frozen dataclasses: `Literal`, `ContextAccess`, `Star`, `IndexAccess`,
`FunctionCall`, `Grouping`, `Unary`, `Binary` and `Logical` (a flat `&&` or `||` chain).

## How it works

The code is a close port of the lexer, parser, evaluator and built-in functions of
`@actions/expressions` (0.3.61, `actions/languageservices` at `4043eda`). The JavaScript semantics
are reimplemented in Python rather than approximated:

- `Number(string)` is a regular-expression grammar with the same accepted forms.
- Number to string does `+x.toFixed(15)` with exact half-up rounding on the double's true value,
  then ECMAScript shortest round-trip formatting.
- `<` and `>` on strings compare uppercased UTF-16 code units. The dotless `i` is not uppercased.
- Objects keep insertion order, but `toJSON` and `fromJSON` order integer-like keys first, as
  JavaScript objects do. Keys are case-insensitive with the first spelling winning, and keys named
  `constructor` or `__proto__` never exist, as in the reference.
- Reference quirks are kept on purpose: only the first `''` inside a string literal collapses,
  `format('{0abc}', x)` is accepted, `contains` on an array uses `==` (case-insensitive), and a
  filter like `a.*.b` produces a new array each time, so `a.*.b == a.*.b` is false.

The template helper follows `TemplateReader.ParseScalar` from `actions/runner`: it finds `${{`,
tracks quoted strings when looking for `}}`, trims the expression, and treats a template that is
one quoted string as that string.

## Limitations

- Numbers produced by the evaluator are `float`. Values taken from the context are returned as
  given, so `evaluate("x", {"x": 5})` returns the `int` `5`.
- Function names `constructor(...)` and `__proto__(...)` are rejected as unknown. The reference
  accepts them at parse time (checked with `constructor(1)` and `__proto__(1)`) because it looks
  names up on a plain JavaScript object, then returns a non-expression value or fails with
  `f.call is not a function`.
- Nesting deeper than about 1,000 levels (arrays in `fromJSON`, or values in `toJSON`) fails with an
  evaluation error. The reference fails between 2,000 and 3,000 levels on Node 24.
- The reference can overflow the JavaScript stack on a long `==` chain (seen once at 3,000
  operators, and not reproducible: the same chain and a 5,000-operator chain then evaluated).
  This library evaluates chains up to the 21,000-character expression limit.
- Upper- and lower-casing uses Python's Unicode tables, and the reference uses Node's. They can
  differ for characters added in newer Unicode versions. The tests use characters from Unicode 11
  and earlier.
- `hashFiles` and the status functions are supplied by the caller. Nothing tracks steps or reads files.
- The template helper is written from the runner source and unit-tested. The oracle has no
  equivalent, so it is not differentially tested.
- Runner directives (`${{ insert }}`) and the runner's memory limits are not implemented.
- Context names are validated against the mapping you pass, not against the list GitHub allows in
  each workflow location.

## Compatibility

Run: Python 3.14.7 on macOS, Node 24.20.0 with `@actions/expressions` 0.3.61. The CI workflow runs
Python 3.11, 3.12, 3.13 and 3.14. Only 3.14.7 has been run here.

The official fixtures (`actions/languageservices`, `expressions/testdata` at `4043eda`) pass 1015 of
1015 cases. The five cases the upstream TypeScript runner skips are not asserted: four are
multi-line position cases that follow the C# convention, one is a C# memory limit.

## Development

```
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
(cd tests/oracle && npm ci)        # oracle for the live differential tests
.venv/bin/python -m pytest
.venv/bin/mypy --strict
.venv/bin/python tests/differential.py --n 20000 --seed 1     # standalone differential
```

`pytest` fetches the official fixtures into `tests/_cache` (gitignored) from a pinned commit and
checks each file's sha256. It skips with a warning when offline. The live differential tests skip
with a warning when `node` or `tests/oracle/node_modules` is missing. `tests/data/differential.json`
is a recorded subset (1,500 cases) of the generated corpus with the oracle's answers, so the
comparison still runs without Node. `tests/gen_corpus.py` is the generator.

## License

MIT. See [LICENSE](LICENSE). Parts are derived from `actions/languageservices` and `actions/runner`
(both MIT, Copyright GitHub); their licenses are in
[LICENSE-actions-languageservices](LICENSE-actions-languageservices) and
[LICENSE-actions-runner](LICENSE-actions-runner).
