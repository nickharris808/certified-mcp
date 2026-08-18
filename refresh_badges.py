#!/usr/bin/env python3
"""Regenerate the README badges that carry a number, by running the code.

A badge saying "26 passing" over a suite of 409 is a claim the code does not
support, and that is what shipped. So the numbers are derived here, and six of
the published repositories run this with --check (lcert-verify, lcert-build,
equiv-receipt, prereg-seal, cert-atlas, certified-kit): a stale badge fails
their build rather than misleading a reader.

That defence is not universal, and saying otherwise would be the same kind of
claim this script exists to prevent. `certified-mcp` and `lcert-verify-web` run
no --check step, and `oss/spaces/` is in no workflow's matrix at all -- which is
where a stale cert-atlas figure (0.955, from a 22-forgery corpus) survived
undetected until 2026-07-31 -- the corpus now holds 28 and the reference
verifier scores 27/28 = 0.964, computed from the corpus rather than asserted. Their numbers are only as fresh as the last
hand-run of this script.

Same discipline as the generated CLI reference and the regenerated leaderboard.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PY_PACKAGES = ["lcert-verify", "lcert-build", "equiv-receipt", "prereg-seal",
               "cert-atlas", "certified-mcp", "certified-kit"]

PY_VERSIONS = "3.9 | 3.10 | 3.11 | 3.12 | 3.13"


def shield(label: str, message: str, colour: str) -> str:
    def enc(s):
        return (s.replace("-", "--").replace("_", "__").replace(" ", "%20")
                .replace("|", "%7C").replace("/", "%2F"))
    return f"https://img.shields.io/badge/{enc(label)}-{enc(message)}-{colour}"


def count_tests(pkg: Path) -> int:
    """Tests COLLECTED, by asking pytest. Not by reading a number.

    Collected rather than passed, deliberately. Some tests skip when an optional
    tool is absent — `cadical` is not on the CI runners — so a passed count is a
    property of the machine, not of the suite, and a badge asserting one would be
    stale on any environment that differs from where it was generated. Collection
    is the same everywhere.

    Whether they pass is what the CI badge beside it says.
    """
    # No -q: several packages set it in addopts, and -qq replaces the summary
    # line this function reads with a per-file listing.
    r = subprocess.run([sys.executable, "-m", "pytest", "tests", "--collect-only",
                        "-p", "no:cacheprovider", "-p", "no:regtest"],
                       cwd=pkg, capture_output=True, text=True)
    m = re.findall(r"(\d+) tests? collected", r.stdout + r.stderr)
    if not m:
        raise RuntimeError(f"could not count tests in {pkg.name}:\n"
                           f"{(r.stdout + r.stderr)[-400:]}")
    if r.returncode != 0:
        raise RuntimeError(f"{pkg.name}: collection failed; refusing to write a badge")
    return int(m[-1])


def count_conformance(pkg: Path) -> int:
    subprocess.run([sys.executable, "test/gen_fixtures.py"], cwd=pkg,
                   capture_output=True, text=True)
    r = subprocess.run(["node", "test/conformance.mjs"], cwd=pkg,
                       capture_output=True, text=True)
    m = re.search(r"(\d+) passed", r.stdout)
    if not m:
        raise RuntimeError(f"could not count conformance checks:\n{r.stdout[-400:]}")
    return int(m.group(1))


def atlas_shape(pkg: Path):
    sys.path.insert(0, str(pkg / "src"))
    import tempfile

    from cert_atlas.generate import build
    ix = build(Path(tempfile.mkdtemp()) / "a")
    return ix["n_cases"], ix["n_invalid"]


def badges_for(name: str, pkg: Path) -> dict:
    """label -> (message, colour), every number derived by running the code.

    ``pkg`` is the package directory, which differs between the development tree
    (one directory per package) and a published repository (the package IS the
    repository root) -- hence --single.
    """
    out = {
        "license": ("Apache-2.0", "blue"),
        "python": (PY_VERSIONS, "blue"),
        "dependencies": ("none", "brightgreen"),
    }
    if name == "lcert-verify-web":
        out.pop("python")
        out["node"] = ("18+", "blue")
        out["conformance"] = (f"{count_conformance(pkg)} checks vs Python", "brightgreen")
        return out
    if name == "certified-oss":
        return {"license": ("Apache-2.0", "blue"),
                "repositories": ("9", "blue"),
                "docs": ("live", "brightgreen")}
    out["tests"] = (f"{count_tests(pkg)} tests", "blue")
    if name == "cert-atlas":
        n, inv = atlas_shape(pkg)
        out["atlas"] = (f"{n} cases / {inv} forgeries", "blue")
        out["python"] = ("3.9+", "blue")
        out.pop("dependencies")
    if name in ("lcert-build", "certified-kit", "certified-mcp"):
        out.pop("dependencies", None)
        out["python"] = ("3.9+", "blue")
    if name == "certified-mcp":
        # DERIVED, not typed. This was hardcoded as "8 tools" while server.py registered 9 --
        # the one number in this file that was asserted rather than measured, in the very script
        # whose docstring says a badge the code does not support is what shipped.
        out["mcp"] = (f"stdio | {_mcp_tool_count(pkg)} tools", "8A2BE2")
    return out


def rewrite(readme: Path, name: str, badges: dict) -> str:
    text = readme.read_text()
    ci = (f"[![ci](https://github.com/nickharris808/{name}/actions/workflows/ci.yml/"
          f"badge.svg)](https://github.com/nickharris808/{name}/actions/workflows/ci.yml)")
    line = ci if "actions/workflows/ci.yml" in text else ""
    for label, (msg, colour) in badges.items():
        line += ("\n" if line else "") + f"![{label}]({shield(label, msg, colour)})"

    # Strip any existing badge lines wherever they are, then place the block
    # directly under the H1. A stranger should see what this is and that it is
    # green before reading a word of prose.
    kept = [ln for ln in text.split("\n")
            if not re.match(r"^(\[!\[ci\]|!\[[a-z]+\]\(https://img\.shields\.io)", ln)]
    while len(kept) > 1 and kept[0].strip() == "":
        kept.pop(0)
    out, placed = [], False
    for ln in kept:
        out.append(ln)
        if not placed and ln.startswith("# "):
            out.append("")
            out.append(line)
            placed = True
    if not placed:
        out = [line, ""] + out
    # collapse any run of blank lines the strip left behind
    collapsed = []
    for ln in out:
        if ln.strip() == "" and collapsed and collapsed[-1].strip() == "":
            continue
        collapsed.append(ln)
    return "\n".join(collapsed)



# ------------------------------------------------------------------ the landing page
#: (package, published repo name, one-line description). Order is the display order.
LANDING = [
    ("lcert-verify", "lcert-verify",
     "Re-derive a manufacturing certificate's verdict. Stdlib only."),
    ("lcert-build", "lcert-build",
     "Emit a certificate bundle from your own analysis."),
    ("equiv-receipt", "equiv-receipt",
     "Portable logic-equivalence receipts; DRAT checking, zero deps."),
    ("prereg-seal", "prereg-seal",
     "Seal acceptance criteria before you measure."),
    ("cert-atlas", "cert-atlas",
     "{n_forgeries} labelled forgeries + a two-sided metric."),
    ("certified-mcp", "certified-mcp",
     "{n_tools} MCP tools giving agents a verifier they can't argue with."),
    ("certified-kit", "certified-kit",
     "One install, one command, every verb forwarded to the component that owns it."),
    ("lcert-verify-web", "lcert-verify-web",
     "Browser verifier; nothing uploaded."),
]

_LANDING_START = "<!-- BEGIN GENERATED: deliverables -->"
_LANDING_END = "<!-- END GENERATED: deliverables -->"


def _atlas_facts(root: Path) -> tuple[int, int]:
    """(n_cases, n_forgeries) read from the committed baseline + the defect registry."""
    baseline = json.loads((root / "cert-atlas" / "BASELINE.json").read_text())
    defects = (root / "cert-atlas" / "src" / "cert_atlas" / "defects.py").read_text()
    return int(baseline["n_cases"]), len(re.findall(r"^\s*_d\(", defects, re.M))


def _mcp_tool_count(pkg: Path) -> int:
    """Derived from the decorators, not typed. The badge used to hard-code `8` while the
    server registered 9 -- the single number in this file that was asserted rather than derived.

    Takes the *package* directory, not the tree root, because those are the same directory in a
    published repository and different ones in this dev tree. The earlier signature took the root
    and was called with the module-level ``ROOT``, which resolved by luck here and crashed with
    ``certified-mcp/src/certified_mcp/server.py: no such file`` under ``--single`` -- so adding the
    ``--check`` step to certified-mcp's CI would have broken its build on the first run.
    """
    src = (pkg / "src" / "certified_mcp" / "server.py").read_text()
    return len(re.findall(r"^@tool\(", src, re.M))


def landing_table(root: Path) -> str:
    n_cases, n_forgeries = _atlas_facts(root)
    n_tools = _mcp_tool_count(root / "certified-mcp")
    counts, total = {}, 0
    for pkg, _repo, _desc in LANDING:
        d = root / ("verify-web" if pkg == "lcert-verify-web" else pkg)
        if pkg == "lcert-verify-web":
            counts[pkg] = f"{count_conformance(d)} JS conf."
        else:
            n = count_tests(d)
            total += n
            counts[pkg] = str(n)

    rows = ["| Package | What it does | Live | Tests collected |", "|---|---|---|---|"]
    for pkg, repo, desc in LANDING:
        desc = desc.format(n_forgeries=n_forgeries, n_tools=n_tools)
        live = f"[repo](https://github.com/nickharris808/{repo})"
        if pkg == "cert-atlas":
            live += " · [dataset](https://huggingface.co/datasets/nickh007/cert-atlas)"
        if pkg == "lcert-verify-web":
            live += " · [\U0001f50f Space](https://huggingface.co/spaces/nickh007/cert-verifier)"
        rows.append(f"| **{pkg}** | {desc} | {live} | {counts[pkg]} |")

    conf = counts["lcert-verify-web"].split()[0]
    rows += [
        "",
        f"**{total:,} Python tests collected + {conf} JS conformance checks.** *Collected*, not "
        f"passed: some tests skip when an optional tool is absent, so a passed count is a property "
        f"of the machine rather than of the suite. Whether they pass is what each repository's CI "
        f"badge says.",
        "",
        f"The atlas holds **{n_cases} cases, {n_forgeries} of them forgeries**. `certified-mcp` "
        f"registers **{n_tools} tools**.",
        "",
        "**Not on PyPI or npm yet** — every package installs from git; see each README. The "
        "names are unregistered, so the plain `pip install <name>` form installs nothing.",
    ]
    return "\n".join(rows)


def rewrite_landing(root: Path) -> str:
    """Rebuild the generated block in oss/README.md between its two markers."""
    readme = root / "README.md"
    text = readme.read_text()
    table = landing_table(root)
    new_block = f"{_LANDING_START}\n\n{table}\n\n{_LANDING_END}"
    if _LANDING_START in text and _LANDING_END in text:
        return re.sub(re.escape(_LANDING_START) + r".*?" + re.escape(_LANDING_END),
                      lambda _m: new_block, text, flags=re.S)
    raise RuntimeError(
        "oss/README.md has no generated-deliverables markers; add "
        f"{_LANDING_START} / {_LANDING_END} around the table first")

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("names", nargs="*",
                    default=PY_PACKAGES + ["lcert-verify-web", "certified-oss"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--single", default="")
    ap.add_argument("--landing", action="store_true",
                    help="also regenerate the deliverables table in oss/README.md")
    a = ap.parse_args(argv)

    stale = []
    if a.landing:
        root = Path(a.root)
        new = rewrite_landing(root)
        cur = (root / "README.md").read_text()
        if a.check:
            if cur != new:
                stale.append("README.md (landing table)")
        elif cur != new:
            (root / "README.md").write_text(new)
            print("  README.md: deliverables table regenerated")
        else:
            print("  README.md: deliverables table already current")

    for name in (a.names or PY_PACKAGES + ["lcert-verify-web", "certified-oss"]):
        d = Path(a.root) if a.single == name else \
            Path(a.root) / ("verify-web" if name == "lcert-verify-web" else name)
        readme = d / "README.md"
        if not readme.exists():
            print(f"  {name}: no README")
            continue
        try:
            new = rewrite(readme, name, badges_for(name, d))
        except Exception as exc:                       # noqa: BLE001
            print(f"  {name}: could not derive badges — {exc}", file=sys.stderr)
            return 1
        if a.check:
            if readme.read_text() != new:
                stale.append(name)
        else:
            readme.write_text(new)
            print(f"  {name}: badges refreshed")
    if stale:
        print("STALE badges (run python refresh_badges.py): " + ", ".join(stale),
              file=sys.stderr)
        return 1
    if a.check:
        print("every badge is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
