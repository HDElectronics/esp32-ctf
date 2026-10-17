#!/usr/bin/env python3
"""HW-04 I2C chatter: decode the bit-banged I2C write to 0x5A and submit.

Wiring: analyzer GND -> board GND, D0 -> GPIO22 (SCL), D1 -> GPIO21 (SDA).
Capture >= 6 s at >= 500 kHz (the bus runs at ~50 kHz, a burst every 5 s).

Either let sigrok decode and pass its annotations:
  sigrok-cli -d fx2lafw --config samplerate=1m --time 6s -C D0,D1 \
      -P i2c:scl=D0:sda=D1 -A i2c=address-write:data-write > i2c.txt
  hw04_i2c.py --annotations i2c.txt
or export raw samples and decode here:
  sigrok-cli -d fx2lafw --config samplerate=1m --time 6s -C D0,D1 -O csv > i2c.csv
  hw04_i2c.py i2c.csv --scl D0 --sda D1
  hw04_i2c.py --selftest
"""
import argparse
import sys

from _util import DEFAULT_PORT, bytes_from_annotations, channel_index, load_logic_csv, \
    submit_and_exit, wrap_flag

ADDR = 0x5A


def decode_i2c(samples):
    """samples: iterable of (scl, sda). Returns [(addr, rw, bytes)] per transaction."""
    out, bits, cur = [], [], None
    prev = None
    for scl, sda in samples:
        if prev is not None:
            pscl, psda = prev
            if pscl and scl and psda and not sda:  # START / repeated START
                if cur and cur[2]:
                    out.append(cur)
                cur, bits = [None, None, bytearray()], []
            elif pscl and scl and not psda and sda:  # STOP
                if cur:
                    out.append(cur)
                cur, bits = None, []
            elif not pscl and scl and cur is not None:  # SCL rising: sample SDA
                bits.append(sda)
                if len(bits) == 9:  # 8 data bits + ACK slot (ignored)
                    b = 0
                    for x in bits[:8]:
                        b = (b << 1) | x
                    if cur[0] is None:
                        cur[0], cur[1] = b >> 1, b & 1
                    else:
                        cur[2].append(b)
                    bits = []
        prev = (scl, sda)
    return [(a, rw, bytes(d)) for a, rw, d in out if a is not None]


def synth(payload, half=10):
    """Synthesize (scl, sda) samples at 1 sample/us for a write to ADDR."""
    s = [(1, 1)] * 50
    s += [(1, 0)] * half + [(0, 0)] * half
    for b in [ADDR << 1] + list(payload):
        for i in range(7, -1, -1):
            bit = (b >> i) & 1
            s += [(0, bit)] * half + [(1, bit)] * half
        s += [(0, 1)] * half + [(1, 1)] * half  # NACK
    s += [(0, 0)] * half + [(1, 0)] * half + [(1, 1)] * 50
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--annotations")
    ap.add_argument("--scl", default="D0")
    ap.add_argument("--sda", default="D1")
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        flag = b"ESP{0123456789AB}"
        got = decode_i2c(synth(flag) + synth(flag))
        assert got == [(ADDR, 0, flag)] * 2, got
        print("selftest ok:", got[0])
        return
    if args.annotations:
        data = bytes_from_annotations(open(args.annotations).read(), "data write")
    elif args.csv:
        names, rows = load_logic_csv(args.csv)
        ci, di = channel_index(names, args.scl), channel_index(names, args.sda)
        txs = decode_i2c((r[ci], r[di]) for r in rows)
        for a, rw, d in txs:
            print("addr 0x%02X %s: %r" % (a, "R" if rw else "W", d))
        data = b"".join(d for a, rw, d in txs if a == ADDR and rw == 0)
    else:
        ap.error("give a CSV capture, --annotations or --selftest")

    flag = wrap_flag(data.decode("ascii", "replace"))
    if not flag:
        print("no flag in decoded bytes:", data)
        sys.exit(1)
    submit_and_exit(flag, args.port)


if __name__ == "__main__":
    main()
