# STATE.md — Locked Answer (Task 03, Computer Science)

> **Status: LOCKED.** Written before any solver-facing artifact exists.
> Domain chosen by the human: **Computer Science**.
> Hidden rule: parameter recovery for an unknown CRC register machine.

---

## 1. The committed answer

The hidden system is a 64-bit, byte-wise, **MSB-first (non-reflected)** CRC register machine:

```
reg = INIT
for each byte b of the message:
    reg ^= (b << 56)
    repeat 8 times:
        if reg & 0x8000000000000000: reg = ((reg << 1) ^ POLY) & 0xFFFFFFFFFFFFFFFF
        else:                        reg = (reg << 1) & 0xFFFFFFFFFFFFFFFF
return reg ^ XOROUT
```

The three hidden parameters — **the answer** — are:

| Parameter | Value |
|---|---|
| `POLY`    | `0xDE27F4C90BA4596B` |
| `INIT`    | `0x2851D5EDB7B43883` |
| `XOROUT`  | `0x2851D5EDB7B43883` |

Answer space: 2^192 triples a priori. Not sweepable, not guessable. See §5 for the residual
space after the cheap observations, which is the number that actually matters.

### Reference values produced by the locked answer

| Message (hex) | Output |
|---|---|
| (empty)         | `0x0000000000000000` |
| `00`            | `0xAE3A4BA39060CB0B` |
| `01`            | `0x701DBF6A9BC49260` |
| `0000`          | `0x87F8680FF5707BA5` |
| `ff`            | `0x12CF2C6CB26391B5` |
| `313233343536373839` (`"123456789"`) | `0x05F8D10865E59988` |
| `01020304`      | `0x19C0DF70BFD840C1` |

Structural facts that follow from the choice (all verified numerically):

- `popcount(POLY) = 34` — even, so the full polynomial `P = x^64 + POLY` has `P(1) = 1`,
  i.e. `(x+1)` does **not** divide `P`. This is what makes the recovery step solvable (see §3).
- `POLY` is odd, so `gcd(x, P) = 1` and the byte transform is invertible.
- `INIT == XOROUT`, which is **deliberate** — see §2, decision 4.

---

## 2. Order of design decisions (and why each was taken)

1. **Domain → Computer Science.** Chosen by the human at Step 0.

2. **Hidden rule → CRC parameter recovery.** Picked over the guide's other CS suggestions
   (FSM, cache-eviction policy, hash rule) for one reason: *answer-space width*. A hidden
   eviction policy is a menu pick (`{LRU, FIFO, LFU, MRU, CLOCK}` × a small capacity ≈ 10^2
   combinations) and a hidden sort key or small FSM is similar. Any of those can be swept by a
   simulator inside the 6-query budget, which Section 6b calls a fake investigation. CRC
   parameter recovery is recovered *structurally*, by algebra over GF(2), not by search. It is
   also a real, named engineering problem ("CRC RevEng").

3. **Model class is disclosed; only the three constants are hidden.** The exact register loop
   above is stated in `problem.md`. This is a fairness decision: it is what makes the answer
   provably unique (§3). The difficulty must come from the algebra and the trap, never from
   guessing which dialect of CRC is running. Reflection (`REFIN`/`REFOUT`) was considered as a
   fourth hidden parameter and **rejected**: uniqueness across the reflected and non-reflected
   families cannot be proven by construction, only spot-checked, and an unprovable answer is a
   broken task. (It was nevertheless checked — §4.)

4. **`INIT` set equal to `XOROUT`.** This is the trap's foundation. It forces
   `crc(empty) = INIT ^ XOROUT = 0x0000000000000000`, and all-zeroes on the empty message is
   *also* what the two most natural wrong hypotheses predict:
   - `(POLY, 0, 0)` — "it's a bare CRC, no init/final xor" (CRC-64/ECMA-182, CRC-64/GO-ISO)
   - `(POLY, 0xFF..FF, 0xFF..FF)` — "it's the usual all-ones convention" (CRC-64/XZ, CRC-64/WE)

   All three models agree on the single most obvious probe and diverge on every nonempty
   message. The honeypot is the first thing a solver will query.

5. **`POLY` chosen with even popcount.** Not cosmetic — it is a *correctness requirement*.
   See §3; with odd popcount the recovery step has no unique solution and the task would be
   broken. The generator loop in `.scratch` rejected candidates until this held **and** the
   computed rank of `(T ^ I)` was 64.

6. **`POLY` chosen to be absent from the standard CRC catalogue.** A solver must not be able to
   shortcut by recognising `0x42F0E1EBA9EA3693` (ECMA-182), `0xAD93D23594C935A9` (WE/Jones),
   `0x000000000000001B` (GO-ISO), or `0xA17870F5D4F51B49`. `0xDE27F4C90BA4596B` is none of
   these.

7. **`INIT` chosen to be a nondescript constant.** Not all-ones, not `0xDEADBEEF...`, not a
   golden-ratio or AES/SHA test constant. Nothing about `0x2851D5EDB7B43883` is guessable.

8. **Register width 64, not 32.** The task was first built at 32 bits and the red-team pass
   (§5) killed that version: after the three cheap observations the residual space was only
   2^32, which a table-driven sweep clears in about an hour of pure Python and seconds in C.
   That would have made the GF(2) solve — the entire crux — optional. Widening to 64 bits
   raises the residual to 2^64 and closes the bypass. Everything else about the design carried
   over unchanged, including the identity in §3 Step 1 and the catalogue trap, since 64-bit
   CRCs have their own all-zeroes and all-ones conventions.

9. **Budget 6, intended solve needs 3.** The headroom is deliberate and is *not* slack: the
   spare queries exist so the intended solver can spend them **verifying** its answer on
   independent messages. Verification is precisely the step that separates a passing solve
   from the trap (see `reasoning_trap.md`). A solver who never verifies never discovers that
   its `(POLY, 0, 0)` model is wrong.

---

## 3. Why this is the only answer

**Claim.** Exactly one triple `(POLY, INIT, XOROUT)` in the disclosed model class reproduces
the hidden system's outputs. Three queries suffice to pin it, and no other triple survives them.

Write `T(v)` for the register transform applied by one pass of the 8 shift steps. For a fixed
`POLY`, `T` is **GF(2)-linear**: `T(u ^ v) = T(u) ^ T(v)`. (Each step is a shift plus a
conditional XOR of `POLY`, and the condition is itself a linear functional of the register.)

Let `B = 0x0100000000000000`, the register with only bit 56 set.

### Step 1 — `POLY` is determined, exactly, by two queries

`B` has bit 56 set and no higher bit. Seven left-shifts carry it to `0x8000000000000000` with
no reduction firing; the eighth shift sees the top bit set and produces
`(0x8000000000000000 << 1) ^ POLY = POLY`. Therefore

> **`T(B) = POLY` identically.**

For one-byte messages, `crc([b]) = T(INIT ^ (b << 56)) ^ XOROUT`. By linearity of `T`:

```
crc([0x00]) ^ crc([0x01]) = ( T(INIT)     ^ XOROUT )
                          ^ ( T(INIT ^ B) ^ XOROUT )
                          = T(B)
                          = POLY
```

`INIT` and `XOROUT` cancel completely. This is an identity, not a fit — `POLY` is forced.
Verified numerically: `0xAE3A4BA39060CB0B ^ 0x701DBF6A9BC49260 = 0xDE27F4C90BA4596B`. ✔

### Step 2 — `INIT` is determined by one more query

With `POLY` known, `T` is fully computable offline, with no further queries. Let

```
c = crc(empty)   = INIT ^ XOROUT
A = crc([0x00])  = T(INIT) ^ XOROUT
```

XOR them: `A ^ c = T(INIT) ^ INIT = (T ^ I)(INIT)`, where `I` is the identity map. This is a
64×64 linear system over GF(2). It has a **unique** solution iff `(T ^ I)` is nonsingular.

`(T ^ I)` is singular iff some nonzero `v` of degree < 64 satisfies `v·x^8 ≡ v (mod P)`, i.e.
`P | v·(x^8 + 1) = v·(x + 1)^8`. If `(x + 1) ∤ P` then `gcd(P, (x+1)^8) = 1`, forcing `P | v`,
which is impossible for `0 ≠ deg v < 64`. And `(x + 1) ∤ P ⟺ P(1) = 1 ⟺ popcount(POLY)` is
even — which is exactly why decision 5 in §2 was made.

Computed rank of `(T ^ I)` for `POLY = 0xDE27F4C90BA4596B`: **64**. Nonsingular. So `INIT` is
unique. ✔

### Step 3 — `XOROUT` is then forced

`XOROUT = c ^ INIT`. No freedom remains. ✔

### Consequence

The three queries `crc(empty)`, `crc([0x00])`, `crc([0x01])` admit exactly one consistent
triple, and it is the locked one. Any other triple must differ from it in `POLY`
(contradicting the Step-1 identity), or in `INIT` (contradicting the Step-2 nonsingularity),
or in `XOROUT` (contradicting Step 3). There is no second answer.

---

## 4. The reflected family does not alias either (verified, not assumed)

Uniqueness within the disclosed model class would be enough, since `problem.md` prints the
loop in full. But the obvious objection is that a solver using the *LSB-first* (reflected) CRC
dialect might find a triple in **that** family reproducing all three observations, which would
make the task ambiguous in spirit even if not in letter. It does not exist:

- Any reflected candidate must satisfy `T_r(1) = crc([0x00]) ^ crc([0x01]) = 0xDE27F4C90BA4596B`,
  where `T_r` is the reflected byte transform.
- `T_r(1)` is **not** linear in `POLY'` (the branch conditions depend on `POLY'`'s own bits),
  so this cannot be solved by a single linear system. Conditioning on the 8 branch bits makes
  each branch linear; enumerating all 128 branches, and within each branch the *entire*
  solution space including the nullspace, is exhaustive.
- Result: **no reflected polynomial satisfies the constraint.** The reflected family is empty
  before `INIT'`/`XOROUT'` are even considered.
- The enumeration was validated before being trusted: round-tripping random polynomials
  recovered 12/12 at 32 bits and 10/10 at 64 bits. (A first, naive version of this search took
  only one particular solution per branch and recovered just 7/12 — it would have reported the
  same "none" for the wrong reason. The result above is from the corrected, validated search.)

### What uniqueness does *not* mean

A bit-reversed reading of the polynomial (`0xD69A25D0932FE47B`) is a *different representation
of a different machine*, not a second answer, and is graded wrong.

---

## 5. Difficulty claim

The answer is not guessable and not searchable. The numbers that matter:

| | |
|---|---|
| a priori answer space | 2^192 |
| residual space after `crc(empty)`, `crc(00)`, `crc(01)` | **2^64** |
| queries needed by the intended solve | 3 of 6 |

The residual figure is the honest one. Three cheap observations force `POLY` and establish
`INIT == XOROUT`, which collapses the problem to a single 64-bit unknown. 2^64 is beyond any
sweep, so the only remaining route is the GF(2) solve. **This is why the register is 64 bits
wide and not 32** — at 32 bits the residual was 2^32 and the crux was bypassable by an hour of
brute force (§2, decision 8).

The naive-but-competent approach — read `crc(empty) = 0`, conclude the init and final-xor
constants are absent or are the usual all-ones, and extract `POLY` from the difference of two
one-byte probes — recovers `POLY` correctly, matches the empty-message evidence exactly, and
is **wrong**. Target: ≤ 2/8.
