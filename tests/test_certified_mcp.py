"""Tests for the MCP server: protocol conformance and real tool behaviour."""
from __future__ import annotations

import io
import json


import certified_mcp as M
from certified_mcp.server import handle


def call(name, args):
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": name, "arguments": args}})
    content = r["result"]["content"][0]["text"]
    try:
        return json.loads(content), r["result"]["isError"]
    except ValueError:
        return content, r["result"]["isError"]


# ---------- protocol ----------

def test_initialize_returns_protocol_and_capabilities():
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r["result"]["protocolVersion"] == M.PROTOCOL_VERSION
    assert "tools" in r["result"]["capabilities"]
    assert r["result"]["serverInfo"]["name"] == "certified-mcp"


def test_initialized_notification_gets_no_response():
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_is_wellformed():
    r = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = r["result"]["tools"]
    assert len(tools) >= 8
    for t in tools:
        assert t["name"] and t["description"]
        assert t["inputSchema"]["type"] == "object"
        # a description an agent cannot act on is a broken tool
        assert len(t["description"]) > 60


def test_unknown_method_is_an_error():
    r = handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})
    assert r["error"]["code"] == -32601


def test_unknown_tool_is_an_error():
    r = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "does_not_exist", "arguments": {}}})
    assert r["error"]["code"] == -32602


def test_tool_exception_is_reported_not_raised():
    out, is_err = call("verify_certificate", {"bundle_dir": "/nonexistent/path"})
    assert is_err is False          # the tool returns a structured failure...
    assert out["ok"] is False       # ...rather than crashing the server


# ---------- certificates ----------

def test_verify_certificate_accepts_and_rejects(tmp_path):
    import lcert_verify as L
    from lcert_verify import _verifier as V
    d = tmp_path / "b"
    c = L.gate_cert("x", budget=0.05, safety=1.5, n_photons=100.0, thr=0.30,
                    delta_dose=0.02, loci=[(0.10, 0.11, 0.05)])
    L.make_bundle(d, gate_certs=[c], kpis=[], prereg={})
    out, _ = call("verify_certificate",
                  {"bundle_dir": str(d), "expected_sha256": L.bundle_fingerprint(d)})
    assert out["ok"] is True and out["n_certificates"] == 1
    assert out["verdict"] == "VERIFIED"

    # ...and without the anchor it abstains rather than passing
    out2, _ = call("verify_certificate", {"bundle_dir": str(d)})
    assert out2["verdict"] == "UNVERIFIED" and out2["ok"] is False

    b = json.loads((d / "bundle.json").read_text())
    b["gate_certs"][0]["recorded"]["interval_admit"] = False
    (d / "bundle.json").write_bytes(V._canon(b) + b"\n")
    out, _ = call("verify_certificate", {"bundle_dir": str(d), "expected_sha256": "ab" * 32})
    assert out["ok"] is False


def test_verify_certificate_refuses_vacuous_bundle(tmp_path):
    import lcert_verify as L
    d = tmp_path / "empty"
    L.make_bundle(d, gate_certs=[], kpis=[], prereg={})
    fp = L.bundle_fingerprint(d)
    out, _ = call("verify_certificate", {"bundle_dir": str(d), "expected_sha256": fp})
    assert out["ok"] is False and out["verdict"] == "VACUOUS"
    out, _ = call("verify_certificate",
                  {"bundle_dir": str(d), "expected_sha256": fp, "allow_empty": True})
    assert out["ok"] is True


# ---------- equivalence ----------

AND_B = [{"op": "AND", "out": "y", "args": ["a", "b"]}]
DEMORGAN = [{"op": "NOT", "out": "na", "args": ["a"]},
            {"op": "NOT", "out": "nb", "args": ["b"]},
            {"op": "OR", "out": "o", "args": ["na", "nb"]},
            {"op": "NOT", "out": "y", "args": ["o"]}]
OR_B = [{"op": "OR", "out": "y", "args": ["a", "b"]}]


def test_prove_equivalence_finds_equivalence():
    out, err = call("prove_equivalence",
                    {"inputs": ["a", "b"], "circuit_a": AND_B, "circuit_b": DEMORGAN})
    assert err is False
    assert out["verdict"] == "EQUIVALENT" and out["receipt_verifies"] is True


def test_prove_equivalence_returns_a_counterexample():
    out, _ = call("prove_equivalence",
                  {"inputs": ["a", "b"], "circuit_a": AND_B, "circuit_b": OR_B})
    assert out["verdict"] == "COUNTEREXAMPLE"
    assert "counterexample" in out


def test_prove_then_verify_roundtrip(tmp_path):
    p = tmp_path / "r.json"
    out, _ = call("prove_equivalence",
                  {"inputs": ["a", "b"], "circuit_a": AND_B, "circuit_b": DEMORGAN,
                   "out_path": str(p)})
    assert out["written"] == str(p)
    out2, _ = call("verify_receipt", {"receipt_path": str(p)})
    assert out2["ok"] is True and out2["verdict"] == "EQUIVALENT"


def test_unsupported_gate_is_reported():
    bad = [{"op": "NAND", "out": "y", "args": ["a", "a"]}]
    out, is_err = call("prove_equivalence",
                       {"inputs": ["a"], "circuit_a": bad, "circuit_b": AND_B})
    assert is_err is True and "NAND" in str(out)


def test_check_drat(tmp_path):
    import equiv_receipt as E
    cnf, drat = tmp_path / "f.cnf", tmp_path / "f.drat"
    cnf.write_text(E.to_dimacs([[1, 2], [-1, 2], [1, -2], [-1, -2]]))
    drat.write_text("2 0\n0\n")
    out, _ = call("check_drat", {"cnf_path": str(cnf), "drat_path": str(drat)})
    assert out["verified"] is True
    drat.write_text("0\n")
    cnf.write_text(E.to_dimacs([[1, 2]]))
    out, _ = call("check_drat", {"cnf_path": str(cnf), "drat_path": str(drat)})
    assert out["verified"] is False


# ---------- seals ----------

def test_seal_and_check(tmp_path):
    spec = {"threshold_nm": 3.0, "corners": ["nominal"]}
    p = tmp_path / "s.json"
    out, _ = call("seal_criteria", {"spec": spec, "out_path": str(p)})
    assert "digest" in out
    out, _ = call("check_seal", {"spec": spec, "seal_path": str(p)})
    assert out["matched"] is True
    out, _ = call("check_seal", {"spec": dict(spec, threshold_nm=9.9), "seal_path": str(p)})
    assert out["matched"] is False and out["recomputed"] != out["sealed"]


def test_seal_does_not_leak_the_spec():
    out, _ = call("seal_criteria", {"spec": {"threshold_nm": 3.0, "secret_corner": "xyz"}})
    assert "xyz" not in json.dumps(out) and "3.0" not in json.dumps(out)


# ---------- atlas ----------

def test_score_verifier_against_the_atlas(tmp_path):
    import cert_atlas as A
    a = tmp_path / "atlas"
    A.build(a)
    out, _ = call("score_verifier", {"atlas_dir": str(a), "command": ["true", "{path}"]})
    assert out["atlas_score"] == 0.0        # accepts everything
    assert out["detection"] == 0.0


def test_explain_defect():
    out, _ = call("explain_defect", {"key": "receipt.swapped_cnf"})
    assert out["severity"] == "soundness"
    assert "encoder" in out["caught_by"]
    out, _ = call("explain_defect", {})
    assert len(out) >= 20


def test_explain_unknown_defect_lists_known():
    out, _ = call("explain_defect", {"key": "nope"})
    assert "known" in out


# ---------- transport ----------

def test_stdio_roundtrip():
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    stdin = io.StringIO("\n".join(json.dumps(r) for r in reqs) + "\n")
    stdout = io.StringIO()
    M.serve(stdin, stdout)
    lines = [json.loads(x) for x in stdout.getvalue().strip().splitlines()]
    assert len(lines) == 2                      # the notification produced no response
    assert lines[0]["result"]["serverInfo"]["name"] == "certified-mcp"
    assert len(lines[1]["result"]["tools"]) >= 8


def test_server_survives_malformed_input():
    stdin = io.StringIO("not json\n\n" + json.dumps(
        {"jsonrpc": "2.0", "id": 9, "method": "ping"}) + "\n")
    stdout = io.StringIO()
    M.serve(stdin, stdout)
    lines = stdout.getvalue().strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["id"] == 9


def test_no_tool_can_mint_a_certificate():
    """The moat: agents may check, never produce a manufacturing certificate."""
    names = set(M.TOOLS)
    assert not any(n.startswith(("certify", "admit", "mint", "gate_")) for n in names)
    for t in M.TOOLS.values():
        assert "produce a certificate" not in t["description"].lower()
