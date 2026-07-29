# Contributing to certified-mcp

This package is part of [certified-oss][p]. **The portfolio-wide guide is
[CONTRIBUTING.md][c] and it is the one to read** — it covers the rules that are not negotiable,
how to install packages that depend on each other, and what kind of contribution is most wanted
(a forgery this project fails to catch).

What is specific to this package:

- **No tool may mint a certificate.** `test_no_tool_can_mint_a_certificate` asserts it. The server
  exposes checking, never producing.
- **Every tool must be able to abstain.** An MCP tool that can only say yes or no will teach the
  model to treat absence of evidence as evidence.

## Working on it

```bash
pip install -e ".[test]"
pytest -q
ruff check .
```

## Licence

Apache-2.0. By contributing you agree your contribution is licensed the same way.

[p]: https://github.com/nickharris808/certified-oss
[c]: https://github.com/nickharris808/certified-oss/blob/main/CONTRIBUTING.md
