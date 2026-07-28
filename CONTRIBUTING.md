# Contributing

## The rules

1. **Local and read-only.** No tool may open a network connection, upload, or phone home. A PR
   adding one will be declined regardless of merit.
2. **No tool may mint a certificate.** `test_no_tool_can_mint_a_certificate` enforces this. The
   server is a checker surface.
3. **Tool descriptions are the interface.** An agent picks tools by reading them, so a vague
   description is a bug. Tests assert a minimum length; write for a reader who has no other context.
4. **Errors are returned, never raised.** A tool that throws kills the session. Return a structured
   failure and let the agent recover.
5. **Standard library only** — this gets wired into agents with filesystem access, so the audit
   surface stays small enough to read.

## Testing

```
pip install -e ".[test]"
pytest
```

`test_stdio_roundtrip` exercises the real transport. If you touch the protocol layer, also run the
server against a real MCP client before submitting.

## Installing for development

Dependencies use PEP 508 **direct references** to the public GitHub repositories, so
`pip install ./<pkg>` works for anyone today without anything being on PyPI.

That has one consequence worth knowing: you cannot install every package from local
paths in a single command, because pip sees the direct reference and the local path as
two different sources for the same name. Install the leaf packages first, then the
dependents with `--no-deps`:

```
pip install -e ./lcert-verify -e ./equiv-receipt -e ./prereg-seal
pip install --no-deps -e ./cert-atlas -e ./certified-mcp
```

For a future PyPI release the direct references become plain version specifiers and this
step disappears. That swap is deliberately not on the critical path.
