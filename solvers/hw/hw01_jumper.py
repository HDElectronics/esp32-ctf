#!/usr/bin/env python3
"""HW-01 Jumper it: bridge GPIO26 -> GPIO33 with a jumper wire, then run this.

It resets the board (RTS -> EN), reads the boot log for the flag the jumper
check prints, and submits it. Without the jumper the log says
"pin check GPIO26->GPIO33: open".
"""
import argparse
import re
import sys

from _util import DEFAULT_PORT, FLAG_RE, Console


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    con = Console(args.port, reset=True)
    log = con.read_until(r"HW-01 flag: ESP\{[0-9A-F]{12}\}|GPIO26->GPIO33: open", timeout=10)
    m = re.search(r"HW-01 flag: (" + FLAG_RE.pattern + ")", log)
    if not m:
        print("No HW-01 flag in the boot log. Is the jumper GPIO26 <-> GPIO33 in place?")
        sys.exit(1)
    flag = m.group(1)
    print("flag:", flag)
    con.read_until(r"ctf> ", timeout=10)
    ok = con.submit(flag)
    con.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
