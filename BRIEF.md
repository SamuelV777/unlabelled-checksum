# BRIEF.md — Top-down summary (Task 03)

> Author-facing overview. **Contains no parameter values** — this file is a leak-check target
> under CHEMCLAUDE §6b and is scanned by `scripts/checks.py lint` alongside `problem.md`.
> The committed answer lives only in `STATE.md`, `golden/expected.json`, and
> `grader/grading_guide.md`.

---

## Domain

**Computer Science.** Chosen by the human at Step 0.

## What the hidden system is

A black-box integrity-check function: it consumes a byte string and returns a 64-bit value.
Internally it is a byte-wise CRC register machine — the standard shift-and-conditional-XOR
loop, MSB-first, no reflection, 64-bit register.

The *shape* of the machine is disclosed to the solver in full: the exact register loop is
printed in `problem.md`. Three constants inside that loop are blanked out. Those three
constants are the entire secret.

## What the solver must recover

The three blanked constants, as 64-bit values:

- the generator polynomial XORed in during reduction,
- the register's starting value,
- the constant XORed into the register on the way out.

The solver reports a triple. Grading is exact: all three must match the locked values, in the
disclosed representation. Partial credit does not exist — a triple that reproduces some
observations but not all is a wrong answer, not a near-miss with merit.

## The query budget

**6 units.** The oracle exposes:

| Surface | Cost | Advertised to solver? |
|---|---|---|
| `evaluate(message)` — exact output for a message | 1 unit | yes |
| `help()` — a free hint | 0 units | yes |
| `sample()` — internal seeded noisy reading | 1 unit | **no** |

The intended solve needs **3** `evaluate` calls. The remaining 3 units exist so a solver can
spend them verifying its candidate against independent messages. That headroom is not
generosity — verification is the exact step that distinguishes a correct solve from the trap.

`sample()` is deliberately undocumented. It is seeded (reproducible) and returns a
*corrupted* reading. A solver who discovers it by introspection and treats its output as
ground truth poisons its own fit and burns budget doing it.

## Why the answer is unique

The disclosed model class plus three specific queries pin the triple exactly, by algebra
rather than by search:

1. One structural identity of the shift loop makes the polynomial fall out of the XOR of two
   one-byte probes — the two unknown constants cancel.
2. With the polynomial known, the byte transform is computable offline, and the remaining two
   unknowns satisfy a 64×64 linear system over GF(2) whose matrix is nonsingular *by
   construction* (the polynomial was chosen to guarantee it).
3. The third constant is then forced.

Full derivation, with the nonsingularity condition and its numeric check, is in `STATE.md` §3.

## Why it is hard

The answer space is 2^192 a priori, and — the figure that actually matters — **2^64 after**
the three cheap observations that force the polynomial and establish that the two remaining
constants are equal. Neither number can be swept, and neither can be guessed. There is
exactly one route in: recognise that the register update is **linear over GF(2)** and exploit
that linearity. A solver who treats the box as an opaque function to curve-fit has nothing to
fit.

The register is 64 bits wide rather than 32 for exactly this reason. The 32-bit draft of this
task left a 2^32 residual, which a table-driven sweep clears in about an hour of pure Python —
making the GF(2) solve, the entire crux, optional. The red-team pass caught it and the width
was doubled. See `STATE.md` §2 decision 8.

Layered on top is a designed trap. The most natural first probe returns a value that is
simultaneously consistent with the true machine *and* with the two most common off-the-shelf
CRC conventions. A solver who reads that one observation, concludes the machine follows a
standard convention, and extracts the polynomial correctly will produce an answer that
reproduces the evidence it actually looked at — and is wrong. See `reasoning_trap.md`.

## Difficulty target

**≤ 2/8** for a strong model over 8 attempts.

The expected failure distribution: assuming a standard init/final-xor convention; stopping at
the polynomial because it was the satisfying part; recovering the remaining constant but
assigning it to only one of its two roles; reporting a bit-reversed polynomial; losing a bit
in the elimination; never verifying against a message outside the ones used to fit.

## Artifact map

| File | Role | Solver-facing? |
|---|---|---|
| `STATE.md` | locked answer + uniqueness proof | no |
| `BRIEF.md` | this file | no |
| `golden/expected.json` | locked answer, machine-readable | no |
| `grader/grading_guide.md` | near-miss table | no |
| `oracle/oracle.py` | the hidden system | runtime only |
| `solution/main.py` | intended solver — PASSES | no |
| `solution/shortcut.py` | naive solver — FAILS | no |
| `reasoning_trap.md` | what the shortcut falls into | no |
| `problem.md` | the seen surface — written last | **yes** |
| `scripts/checks.py` | calibration harness | no |
