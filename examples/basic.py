"""Smallest useful calls: evaluate an expression, interpolate a template."""

from __future__ import annotations

import gha_expr

context = {
    "github": {"ref": "refs/heads/main", "event_name": "push", "run_number": 7},
    "matrix": {"os": "ubuntu-latest", "node": [18, 20, 22]},
}

print(gha_expr.evaluate("github.event_name == 'push' && startsWith(github.ref, 'refs/heads/')", context))
print(gha_expr.evaluate("join(matrix.node, ', ')", context))
print(gha_expr.interpolate("build-${{ github.run_number }}-${{ matrix.os }}", context))
print(gha_expr.evaluate("toJSON(matrix)", context))
