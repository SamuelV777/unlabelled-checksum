"""checks.py — calibration harness for task-03.

Subcommands, each printing a clear PASS/FAIL line:

    verify     runs solution/main.py against the oracle, asserts it recovers expected.json
    shortcut   runs solution/shortcut.py, asserts it does NOT recover the answer
    lint       scans the solver-facing surfaces for any leak of the answer
    preview    reports the intended difficulty target
    selftest   runs all four and asserts the expected outcomes

Stdlib only. Offline. Run from the task root:

    python scripts/checks.py selftest
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIFFICULTY_TARGET = "<= 2/8"


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #
def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, relpath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expected() -> dict:
    with open(os.path.join(ROOT, "golden", "expected.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _read(relpath: str) -> str:
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as handle:
        return handle.read()


def _triple(answer: dict) -> tuple[int, int, int]:
    return answer["POLY"], answer["INIT"], answer["XOROUT"]


def _banner(title: str) -> None:
    print(f"--- {title} " + "-" * max(0, 62 - len(title)))


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
def cmd_verify(quiet: bool = False) -> bool:
    _banner("verify: intended solver vs. locked answer")
    expected = _expected()
    oracle_mod = _load("oracle_mod", os.path.join("oracle", "oracle.py"))
    main_mod = _load("main_mod", os.path.join("solution", "main.py"))

    # The oracle must still agree with the answer locked in expected.json. If someone edits
    # the oracle's packed parameters, this is what catches it.
    # Probe the machine directly: Oracle enforces a fixed 6-unit budget by design and
    # deliberately offers no way to widen it, so the harness must not go through it here.
    drift = []
    for hexmsg, want in expected["reference_outputs"].items():
        got = oracle_mod._machine(bytes.fromhex(hexmsg))
        if got != int(want, 16):
            drift.append((hexmsg or "(empty)", want, f"0x{got:016X}"))
    if drift:
        for hexmsg, want, got in drift:
            print(f"  ORACLE DRIFT  {hexmsg}: expected {want}, oracle gave {got}")
        print("FAIL - the oracle no longer matches golden/expected.json")
        return False
    print(f"  oracle matches all {len(expected['reference_outputs'])} locked reference outputs")

    oracle = oracle_mod.Oracle()
    result = main_mod.solve(oracle, verbose=not quiet)
    got = (result["POLY"], result["INIT"], result["XOROUT"])
    want = _triple(expected["answer"])

    print()
    print(f"  recovered  POLY=0x{got[0]:016X} INIT=0x{got[1]:016X} XOROUT=0x{got[2]:016X}")
    print(f"  expected   POLY=0x{want[0]:016X} INIT=0x{want[1]:016X} XOROUT=0x{want[2]:016X}")
    print(f"  budget     {oracle.spent} of {oracle.budget} spent")

    ok_answer = got == want
    ok_budget = oracle.spent <= oracle.budget
    if ok_answer and ok_budget:
        print(f"PASS - intended solver recovers the answer within budget "
              f"({oracle.spent}/{oracle.budget})")
        return True
    if not ok_answer:
        print("FAIL - intended solver did not recover the locked answer")
    if not ok_budget:
        print("FAIL - intended solver overspent the budget")
    return False


# --------------------------------------------------------------------------- #
# shortcut
# --------------------------------------------------------------------------- #
def cmd_shortcut(quiet: bool = False) -> bool:
    _banner("shortcut: naive solver must NOT recover the answer")
    expected = _expected()
    oracle_mod = _load("oracle_mod", os.path.join("oracle", "oracle.py"))
    short_mod = _load("short_mod", os.path.join("solution", "shortcut.py"))

    oracle = oracle_mod.Oracle()
    result = short_mod.solve(oracle, verbose=not quiet)
    got = (result["POLY"], result["INIT"], result["XOROUT"])
    want = _triple(expected["answer"])

    print()
    print(f"  shortcut   POLY=0x{got[0]:016X} INIT=0x{got[1]:016X} XOROUT=0x{got[2]:016X}")
    print(f"  expected   POLY=0x{want[0]:016X} INIT=0x{want[1]:016X} XOROUT=0x{want[2]:016X}")

    matched = [
        name for name, g, w in zip(("POLY", "INIT", "XOROUT"), got, want) if g == w
    ]
    print(f"  shortcut got right: {', '.join(matched) if matched else 'nothing'}")

    if got == want:
        print("FAIL - the naive solver SUCCEEDED; the trap is not real")
        return False

    # The trap must be a real one: the shortcut is supposed to derive POLY correctly and
    # fail only on the constants. If it fails on POLY too, it was crippled, not trapped.
    if got[0] != want[0]:
        print("FAIL - shortcut got POLY wrong; that is a crippled solver, not a trap")
        return False

    print("  trap is principled: POLY derived correctly, constants assumed from a catalogue")
    print("FAIL (as intended) - naive solver does not recover the answer")
    return True


# --------------------------------------------------------------------------- #
# lint
# --------------------------------------------------------------------------- #
def _leak_tokens(expected: dict) -> list[tuple[str, str]]:
    """(needle, why) pairs that must not appear on any solver-facing surface."""
    poly, init, xorout = _triple(expected["answer"])
    tokens: list[tuple[str, str]] = []

    for name, value in (("POLY", poly), ("INIT", init), ("XOROUT", xorout)):
        tokens.append((f"{value:016x}", f"{name} in hex"))
        tokens.append((str(value), f"{name} in decimal"))

    # Derived forms a careless author might paste in.
    rev = int(f"{poly:064b}"[::-1], 2)
    tokens.append((f"{rev:016x}", "bit-reversed POLY"))
    tokens.append((f"{poly | (1 << 64):017x}", "POLY with the implicit x^64 term"))

    # Any observed output of the machine narrows the answer: two of them give POLY outright.
    for hexmsg, out in expected["reference_outputs"].items():
        tokens.append((out[2:].lower(), f"machine output for message '{hexmsg or 'empty'}'"))

    return tokens


def cmd_lint(quiet: bool = False) -> bool:
    _banner("lint: solver-facing surfaces must not name the answer")
    expected = _expected()
    tokens = _leak_tokens(expected)

    oracle_mod = _load("oracle_mod", os.path.join("oracle", "oracle.py"))

    # Two tiers. `surfaces` is everything that must not contain the answer's VALUES --
    # BRIEF.md is author-facing, but CHEMCLAUDE 6b requires it to be leak-checked too.
    # `solver_facing` is the subset a solver actually reads; only those must also avoid
    # giving away the METHOD, which BRIEF.md is supposed to explain.
    surfaces = {
        "problem.md": _read("problem.md"),
        "BRIEF.md": _read("BRIEF.md"),
        "oracle.help()": oracle_mod.Oracle().help(),
    }
    solver_facing = ("problem.md", "oracle.help()")

    findings: list[str] = []
    for surface, text in surfaces.items():
        # Normalise so "0x B7_A4 D9C3" cannot slip past a plain substring search.
        flat = re.sub(r"[\s_,]", "", text).lower().replace("0x", "")
        for needle, why in tokens:
            if needle in flat:
                findings.append(f"{surface}: leaks {why} ({needle})")

    # Structural leaks: these do not print a value but collapse the answer space.
    structural = [
        (r"init\s*==?\s*xorout", "states INIT == XOROUT, halving the unknown bits"),
        (r"xorout\s*==?\s*init", "states XOROUT == INIT, halving the unknown bits"),
        (r"even\s+popcount|popcount.*even", "reveals the parity constraint used to pick POLY"),
        (r"gf\(2\)|galois|linear\s+map|linearity", "reveals the solution method"),
    ]
    for surface in solver_facing:
        for pattern, why in structural:
            if re.search(pattern, surfaces[surface], re.IGNORECASE):
                findings.append(f"{surface}: {why}")

    # The undocumented surface must stay undocumented.
    if re.search(r"\bsample\b", surfaces["problem.md"], re.IGNORECASE):
        findings.append("problem.md: mentions the unadvertised sample() surface")
    if re.search(r"\bsample\b", surfaces["oracle.help()"], re.IGNORECASE):
        findings.append("oracle.help(): mentions the unadvertised sample() surface")

    if not quiet:
        for surface in surfaces:
            tier = "values + method" if surface in solver_facing else "values only"
            print(f"  scanned {surface:16} ({tier})")
        print(f"  {len(tokens)} value tokens; {len(structural)} method patterns on "
              f"{len(solver_facing)} solver-facing surfaces")

    if findings:
        for finding in findings:
            print(f"  LEAK  {finding}")
        print(f"FAIL - {len(findings)} leak(s) found")
        return False

    print("CLEAN - no solver-facing surface names or narrows the answer")
    return True


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #
def cmd_preview(quiet: bool = False) -> bool:
    _banner("preview: intended difficulty")
    expected = _expected()
    oracle_mod = _load("oracle_mod", os.path.join("oracle", "oracle.py"))

    poly, init, xorout = _triple(expected["answer"])
    c_empty = oracle_mod._machine(b"")

    # How many decoy conventions survive the single most obvious probe?
    def crc(message, p, i, x):
        reg, mask, top = i, 0xFFFFFFFFFFFFFFFF, 0x8000000000000000
        for byte in message:
            reg = (reg ^ (byte << 56)) & mask
            for _ in range(8):
                reg = ((reg << 1) ^ p) & mask if reg & top else (reg << 1) & mask
        return reg ^ x

    ones = 0xFFFFFFFFFFFFFFFF
    decoys = [
        ("ECMA-182 / GO-ISO, bare (0, 0)", 0, 0),
        ("CRC-64/XZ, CRC-64/WE (FF..FF, FF..FF)", ones, ones),
    ]
    survive = [n for n, i, x in decoys if crc(b"", poly, i, x) == c_empty]

    print(f"  answer space                 2^192 triples a priori;")
    print(f"                               2^64 residual after the 3 cheap observations")
    print(f"  queries the solve needs      {expected['queries_required_by_intended_solver']} "
          f"of {expected['query_budget']}")
    print(f"  crc(empty)                   0x{c_empty:016X}")
    print(f"  decoy conventions that also predict that value: {len(survive)}")
    for name in survive:
        print(f"      - {name}")
    print()
    print("  expected failure modes:")
    for mode in (
        "assumes a catalogue convention for INIT/XOROUT (the shortcut; rows A/B)",
        "derives POLY, declares victory, hedges on the rest (row K)",
        "solves for the constant, assigns it to one role only (rows C/D)",
        "reports a bit-reversed or 65-bit polynomial (rows E/I)",
        "loses a bit in the GF(2) elimination (rows F/G)",
        "never verifies against a message outside the fit",
    ):
        print(f"      - {mode}")
    print()
    print("  only route to a pass: recognise the shift loop is GF(2)-linear and solve")
    print("  a 64x64 system. No amount of care rescues the catalogue approach, and the")
    print("  2^64 residual space rules out sweeping for the constants instead.")
    print()

    target = expected["difficulty_target"]
    ok = target == DIFFICULTY_TARGET
    numerator = int(re.search(r"(\d+)\s*/\s*8", target).group(1))
    if ok and numerator <= 2:
        print(f"PASS - difficulty target {target} for a strong model over 8 attempts")
        return True
    print(f"FAIL - difficulty target {target!r} is not {DIFFICULTY_TARGET}")
    return False


# --------------------------------------------------------------------------- #
# selftest
# --------------------------------------------------------------------------- #
def cmd_selftest() -> bool:
    print("=" * 68)
    print("selftest - running all four checks and asserting expected outcomes")
    print("=" * 68)
    print()

    results = []
    for label, func, expectation in (
        ("verify", cmd_verify, "PASS"),
        ("shortcut", cmd_shortcut, "FAIL (as intended)"),
        ("lint", cmd_lint, "CLEAN"),
        ("preview", cmd_preview, DIFFICULTY_TARGET),
    ):
        buffer = io.StringIO()
        stdout = sys.stdout
        sys.stdout = buffer
        try:
            ok = func(quiet=True)
        finally:
            sys.stdout = stdout
        results.append((label, ok, expectation, buffer.getvalue()))
        print(f"  [{'ok' if ok else 'XX'}] {label:10} expected {expectation}")

    print()
    failures = [label for label, ok, _, _ in results if not ok]
    if failures:
        print("-" * 68)
        for label, ok, _, output in results:
            if not ok:
                print(f"output of failing check '{label}':")
                print(output)
        print(f"FAIL - {len(failures)} check(s) landed wrong: {', '.join(failures)}")
        return False

    print("PASS - all four checks landed as intended (green)")
    return True


# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    commands = {
        "verify": lambda: cmd_verify(),
        "shortcut": lambda: cmd_shortcut(),
        "lint": lambda: cmd_lint(),
        "preview": lambda: cmd_preview(),
        "selftest": cmd_selftest,
    }
    if len(argv) < 2 or argv[1] not in commands:
        print("usage: python scripts/checks.py {verify|shortcut|lint|preview|selftest}")
        return 2
    return 0 if commands[argv[1]]() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
