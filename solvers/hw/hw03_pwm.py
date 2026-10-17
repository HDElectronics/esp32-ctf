#!/usr/bin/env python3
"""HW-03 PWM frequency: give the measured GPIO25 frequency to the answer gate.

  hw03_pwm.py 4321.5     answer with a measured frequency (Hz), submit the flag
  hw03_pwm.py --dev      dev build: use the PCNT self-measurement from `hwdev`

Measure with a logic analyzer, e.g.
  sigrok-cli -d fx2lafw --config samplerate=1m --samples 1m -C D0 -O csv > pwm.csv
  hw03_pwm.py --csv pwm.csv --rate 1000000
"""
import argparse
import re
import sys

from _util import DEFAULT_PORT, FLAG_RE, Console, channel_index, load_logic_csv


def freq_from_csv(path, rate, chan):
    names, rows = load_logic_csv(path)
    i = channel_index(names, chan)
    rises = [n for n in range(1, len(rows)) if rows[n - 1][i] == 0 and rows[n][i] == 1]
    if len(rises) < 2:
        raise SystemExit("not enough rising edges in capture")
    return rate * (len(rises) - 1) / (rises[-1] - rises[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hz", nargs="?", type=float)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--csv")
    ap.add_argument("--rate", type=float, help="capture sample rate (Hz) for --csv")
    ap.add_argument("--chan", default="D0")
    ap.add_argument("--port", default=DEFAULT_PORT)
    args = ap.parse_args()

    con = None
    if args.csv:
        if not args.rate:
            ap.error("--csv needs --rate")
        hz = freq_from_csv(args.csv, args.rate, args.chan)
    elif args.dev:
        con = Console(args.port)
        out = con.cmd("hwdev", timeout=5)
        m = re.search(r"pcnt (\d+) Hz", out)
        if not m:
            print(out)
            sys.exit("no `hwdev` output (dev build needed)")
        hz = float(m.group(1))
    elif args.hz:
        hz = args.hz
    else:
        ap.error("give a frequency, --csv or --dev")

    print("measured: %.1f Hz" % hz)
    con = con or Console(args.port)
    out = con.cmd("answer HW-03 %.0f" % hz)
    print(out)
    m = FLAG_RE.search(out)
    if not m:
        con.close()
        sys.exit(1)
    ok = con.submit(m.group(0))
    con.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
