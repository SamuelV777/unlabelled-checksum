"""main.py — the intended solver.

Recovers (POLY, INIT, XOROUT) from the hidden register machine in 3 queries, then spends
2 more of the 6-unit budget verifying the result on messages it did not fit to. 5 of 6 used.

The whole solve rests on one observation: for a fixed POLY, one pass of the eight shift steps
is a GF(2)-LINEAR map on the register. Linear means the two unknown constants can be made to
cancel, and what is left is a 64x64 linear system, not a search over 2^192 triples.

Stdlib only.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "oracle"))

from oracle import Oracle  # noqa: E402

WIDTH = 64
MASK = 0xFFFFFFFFFFFFFFFF
TOP_BIT = 0x8000000000000000
TOP_BYTE = 0x0100000000000000          # the register with only bit 56 set


# --------------------------------------------------------------------------- #
# The register transform, and GF(2) linear algebra over 64-bit vectors.
# --------------------------------------------------------------------------- #
def byte_transform(reg: int, poly: int) -> int:
    """One pass of the eight shift steps. GF(2)-linear in `reg` for fixed `poly`."""
    for _ in range(8):
        if reg & TOP_BIT:
            reg = ((reg << 1) ^ poly) & MASK
        else:
            reg = (reg << 1) & MASK
    return reg


def solve_gf2(columns: list[int], target: int, nbits: int = WIDTH):
    """Solve XOR_i x_i * columns[i] == target over GF(2).

    `columns[i]` is the image of the i-th basis vector. Returns the unique solution, or
    None if the system is inconsistent or under-determined (which would mean the task's
    uniqueness argument had failed).
    """
    rows = []
    for r in range(nbits):
        bits = 0
        for i in range(nbits):
            if (columns[i] >> r) & 1:
                bits |= 1 << i
        rows.append([bits, (target >> r) & 1])

    pivots: dict[int, int] = {}
    used: set[int] = set()
    for col in range(nbits):
        pivot = next(
            (i for i in range(nbits) if i not in used and (rows[i][0] >> col) & 1), None
        )
        if pivot is None:
            continue
        used.add(pivot)
        pivots[col] = pivot
        for i in range(nbits):
            if i != pivot and ((rows[i][0] >> col) & 1):
                rows[i][0] ^= rows[pivot][0]
                rows[i][1] ^= rows[pivot][1]

    for row_bits, rhs in rows:
        if row_bits == 0 and rhs == 1:
            return None                      # inconsistent
    if len(pivots) != nbits:
        return None                          # under-determined

    solution = 0
    for col, i in pivots.items():
        if rows[i][1]:
            solution |= 1 << col
    return solution


def crc(message: bytes, poly: int, init: int, xorout: int) -> int:
    """Our reconstruction of the machine, used only to verify a candidate."""
    reg = init
    for byte in message:
        reg = (reg ^ (byte << 56)) & MASK
        reg = byte_transform(reg, poly)
    return reg ^ xorout


# --------------------------------------------------------------------------- #
# The solve.
# --------------------------------------------------------------------------- #
def solve(oracle: Oracle, verbose: bool = True) -> dict:
    def say(text: str = "") -> None:
        if verbose:
            print(text)

    say("intended solver - exploiting GF(2) linearity of the shift loop")
    say("=" * 72)

    # -- Queries 1-3: the only three the derivation needs ------------------- #
    c_empty = oracle.evaluate("")        # = INIT ^ XOROUT
    c_00 = oracle.evaluate("00")         # = T(INIT) ^ XOROUT
    c_01 = oracle.evaluate("01")         # = T(INIT ^ TOP_BYTE) ^ XOROUT

    say(f"query 1  evaluate('')   = 0x{c_empty:016X}  -> INIT ^ XOROUT")
    say(f"query 2  evaluate('00') = 0x{c_00:016X}  -> T(INIT) ^ XOROUT")
    say(f"query 3  evaluate('01') = 0x{c_01:016X}  -> T(INIT ^ B) ^ XOROUT")
    say(f"         where B = 0x{TOP_BYTE:016X}")
    say()

    # -- Step 1: POLY, by an identity of the shift loop --------------------- #
    # B = 0x0100000000000000 has bit 56 set and nothing higher. Seven left shifts carry it
    # to 0x8000000000000000 with no reduction firing; the eighth shift sees the top bit and
    # emits (0x8000000000000000 << 1) ^ POLY == POLY. So T(B) == POLY, identically.
    # T is linear, so XORing the two one-byte outputs cancels INIT and XOROUT outright:
    #     crc(00) ^ crc(01) = T(INIT) ^ T(INIT ^ B) = T(B) = POLY
    poly = c_00 ^ c_01
    say("step 1  T(B) == POLY identically: seven clean shifts, then one reduction.")
    say("        T is GF(2)-linear, so XORing the two one-byte outputs cancels both")
    say("        unknown constants outright:  crc(00) ^ crc(01) = T(B) = POLY")
    say(f"        POLY = 0x{c_00:016X} ^ 0x{c_01:016X}")
    say(f"             = 0x{poly:016X}")
    say()

    # -- Step 2: INIT, by a 64x64 GF(2) solve ------------------------------- #
    #     crc(00) ^ crc('') = T(INIT) ^ INIT = (T ^ I)(INIT)
    # With POLY known, T costs nothing to evaluate, so the matrix is built offline.
    columns = [byte_transform(1 << i, poly) ^ (1 << i) for i in range(WIDTH)]
    init = solve_gf2(columns, c_00 ^ c_empty)
    if init is None:
        raise RuntimeError("(T ^ I) is singular - the task's uniqueness argument is broken")
    say("step 2  crc(00) ^ crc('') = T(INIT) ^ INIT = (T ^ I)(INIT).")
    say("        POLY is known, so (T ^ I) is built offline from the 64 basis vectors -")
    say("        no further queries. Gaussian elimination over GF(2) inverts it.")
    say(f"        (T ^ I)(INIT) = 0x{c_00 ^ c_empty:016X}")
    say(f"        INIT          = 0x{init:016X}")
    say()

    # -- Step 3: XOROUT falls out ------------------------------------------- #
    xorout = c_empty ^ init
    say("step 3  XOROUT = crc('') ^ INIT")
    say(f"               = 0x{c_empty:016X} ^ 0x{init:016X}")
    say(f"               = 0x{xorout:016X}")
    say()

    # -- Step 4: spend spare budget falsifying ourselves -------------------- #
    # This is the step the shortcut never takes. Two messages we did not fit to.
    say("step 4  verification - 2 spare budget units on messages NOT used in the fit")
    all_ok = True
    for hexmsg in ("0000", "313233343536373839"):
        predicted = crc(bytes.fromhex(hexmsg), poly, init, xorout)
        actual = oracle.evaluate(hexmsg)
        ok = predicted == actual
        all_ok &= ok
        label = hexmsg if len(hexmsg) <= 8 else f"{hexmsg} ('123456789')"
        say(f"        {label}")
        say(f"          predicted 0x{predicted:016X}  actual 0x{actual:016X}  "
            f"{'OK' if ok else 'MISMATCH'}")

    # The three fitted observations must also reproduce, by construction.
    for hexmsg, observed in (("", c_empty), ("00", c_00), ("01", c_01)):
        all_ok &= crc(bytes.fromhex(hexmsg), poly, init, xorout) == observed

    say()
    say("=" * 72)
    say(f"POLY   = 0x{poly:016X}")
    say(f"INIT   = 0x{init:016X}")
    say(f"XOROUT = 0x{xorout:016X}")
    say(f"budget: {oracle.spent} of {oracle.budget} spent, {oracle.remaining} unused")
    say(f"consistent with every observation: {all_ok}")

    return {"POLY": poly, "INIT": init, "XOROUT": xorout, "verified": bool(all_ok)}


def main() -> int:
    result = solve(Oracle())
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
