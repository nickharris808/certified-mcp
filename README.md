# certified-mcp

[![ci](https://github.com/nickharris808/certified-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/nickharris808/certified-mcp/actions/workflows/ci.yml)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![mcp](https://img.shields.io/badge/MCP-stdio%20%7C%208%20tools-8A2BE2)
![tests](https://img.shields.io/badge/tests-21%20passing-brightgreen)

**Give your agent something it cannot talk its way past.**

An MCP server exposing certificate verification, equivalence proving, and pre-registration sealing
as tools. An agent that edits a design, a proof, or a benchmark config has no way to check its own
work — so it reports success. These tools return a verdict **re-derived from the artifact**, not
asserted about it.

## Install

> **Status: pre-release.** Not yet on PyPI. Until then, install from a checkout:
>
> ```
> pip install ./lcert-verify ./equiv-receipt ./prereg-seal ./cert-atlas ./certified-mcp
> ```

```
pip install certified-mcp
```

## 30-second quickstart

Add to your MCP client config (Claude Desktop, Cursor, or any MCP host):

```json
{
  "mcpServers": {
    "certified": { "command": "certified-mcp" }
  }
}
```

Then ask your agent something it would otherwise have to guess at:

> "I refactored this adder. Prove it's still equivalent to the original."

```
prove_equivalence(inputs=["a","b"], circuit_a=[...], circuit_b=[...])
-> {"verdict": "EQUIVALENT", "receipt_verifies": true}
```

Or, when it isn't:

```
-> {"verdict": "COUNTEREXAMPLE", "counterexample": {"1": true, "2": false}}
```

The agent gets a concrete failing input, not "this appears correct."

## Tools

| Tool | What it does |
|---|---|
| `verify_certificate` | Re-derives a manufacturing admission verdict from the certificate's own numbers; checks integrity; refuses a bundle that certifies nothing |
| `verify_receipt` | Re-runs a DRAT proof (or re-simulates a counterexample) over the committed formula |
| `prove_equivalence` | Proves two small combinational circuits equivalent, or returns a differing input |
| `check_drat` | Checks a DRAT refutation from **any** solver; names the first lemma that doesn't follow |
| `seal_criteria` | Seals acceptance criteria before measuring, without revealing them |
| `check_seal` | Detects criteria changed after sealing |
| `score_verifier` | Scores a verifier against the failure atlas |
| `explain_defect` | Explains a defect class: why the forgery looks valid, and what catches it |

## Why an agent benefits specifically

Three failure modes this addresses directly:

1. **Confident wrongness.** An agent that refactors logic will say it preserved behaviour.
   `prove_equivalence` returns a counterexample input when it didn't.
2. **Moving the goalposts.** An agent tuning against a benchmark will quietly relax the threshold.
   `seal_criteria` before the run makes that detectable — including by the agent itself.
3. **Trusting a proof it was handed.** `check_drat` accepts proofs from any solver and re-checks
   every lemma, so a fabricated proof is caught rather than cited.

## Everything here is local and read-only

No network. Nothing uploaded. No telemetry. Every tool either reads a file you name or computes
over arguments you pass.

**None of these tools can produce a manufacturing certificate** — only check one. That asymmetry is
deliberate and is enforced by a test. Checking is cheap and should be everywhere; producing a
certificate worth checking requires the certification engine, which is a separate closed product.

## Implementation

Standard library only, MCP stdio protocol, ~300 lines. You can read the whole server before
deciding to run it — which, for something you are wiring into an agent with filesystem access, you
should.

## Licence

Apache-2.0.

## Honest scope — what these tools prove, and what they do not

| Question | Answer |
|---|---|
| Can an agent check a certificate, proof or seal with these? | **Yes**, all locally and read-only. |
| Does `verify_certificate` returning `UNVERIFIED` mean the certificate is bad? | **No.** It means the tool abstained for want of a trust anchor. An agent must not report it as either pass or fail. |
| Can any tool here *produce* a certificate? | **No** — enforced by a test. These are checkers. |
| Does anything here validate physics? | **Never.** |

---

## The rest of the toolkit

One idea, six pieces: **a recorded verdict is a claim to be checked, never an input to be trusted.**

| | |
|---|---|
| [**lcert-verify**](https://github.com/nickharris808/lcert-verify) | Re-derive a manufacturing certificate's verdict. Stdlib only. |
| [**equiv-receipt**](https://github.com/nickharris808/equiv-receipt) | Prove two circuits equivalent, with a receipt anyone can re-check. |
| [**prereg-seal**](https://github.com/nickharris808/prereg-seal) | Seal acceptance criteria before you measure. |
| [**cert-atlas**](https://github.com/nickharris808/cert-atlas) | 21 labelled forgeries and a metric no degenerate verifier can win. |
| [**certified-mcp**](https://github.com/nickharris808/certified-mcp) | The above, as tools your AI agent can call. |
| [**lcert-verify-web**](https://github.com/nickharris808/lcert-verify-web) | The verifier in a browser. Nothing uploaded. |

**Try it now, no install:** [🔏 the verifier Space](https://huggingface.co/spaces/nickh007/cert-verifier) ·
**Browse the forgeries:** [📊 the atlas dataset](https://huggingface.co/datasets/nickh007/cert-atlas)

### Where the free edition stops

Everything here **checks**. None of it **produces** a certificate that is physically meaningful —
that needs sound enclosures over real process models, which is a separate commercial product. If
you need certificates rather than a way to check them, that is the conversation to have.
