#!/usr/bin/env python3
"""HW-06 Touch pad code: read the `keypad` clue, work out the sequence, then
wait while you touch the pads; submits the flag the board prints.

The clue gives a decimal number; written in base 4 with 6 digits it is the
sequence, A=0 B=1 C=2 D=3 (A=GPIO4, B=GPIO13, C=GPIO27, D=GPIO32).
"""
import argparse
import re
import sys

from _util import DEFAULT_PORT, Console, FLAG_RE


def sequence(n):
    digits = []
    for _ in range(6):
        digits.append("ABCD"[n % 4])
        n //= 4
    return "".join(reversed(digits))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--wait", type=float, default=60, help="seconds to wait for the touches")
    args = ap.parse_args()

    assert sequence(2731) == "CCCCCD"  # 2731 = 222223 in base 4
    con = Console(args.port)
    clue = con.cmd("keypad")
    print(clue)
    m = re.search(r"Combo #(\d+)", clue)
    if not m:
        sys.exit("no clue")
    seq = sequence(int(m.group(1)))
    print("Touch the pads in this order (<= 10 s apart, lift between taps):", " ".join(seq))
    out = con.read_until(r"HW-06 flag: " + FLAG_RE.pattern, timeout=args.wait)
    f = re.search(r"HW-06 flag: (" + FLAG_RE.pattern + ")", out)
    if not f:
        sys.exit("no flag yet; try again (touch firmly, one pad at a time)")
    ok = con.submit(f.group(1))
    con.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
