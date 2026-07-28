"""An MCP server exposing the certificate toolchain to AI agents.

Why this exists: an agent that edits a design, or a proof, or a benchmark
configuration has no way to check its own work. It will confidently report
success. These tools give it something it cannot talk its way past — a verdict
re-derived from the artifact rather than asserted about it.

Every tool here is **local and read-only**. Nothing is uploaded, no network is
touched, and none of them can produce a certificate — only check one. That
asymmetry is deliberate.

Implemented against the MCP stdio protocol using only the standard library, so it
runs anywhere Python does with no dependency tree to audit.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "certified-mcp"
SERVER_VERSION = "1.0.0"

TOOLS: Dict[str, dict] = {}
HANDLERS: Dict[str, Callable[[dict], Any]] = {}


def tool(name: str, description: str, schema: dict):
    def deco(fn):
        TOOLS[name] = {"name": name, "description": description, "inputSchema": schema}
        HANDLERS[name] = fn
        return fn
    return deco


def _str(o) -> str:
    return o if isinstance(o, str) else json.dumps(o, indent=2, sort_keys=True, default=str)


# ---------------------------------------------------------------- tools

@tool("verify_certificate",
      "Verify a manufacturing certificate bundle. Re-derives the admission verdict from the "
      "certificate's own numbers rather than reading it, and checks integrity. Returns a "
      "verdict: VERIFIED, REFUTED, VACUOUS, or UNVERIFIED. IMPORTANT: without an "
      "expected_sha256 (a fingerprint obtained OUT OF BAND, not from the bundle itself) the "
      "verdict is UNVERIFIED — the tool abstains, because internal consistency alone cannot "
      "rule out a forgery whose inputs and verdict were edited together. UNVERIFIED means "
      "'cannot tell', NOT 'the certificate is bad'. Do not report it as either pass or fail.",
      {"type": "object",
       "properties": {
           "bundle_dir": {"type": "string", "description": "Path to the bundle directory."},
           "expected_sha256": {"type": "string",
                               "description": "The out-of-band fingerprint — the trust anchor. "
                                              "Without it the tool abstains."},
           "allow_empty": {"type": "boolean", "default": False},
           "accept_without_anchor": {
               "type": "boolean", "default": False,
               "description": "Accept the weaker internal-consistency check on purpose."}},
       "required": ["bundle_dir"]})
def _verify_certificate(args: dict):
    import lcert_verify as L
    res = L.verify_bundle(args["bundle_dir"], args.get("expected_sha256", ""),
                          require_certs=not args.get("allow_empty", False),
                          require_anchor=not args.get("accept_without_anchor", False))
    return {k: v for k, v in res.items() if k != "rows"}


@tool("verify_receipt",
      "Verify a logic-equivalence receipt. Re-runs the DRAT proof check (or re-simulates the "
      "counterexample) over the committed formula, and recomputes the hash chain. The verdict is "
      "re-derived, never read from the receipt.",
      {"type": "object",
       "properties": {"receipt_path": {"type": "string"}},
       "required": ["receipt_path"]})
def _verify_receipt(args: dict):
    import equiv_receipt as E
    r = E.verify_receipt(json.loads(Path(args["receipt_path"]).read_text()))
    return {"ok": r["ok"], "verdict": r["verdict"], "errors": r["errors"],
            "detail": r.get("detail")}


@tool("prove_equivalence",
      "Prove two small combinational circuits equivalent, or return a counterexample input. "
      "Circuits are given as gate lists over named signals. Returns a receipt any third party can "
      "re-check. Small instances only — this is a demonstration prover, not a production one.",
      {"type": "object",
       "properties": {
           "inputs": {"type": "array", "items": {"type": "string"},
                      "description": "Primary input names, e.g. [\"a\",\"b\"]."},
           "circuit_a": {"type": "array", "items": {"type": "object"},
                         "description": "Gates: {op: AND|OR|NOT|XOR, out: name, args: [names]}."},
           "circuit_b": {"type": "array", "items": {"type": "object"}},
           "out_path": {"type": "string", "description": "Optional path to write the receipt."}},
       "required": ["inputs", "circuit_a", "circuit_b"]})
def _prove_equivalence(args: dict):
    import equiv_receipt as E

    def builder(gates):
        def build(net, prefix):
            last = None
            for g in gates:
                op, out = g["op"].upper(), prefix + g["out"]
                a = [x if x in args["inputs"] else prefix + x for x in g["args"]]
                if op == "NOT":
                    net.NOT(out, a[0])
                elif op in ("AND", "OR", "XOR"):
                    getattr(net, op)(out, a[0], a[1])
                else:
                    raise ValueError(f"unsupported gate {op!r}")
                last = g["out"]
            return prefix + last
        return build

    r = E.prove_equivalence(builder(args["circuit_a"]), builder(args["circuit_b"]),
                            args["inputs"], name_a="circuit_a", name_b="circuit_b")
    res = E.verify_receipt(r)
    out = {"verdict": res["verdict"], "receipt_verifies": res["ok"]}
    meta = next((rec.get("meta") for rec in r["records"] if rec.get("kind") == "meta"), None)
    if meta and "differing_input_assignment" in meta:
        out["counterexample"] = meta["differing_input_assignment"]
    if args.get("out_path"):
        E.write_receipt(args["out_path"], r)
        out["written"] = args["out_path"]
    return out


@tool("check_drat",
      "Check a DRAT refutation against a CNF in DIMACS form. Accepts proofs from any solver. "
      "Returns whether every lemma is RUP and, on failure, the index and content of the first "
      "lemma that does not follow.",
      {"type": "object",
       "properties": {"cnf_path": {"type": "string"}, "drat_path": {"type": "string"}},
       "required": ["cnf_path", "drat_path"]})
def _check_drat(args: dict):
    import equiv_receipt as E
    clauses = E.parse_dimacs(Path(args["cnf_path"]).read_text())
    return E.forward_rup_check(clauses, Path(args["drat_path"]).read_text())


@tool("seal_criteria",
      "Seal an acceptance specification BEFORE measuring, so it cannot be adjusted afterward. "
      "Returns a digest that commits to the criteria without revealing them. Call this before "
      "running an experiment, not after.",
      {"type": "object",
       "properties": {"spec": {"type": "object"},
                      "out_path": {"type": "string"},
                      "note": {"type": "string"}},
       "required": ["spec"]})
def _seal_criteria(args: dict):
    import prereg_seal as P
    s = P.seal(args["spec"], note=args.get("note", ""))
    if args.get("out_path"):
        P.write_seal(args["out_path"], args["spec"], note=args.get("note", ""))
        s = dict(s, written=args["out_path"])
    return s


@tool("check_seal",
      "Check that an acceptance specification still matches its seal. Detects criteria that were "
      "changed after sealing. Returns matched=false with the two digests if they diverge.",
      {"type": "object",
       "properties": {"spec": {"type": "object"}, "seal_path": {"type": "string"},
                      "seal": {"type": "object"}},
       "required": ["spec"]})
def _check_seal(args: dict):
    import prereg_seal as P
    sealed = args.get("seal") or P.read_seal(args["seal_path"])
    try:
        P.verify(args["spec"], sealed)
        return {"matched": True, "digest": sealed["digest"]}
    except P.SealMismatch as e:
        return {"matched": False, "reason": str(e),
                "recomputed": P.digest(args["spec"]), "sealed": sealed.get("digest")}


@tool("score_verifier",
      "Score a verifier command against the certificate failure atlas. Returns detection "
      "(forgeries rejected), precision (valid artifacts accepted), and atlas_score = the minimum "
      "of the two, plus exactly which forgeries got through.",
      {"type": "object",
       "properties": {
           "atlas_dir": {"type": "string"},
           "command": {"type": "array", "items": {"type": "string"},
                       "description": "argv with {path} as the artifact placeholder."}},
       "required": ["atlas_dir", "command"]})
def _score_verifier(args: dict):
    import cert_atlas as A
    res = A.score(args["atlas_dir"], A.command_verifier(args["command"]))
    return {k: v for k, v in res.items() if k != "rows"}


@tool("explain_defect",
      "Explain a certificate defect class from the atlas taxonomy: why the forgery looks valid, "
      "and which check catches it. Call with no key to list every defect.",
      {"type": "object", "properties": {"key": {"type": "string"}}})
def _explain_defect(args: dict):
    import cert_atlas as A
    if not args.get("key"):
        return {k: v.title for k, v in A.DEFECTS.items()}
    d = A.DEFECTS.get(args["key"])
    if d is None:
        return {"error": f"unknown defect {args['key']!r}",
                "known": sorted(A.DEFECTS)}
    return {"key": d.key, "family": d.family, "severity": d.severity, "title": d.title,
            "why_it_looks_valid": d.why_it_looks_valid, "caught_by": d.caught_by,
            "tags": list(d.tags)}


# ---------------------------------------------------------------- protocol

def handle(req: dict) -> dict | None:
    """Handle one JSON-RPC request. Returns None for notifications."""
    method, rid = req.get("method"), req.get("id")

    def ok(result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL_VERSION,
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION}})
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return ok({"tools": list(TOOLS.values())})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        if name not in HANDLERS:
            return err(-32602, f"unknown tool {name!r}")
        try:
            out = HANDLERS[name](params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": _str(out)}],
                       "isError": False})
        except Exception as exc:
            return ok({"content": [{"type": "text",
                                    "text": f"{type(exc).__name__}: {exc}"}],
                       "isError": True})
    if method == "ping":
        return ok({})
    return err(-32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        try:
            resp = handle(req)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            continue
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0


def main(argv=None) -> int:
    return serve()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
