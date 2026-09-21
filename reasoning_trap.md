# reasoning_trap.md — what the shortcut falls into

## The trap in one sentence

The two unknown constants look like a **choice among conventions** and are actually
**128 unknown bits**, so the solver enumerates a catalogue that does not contain the answer,
and every observation it bothers to check is consistent with that catalogue being the right
kind of thing to enumerate.

---

## The bait

The obvious first probe is the empty message. It returns `0x0000000000000000`.

That is a real, correct, useful observation, and the inference drawn from it is also correct:
`crc(empty) = INIT ^ XOROUT`, so `INIT == XOROUT`. Nothing has gone wrong yet.

The damage is in what the value *suggests*. All-zeroes on the empty message is the signature of
the two most common 64-bit CRC conventions in existence:

| Convention | `INIT` | `XOROUT` | `crc(empty)` |
|---|---|---|---|
| bare CRC (ECMA-182, GO-ISO) | `0x0000000000000000` | `0x0000000000000000` | `0x0000000000000000` |
| all-ones (CRC-64/XZ, CRC-64/WE) | `0xFFFFFFFFFFFFFFFF` | `0xFFFFFFFFFFFFFFFF` | `0x0000000000000000` |
| **the hidden machine** | `0x2851D5EDB7B43883` | `0x2851D5EDB7B43883` | `0x0000000000000000` |

Three different machines, one identical output on the first thing anyone probes. The solver
reads all zeroes, feels the shape of a familiar problem, and stops treating those two constants
as unknowns. `INIT` and `XOROUT` have quietly been demoted from *variables to solve* to *a
label to look up*.

## Why the bait is not a cheap trick

The solver then gets the hard-looking part *completely right*. `POLY` really does fall out of
`crc(00) ^ crc(01)`, and the reasoning is sound — the unknown constants cancel by linearity.
Deriving a 64-bit polynomial from two one-byte probes feels like the difficult third of the
problem, and it is the part that produces the satisfying "aha".

So the solver finishes with one third of the answer derived rigorously and two thirds assumed,
and the derived third *feels* like evidence that the whole approach was sound. Confidence is
highest exactly where it is least warranted. That asymmetry — rigour on the easy part,
assumption on the hard part — is the trap's actual mechanism.

## Why a smarter shortcut does not escape

The usual objection to a task like this is that the naive solver was crippled to make it lose.
It was not. `solution/shortcut.py` is deliberately built stronger than the approach it
represents:

- It derives `POLY` correctly, by the correct argument.
- It draws the correct inference `INIT == XOROUT` from the empty message.
- It **verifies**. It checks each surviving convention against `crc(00)`, an observation it
  already paid for, and both fail:

```
  ECMA-182 / GO-ISO (bare)   predicts 0x0000000000000000
                             observed 0xAE3A4BA39060CB0B  mismatch
  XZ / WE (all ones)         predicts 0xBCF567CF22035A41
                             observed 0xAE3A4BA39060CB0B  mismatch
```

It knows it is wrong. It says so. And it still cannot produce the answer, because its entire
hypothesis space for two of the three unknowns is four catalogue rows, and the answer is in
none of them. Widening the catalogue does not help either: there is no list of conventions
containing `0x2851D5EDB7B43883`, and there never will be. **More care does not rescue this
approach. Only abandoning it does.**

This is what makes the difficulty target honest. The task is not separating careful solvers
from careless ones. It is separating solvers who *solve for* the constants from solvers who
*recognise* them.

## Why brute force does not escape either

There is a second tempting escape: once `POLY` is known and `crc(empty) = 0` has established
`INIT == XOROUT`, only one 64-bit unknown remains. Sweep it.

At **2^64** that is not available — not in Python, not in C, not with the budget or without it.
This is deliberate and it is the reason the register is 64 bits wide rather than 32. An earlier
draft of this task used a 32-bit register; there the same reasoning left a 2^32 residual, which
a table-driven sweep clears in about an hour of pure Python and seconds in C. That draft was
discarded, because a crux you can skip with an hour of compute is not a crux. See `STATE.md`
§2 decision 8 and §5.

So the catalogue is too small, and the sweep is too big. What is left is the algebra.

## The escape

The constants are recoverable, exactly, and cheaply — but only via a property of the loop that
the catalogue framing never prompts you to look for:

> For a fixed `POLY`, one pass of the eight shift steps is a **GF(2)-linear map** on the
> register.

Each step is a shift plus a conditional XOR of `POLY`, and the condition is itself a linear
functional of the register, so the whole pass is linear. Once that is seen:

```
crc(00) ^ crc(empty) = T(INIT) ^ INIT = (T ^ I)(INIT)
```

`POLY` is already known, so `T` is computable offline with no further queries, and `(T ^ I)`
is a 64×64 matrix over GF(2). Invert it by Gaussian elimination, read off `INIT`, and
`XOROUT = crc(empty) ^ INIT` follows. Three queries total. No search, no catalogue, no guess.

`(T ^ I)` is nonsingular here by construction — `POLY` was chosen with even popcount precisely
so that `(x+1)` does not divide `x^64 + POLY`, which is exactly the condition for that matrix
to be invertible. See `STATE.md` §3.

## The tell the solver was given and probably ignored

The budget is 6. The derivation needs 3. `help()` says, for free:

> *A candidate triple is worth submitting only if it reproduces every output you have
> observed, not just the one that suggested it. You have more budget than the minimum for a
> reason.*

A solver who spends one spare unit on `0000` and compares it against its candidate discovers
the mismatch immediately. That does not hand over the answer — the shortcut discovers the
mismatch too and is still stuck — but it converts a confident wrong submission into a known
open problem, which is the difference between a solver who might recover and one who cannot.

## Summary

| | Shortcut | Intended solver |
|---|---|---|
| `POLY` | correct, correctly derived | correct, correctly derived |
| `INIT` / `XOROUT` | looked up in a catalogue | **solved** as a linear system |
| Treats the constants as | a label | 128 unknown bits |
| Verifies? | yes — and fails | yes — and passes |
| Queries used | 3 of 6 | 5 of 6 |
| Result | `(DE27F4C90BA4596B, 0, 0)` — **WRONG** | `(DE27F4C90BA4596B, 2851D5EDB7B43883, 2851D5EDB7B43883)` — **CORRECT** |
