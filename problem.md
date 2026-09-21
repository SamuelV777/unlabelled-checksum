# The Unlabelled Checksum

A device on your desk computes an integrity check. Feed it a byte string, it returns a 64-bit
value. It came with no datasheet.

You have disassembled its firmware, so you know **exactly** what it does — a textbook
byte-wise CRC register machine, 64 bits wide, most-significant-bit first, no reflection:

```python
def check(message: bytes) -> int:
    reg = INIT
    for byte in message:
        reg = (reg ^ (byte << 56)) & 0xFFFFFFFFFFFFFFFF
        for _ in range(8):
            if reg & 0x8000000000000000:
                reg = ((reg << 1) ^ POLY) & 0xFFFFFFFFFFFFFFFF
            else:
                reg = (reg << 1) & 0xFFFFFFFFFFFFFFFF
    return reg ^ XOROUT
```

That listing is the whole machine. There is no reflection step, no byte-order twist, no
table lookup that differs from this loop, nothing omitted.

What the disassembly did **not** give you is the three constants. They were fused into the
device.

## Your task

Recover `POLY`, `INIT`, and `XOROUT`.

## How to probe the device

```powershell
python oracle/oracle.py evaluate 00 01ff ""
python oracle/oracle.py help
```

Or from Python:

```python
import sys; sys.path.insert(0, "oracle")
from oracle import Oracle

device = Oracle()
value = device.evaluate("00")       # hex string, or bytes; "" is the empty message
print(f"0x{value:016X}")
print(device.remaining)             # budget left
print(device.help())                # free
```

| Surface | What it does | Cost |
|---|---|---|
| `evaluate(message)` | returns the device's exact 64-bit output for that message | **1 unit** |
| `help()` | a free hint | 0 units |

`message` is any byte string, given as bytes or as a hex string. The empty message is legal.
Outputs are exact — the device is deterministic and returns no noise.

## Your budget: 6 units

Six `evaluate` calls. That is the entire investigation. When the budget is gone, it is gone —
further calls raise `BudgetExhausted`, and a fresh `Oracle()` is a fresh session, not a refill.

Six is more than the minimum this problem requires. The surplus is there to be used.

## Ground rules

- **Treat the device as a black box.** Its parameters are packed inside `oracle/oracle.py`.
  Unpacking them from the file is not a solution, it is a confession.
- Everything runs offline. Standard library only. No network, no keys.
- **Search is not a route.** The three constants span 2^192 possibilities. Even after your
  best cheap observations you will not be able to narrow that to something you can sweep in
  the time you have — and sweeping is not what this problem is asking for anyway.

## What to report

Three 64-bit values:

```
POLY   = 0x????????????????
INIT   = 0x????????????????
XOROUT = 0x????????????????
```

Report them in the representation the loop above uses — `POLY` is the 64-bit value XORed into
the register during reduction, with the `x^64` term implicit and not part of the number.

**All three must be exactly right.** Two out of three is not a partial success; a device
programmed with two of your three constants computes different checksums than the one on your
desk. Getting the polynomial and guessing the rest is the failure mode this problem is built
to catch.

Before you submit: a candidate is only worth submitting if it reproduces **every** output you
have observed — including the ones that did not suggest it.
