#!/usr/bin/env python3
"""HW-05 SPI dump: decode the bit-banged SPI (mode 0) transfer and submit.

Wiring: analyzer GND -> board GND, D0 -> GPIO18 (SCK), D1 -> GPIO23 (MOSI),
D2 -> GPIO5 (CS, active low). Capture >= 11 s at >= 1 MHz (a burst every 10 s).

With sigrok's decoder:
  sigrok-cli -d fx2lafw --config samplerate=1m --time 11s -C D0,D1,D2 \
      -P spi:clk=D0:mosi=D1:cs=D2:cpol=0:cpha=0 -A spi=mosi-data > spi.txt
  hw05_spi.py --annotations spi.txt
or raw samples:
  sigrok-cli -d fx2lafw --config samplerate=1m --time 11s -C D0,D1,D2 -O csv > spi.csv
  hw05_spi.py spi.csv --sck D0 --mosi D1 --cs D2
  hw05_spi.py --selftest
"""
import argparse
import sys

from _util import DEFAULT_PORT, bytes_from_annotations, channel_index, load_logic_csv, \
    submit_and_exit, wrap_flag


def decode_spi(samples):
    """samples: iterable of (sck, mosi, cs). Mode 0, MSB first. Bytes per CS frame."""
    frames, cur, bits, prev = [], None, [], None
    for sck, mosi, cs in samples:
        if prev is not None:
            psck, _, pcs = prev
            if pcs and not cs:
                cur, bits = bytearray(), []
            elif not pcs and cs and cur is not None:
                frames.append(bytes(cur))
                cur = None
            elif cur is not None and not cs and not psck and sck:
                bits.append(mosi)
                if len(bits) == 8:
                    b = 0
                    for x in bits:
                        b = (b << 1) | x
                    cur.append(b)
                    bits = []
        prev = (sck, mosi, cs)
    return frames


def synth(payload, half=5):
    s = [(0, 0, 1)] * 30 + [(0, 0, 0)] * 10
    for b in payload:
        for i in range(7, -1, -1):
            bit = (b >> i) & 1
            s += [(0, bit, 0)] * half + [(1, bit, 0)] * half
    return s + [(0, 0, 0)] * 10 + [(0, 0, 1)] * 30


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--annotations")
    ap.add_argument("--sck", default="D0")
    ap.add_argument("--mosi", default="D1")
    ap.add_argument("--cs", default="D2")
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        flag = b"ESP{0123456789AB}"
        got = decode_spi(synth(flag) + synth(flag))
        assert got == [flag, flag], got
        print("selftest ok:", got[0])
        return
    if args.annotations:
        text = open(args.annotations).read()
        data = bytes_from_annotations(text, "spi")
    elif args.csv:
        names, rows = load_logic_csv(args.csv)
        k = [channel_index(names, c) for c in (args.sck, args.mosi, args.cs)]
        frames = decode_spi((r[k[0]], r[k[1]], r[k[2]]) for r in rows)
        for f in frames:
            print("frame:", f)
        data = b"".join(frames)
    else:
        ap.error("give a CSV capture, --annotations or --selftest")

    flag = wrap_flag(data.decode("ascii", "replace"))
    if not flag:
        print("no flag in decoded bytes:", data)
        sys.exit(1)
    submit_and_exit(flag, args.port)


if __name__ == "__main__":
    main()
