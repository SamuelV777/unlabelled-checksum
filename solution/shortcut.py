"""shortcut.py — the naive solver. It FAILS, and it is meant to.

This is not a strawman. It is the approach a competent engineer actually reaches for when
handed an unknown CRC, and it is deliberately built to be as strong as that approach gets:

  1. It probes the empty message first, which is the obvious first probe.
  2. It reads the result correctly: crc(empty) = INIT ^ XOROUT, so crc(empty) == 0 means
     INIT == XOROUT. That inference is CORRECT.
  3. It derives POLY by the same identity the intended solver uses. It gets POLY exactly
     RIGHT. There is no sabotage here; a third of the answer is genuinely recovered, by a
     genuinely correct argument.
  4. It then does something a strawman would not: it VERIFIES. It tests each candidate
     convention against an observation it already paid for, and reports the failure.

And it still loses. That is the point of the trap, and the reason the difficulty target is
honest: the shortcut does not fail from carelessness, it fails from a category error.

The category error: it treats INIT and XOROUT as a CHOICE FROM A CATALOGUE of standard CRC
conventions, when they are 128 unknown bits with no catalogue entry. Every real-world CRC the
engineer has ever met uses all-zeroes or all-ones, so enumerating those feels exhaustive.
It is not. No amount of extra care rescues this approach - only changing it does. See
reasoning_trap.md.

Stdlib only.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "oracle"))

from oracle import Oracle  # noqa: E402

MASK = 0xFFFFFFFFFFFFFFFF
TOP_BIT = 0x8000000000000000
ONES = 0xFFFFFFFFFFFFFFFF

# The (INIT, XOROUT) conventions of every 64-bit CRC in common use. This list is the
# shortcut's entire hypothesis space for two of the three unknowns -- and that is its
# undoing. CRC-64/XZ ("go-xz") and CRC-64/WE: FFFF..FF / FFFF..FF. CRC-64/ECMA-182 and
# CRC-64/GO-ISO: 0000..00 / 0000..00. A handful of others mix the two.
CATALOGUE = [
    ("ECMA-182 / GO-ISO (bare)", 0x0000000000000000, 0x0000000000000000),
    ("XZ / WE (all ones)", ONES, ONES),
    ("init-only all ones", ONES, 0x0000000000000000),
    ("xorout-only all ones", 0x0000000000000000, ONES),
]


def crc(message: bytes, poly: int, init: int, xorout: int) -> int:
    reg = init
    for byte in message:
        reg = (reg ^ (byte << 56)) & MASK
        for _ in range(8):
            if reg & TOP_BIT:
                reg = ((reg << 1) ^ poly) & MASK
            else:
                reg = (reg << 1) & MASK
    return reg ^ xorout


def solve(oracle: Oracle, verbose: bool = True) -> dict:
    def say(text: str = "") -> None:
        if verbose:
            print(text)

    say("naive solver - identify the CRC against the standard catalogue")
    say("=" * 72)

    c_empty = oracle.evaluate("")
    c_00 = oracle.evaluate("00")
    c_01 = oracle.evaluate("01")
    say(f"query 1  evaluate('')   = 0x{c_empty:016X}")
    say(f"query 2  evaluate('00') = 0x{c_00:016X}")
    say(f"query 3  evaluate('01') = 0x{c_01:016X}")
    say()

    # This part is right, and it is right for the right reason.
    poly = c_00 ^ c_01
    say(f"POLY = crc(00) ^ crc(01) = 0x{poly:016X}")
    say("       <- correct, and correctly derived")
    say()

    # This inference is also right: crc(empty) = INIT ^ XOROUT.
    say(f"crc(empty) = 0x{c_empty:016X}, and crc(empty) = INIT ^ XOROUT,")
    say("so INIT == XOROUT. Which standard convention has INIT == XOROUT?")
    say()

    consistent = [row for row in CATALOGUE if (row[1] ^ row[2]) == c_empty]
    for name, init, xorout in CATALOGUE:
        verdict = "consistent with crc(empty)" if (init ^ xorout) == c_empty else "ruled out"
        say(f"  {name:26} INIT=0x{init:016X}")
        say(f"  {'':26} XOROUT=0x{xorout:016X}  {verdict}")
    say()

    # The shortcut does verify. It just has nothing better to fall back on.
    say("checking each surviving convention against crc(00), already paid for:")
    winner = None
    for name, init, xorout in consistent:
        predicted = crc(b"\x00", poly, init, xorout)
        ok = predicted == c_00
        say(f"  {name:26} predicts 0x{predicted:016X}")
        say(f"  {'':26} observed 0x{c_00:016X}  {'MATCH' if ok else 'mismatch'}")
        if ok and winner is None:
            winner = (name, init, xorout)
    say()

    if winner is None:
        # Every catalogue entry failed. The shortcut has exhausted its hypothesis space and
        # does not possess the concept that would get it further, so it reports the most
        # common convention and flags low confidence. This is exactly what the trap produces:
        # a confident, correctly derived POLY attached to guessed constants.
        name, init, xorout = consistent[0] if consistent else CATALOGUE[0]
        say("no catalogue convention reproduces crc(00).")
        say("falling back to the most common one that is at least consistent with crc(empty).")
    else:
        name, init, xorout = winner

    say("=" * 72)
    say(f"POLY   = 0x{poly:016X}")
    say(f"INIT   = 0x{init:016X}   ({name})")
    say(f"XOROUT = 0x{xorout:016X}   ({name})")
    say(f"budget: {oracle.spent} of {oracle.budget} spent")

    return {"POLY": poly, "INIT": init, "XOROUT": xorout, "convention": name}


def main() -> int:
    solve(Oracle())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
