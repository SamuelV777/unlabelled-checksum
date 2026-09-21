# grading_guide.md — Task 03

> **Grader-facing. Contains the answer.** Never show this to a solver.
> Grading is defined here **against the answer locked in `STATE.md` / `golden/expected.json`**.
> It is not reverse-engineered from `problem.md`, and `problem.md` did not exist when this
> file was first written.

---

## 1. The correct answer

| Parameter | Value |
|---|---|
| `POLY`   | `0xDE27F4C90BA4596B` |
| `INIT`   | `0x2851D5EDB7B43883` |
| `XOROUT` | `0x2851D5EDB7B43883` |

## 2. Grading rule

**All three values must be exactly right. There is no partial credit.**

- Compare as 64-bit integers. Formatting is free: `0xDE27F4C90BA4596B`, `DE27F4C90BA4596B`,
  lower case, and the decimal `16008032544832641387` are the same answer. Leading `0x`, case,
  and underscores are ignored.
- The representation is fixed by the loop printed in `problem.md`: `POLY` is the 64-bit value
  XORed into the register during reduction, with the `x^64` term implicit. A 65-bit value, a
  bit-reversed value, or a "reciprocal" value is **wrong** (rows E and I below).
- A solver that reports only `POLY`, or reports the other two as "unknown" / "probably zero" /
  "standard", scores **0**. Recovering `POLY` is the easy third of the task.
- If the solver reports a triple **and** a contradicting claim (e.g. the right triple in a
  table but "so it's a bare CRC with no init" in prose), grade the triple.

### Why exact-match is the right rule here

Every wrong triple in §3 is wrong *categorically*, not approximately. There is no metric under
which `0x0000000000000000` is "close to" `0x2851D5EDB7B43883` — a one-bit error in any of the
three constants changes the output on essentially every message (row F: one bit in
`INIT`/`XOROUT` changes the `00` output from `0xAE3A4BA39060CB0B` to `0xAE3A4BA39060CA0A`).
"Nearly right" does not exist in this task.

## 3. Near-miss table

Every row is a triple a real solver plausibly arrives at. `divergence probe` is the shortest
message on which the candidate's output differs from the hidden system's — i.e. the query the
solver could have spent one unit on to falsify itself.

| # | Candidate `(POLY, INIT, XOROUT)` | How a solver lands here | Agrees with truth on | Divergence probe | Candidate says | Truth says | Verdict |
|---|---|---|---|---|---|---|---|
| **A** | `(DE27F4C90BA4596B, 0, 0)` | Queries the empty message, sees all zeroes, concludes "no init, no final xor — it's a bare CRC" (ECMA-182 / GO-ISO). Then extracts `POLY` correctly from the one-byte difference. **This is the shortcut.** | empty message | `00` | `0x0000000000000000` | `0xAE3A4BA39060CB0B` | **WRONG** |
| **B** | `(DE27F4C90BA4596B, FFFFFFFFFFFFFFFF, FFFFFFFFFFFFFFFF)` | Same empty-message reading, but assumes the all-ones convention (CRC-64/XZ, CRC-64/WE). Also consistent with `crc(empty) = 0`. | empty message | `00` | `0xBCF567CF22035A41` | `0xAE3A4BA39060CB0B` | **WRONG** |
| **C** | `(DE27F4C90BA4596B, 2851D5EDB7B43883, 0)` | Solves the linear system correctly, recovers `INIT`, then forgets that `XOROUT = crc(empty) ^ INIT` and leaves it at zero. The most *painful* near-miss: two of three correct, one step from the answer. | `01` only | empty message | `0x2851D5EDB7B43883` | `0x0000000000000000` | **WRONG** |
| **D** | `(DE27F4C90BA4596B, 0, 2851D5EDB7B43883)` | Recovers the constant but assigns it to the wrong role — treats it as a final xor applied to a zero-initialised register. | `01` only | empty message | `0x2851D5EDB7B43883` | `0x0000000000000000` | **WRONG** |
| **E** | `(D69A25D0932FE47B, 2851D5EDB7B43883, 2851D5EDB7B43883)` | Correct method, but reports the **bit-reversed** polynomial — habit from LSB-first CRC tables, where a poly is conventionally written reversed. | empty message | `00` | `0xA129D4155EDEB4F0` | `0xAE3A4BA39060CB0B` | **WRONG** |
| **F** | `(DE27F4C90BA4596B, 2851D5EDB7B43882, 2851D5EDB7B43882)` | Correct method, one bit lost in the GF(2) elimination (a sign the back-substitution or the bit-order convention is off by one). | empty message | `00` | `0xAE3A4BA39060CA0A` | `0xAE3A4BA39060CB0B` | **WRONG** |
| **G** | `(DE27F4C90BA4596A, 2851D5EDB7B43883, 2851D5EDB7B43883)` | One bit wrong in `POLY` — typically from mis-transcribing the XOR of the two one-byte outputs. | empty message | `00` | `0xAE3A4BA39060CB33` | `0xAE3A4BA39060CB0B` | **WRONG** |
| **H** | `(42F0E1EBA9EA3693, 0, 0)` | Pattern-matches the whole box to CRC-64/ECMA-182 without ever deriving `POLY`. Pure guess. | empty message | `00` | `0x0000000000000000` | `0xAE3A4BA39060CB0B` | **WRONG** |
| **I** | `(1DE27F4C90BA4596B, 2851D5EDB7B43883, 2851D5EDB7B43883)` | Everything right, but writes `POLY` with the implicit `x^64` term included (65 bits). A representation error, not a reasoning error — still wrong: the loop in `problem.md` XORs a 64-bit value. | — (not a 64-bit value) | — | — | — | **WRONG** |
| **J** | anything derived from `sample()` | Discovers the undocumented `sample()` surface, treats its reading as exact, and fits to corrupted data. Also burns budget. | nothing reliably | any | varies | varies | **WRONG** |
| **K** | `(DE27F4C90BA4596B, ?, ?)` — `POLY` only | Derives `POLY` from the one-byte difference, declares victory on the "hard part", hedges on the rest. | empty message | `00` | n/a | n/a | **WRONG** (incomplete) |
| **✓** | `(DE27F4C90BA4596B, 2851D5EDB7B43883, 2851D5EDB7B43883)` | Recognises the register update is GF(2)-linear; gets `POLY` from `crc(00) ^ crc(01)`; solves `(T ^ I)(INIT) = crc(00) ^ crc(empty)` by elimination; sets `XOROUT = crc(empty) ^ INIT`; verifies on an unused message. | everything | — | — | — | **CORRECT** |

### Rows A, B, E, F, G, H all agree with the truth on the empty message

That is the designed trap, not an accident — `INIT` was set equal to `XOROUT` precisely so
that `crc(empty) = 0x0000000000000000`, the same value rows A, B, H and the whole
`(POLY, W, W)` family all predict. A solver who probes only the empty message and reasons
from it has learned one true fact (`INIT ^ XOROUT = 0`) and nothing else, while feeling like
they have learned the answer.

### No near-miss can agree on all three base observations

Rows A–H are all falsified by the single probe `00`, or by the empty message. This is not
luck — it is the uniqueness proof in `STATE.md` §3: the three observations
`crc(empty)`, `crc(00)`, `crc(01)` admit **exactly one** triple. Any solver who buys all three
and checks its candidate against all three cannot submit a wrong answer.

**This is the crux of the grading.** The task does not punish solvers for not knowing CRC
arcana. It punishes solvers for not checking their answer against evidence they already paid
for, or could have paid for with three spare budget units.

### Verified: not even a reflected machine aliases

A natural objection is that a solver implementing the *LSB-first* (reflected) CRC dialect might
find some `(POLY', INIT', XOROUT')` that reproduces all three observations, which would make
the answer ambiguous. It does not exist, and this was checked rather than assumed:

- The reflected family requires `T_r(1) = crc(00) ^ crc(01) = 0xDE27F4C90BA4596B`, where `T_r`
  is the reflected byte transform.
- Enumerating **all** reflected polynomials satisfying that constraint — by conditioning on the
  8 branch bits of the shift loop, which makes each branch linear in `POLY'`, and enumerating
  the full solution space of each branch including nullspace — yields **no** candidate.
- The enumeration method was validated first by round-tripping random polynomials (12/12 at 32
  bits, 10/10 at 64 bits), so the empty result is a real absence, not a broken search.

So a solver who guesses the wrong bit order does not land on a self-consistent alias; they land
on a candidate that fails the very first probe they own. Graded wrong, and detectably so.

## 4. Acceptable variation in presentation

Accept: any radix or case for the three values; extra commentary; a reported "check value" for
`"123456789"` (`0x05F8D10865E59988`) alongside the triple; the observation `INIT == XOROUT`
stated as an aside.

Reject: a triple that is not exactly the locked one, for any reason, however well argued.
