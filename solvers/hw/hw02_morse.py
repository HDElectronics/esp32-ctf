#!/usr/bin/env python3
"""HW-02 Blinky Morse: decode the LED's on/off durations and submit the flag.

Input: a text file with one "<state> <milliseconds>" pair per line, state
1/0 or on/off (e.g. from frame-stepping a phone slow-motion video, or a light
sensor log). Lines like "[hwdev] m 1 300" from a CONFIG_CTF_HW_DEV build are
accepted too.

  hw02_morse.py durations.txt          decode + submit
  hw02_morse.py --dev                  dev build: sample the LED via `hwdev morse`
  hw02_morse.py --selftest             offline check of the decoder
"""
import argparse
import re
import statistics
import sys

from _util import DEFAULT_PORT, Console, submit_and_exit

MORSE = {
    "-----": "0", ".----": "1", "..---": "2", "...--": "3", "....-": "4",
    ".....": "5", "-....": "6", "--...": "7", "---..": "8", "----.": "9",
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E", "..-.": "F",
}


def parse_durations(text):
    runs = []
    for line in text.splitlines():
        m = re.search(r"\b(on|off|[01])\s+(\d+(?:\.\d+)?)\s*(?:ms)?\s*$", line.strip(), re.I)
        if m:
            state = m.group(1).lower()
            runs.append((1 if state in ("1", "on") else 0, float(m.group(2))))
    # Merge consecutive runs of the same state.
    merged = []
    for s, d in runs:
        if merged and merged[-1][0] == s:
            merged[-1] = (s, merged[-1][1] + d)
        else:
            merged.append((s, d))
    return merged


def decode(runs):
    """Return the list of complete repetitions decoded from (state, ms) runs."""
    ons = [d for s, d in runs if s]
    if not ons:
        return []
    shortest = min(ons)
    unit = statistics.median([d for d in ons if d < 2 * shortest])
    words, cur, sym, complete = [], "", "", False
    for s, d in runs:
        u = d / unit
        if s:
            sym += "." if u < 2 else "-"
            continue
        if u < 2:
            continue  # gap inside a character
        cur += MORSE.get(sym, "?") if sym else ""
        sym = ""
        if u >= 5:  # word gap / repetition pause
            if complete and cur:
                words.append(cur)
            cur, complete = "", True
    return words


def selftest():
    body = "0123456789AF"
    inv = {v: k for k, v in MORSE.items()}
    runs, unit = [(0, 1234)], 100
    for _ in range(2):
        for i, c in enumerate(body):
            code = inv[c]
            for j, e in enumerate(code):
                runs.append((1, unit * (3 if e == "-" else 1) * 1.05))
                gap = 1 if j < len(code) - 1 else (3 if i < len(body) - 1 else 7 + 20)
                runs.append((0, unit * gap * 0.97))
    runs.append((1, 100))  # partial next repetition
    got = decode(runs)
    assert got and all(w == body for w in got), got
    print("selftest ok:", got)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--dev", action="store_true", help="sample via `hwdev morse` (dev build)")
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.dev:
        con = Console(args.port)
        con.ser.write(b"hwdev morse 65\r\n")
        text = con.read_until(r"morse sample end", timeout=75)
        con.close()
    elif args.file:
        text = open(args.file).read()
    else:
        ap.error("give a durations file, --dev or --selftest")

    words = decode(parse_durations(text))
    print("decoded repetitions:", words)
    good = [w for w in words if re.fullmatch(r"[0-9A-F]{12}", w)]
    if not good:
        print("no complete 12-char repetition found; capture at least one full loop")
        sys.exit(1)
    submit_and_exit("ESP{%s}" % good[0], args.port)


if __name__ == "__main__":
    main()
