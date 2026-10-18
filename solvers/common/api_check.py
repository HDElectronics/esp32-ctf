#!/usr/bin/env python3
"""Machine-channel check for the player app protocol (SPEC "v0.2.0").

Sends SOH-prefixed `api ...` lines to the board console and checks the
STX/ETX JSON frames, the hint wallet and the human `status` / `hint` output.

    .venv/bin/python solvers/common/api_check.py [--port /dev/ttyACM0] [--fresh] [--no-mode]

--fresh   runs `reset yes` first (wipes progress!) so absolute point values
          (100 -> 80 -> 180) are checked; without it, checks are relative.
--no-mode skips `api mode radio` (which reboots the board, staying in radio mode).

Organizer tool: it submits the board's SER-01 flag and buys SER-01 tier 2.
Exit status 0 when every check passes.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.console import PROMPT, Console, add_port_arg  # noqa: E402

SOH, STX, ETX = b"\x01", b"\x02", b"\x03"
FRAME_RE = re.compile(rb"\x02([^\x02\x03]*)\x03\r\n")
SER01_RE = re.compile(r"selftest token (ESP\{[0-9A-F]{12}\})")

failures = 0


def check(cond, what):
    global failures
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        failures += 1
    return cond


def api(c, line, timeout=5.0, prefix=b""):
    """Send `prefix` + SOH + line + CR; return (parsed json, raw text outside the frame)."""
    c.write(prefix + SOH + line.encode() + b"\r")
    c.flush()
    buf = b""
    end = time.monotonic() + timeout
    m = None
    while time.monotonic() < end:
        buf += c.read(4096)
        m = FRAME_RE.search(buf)
        if m:
            break
    if not m:
        raise SystemExit("no frame for %r; got %r" % (line, buf[-300:]))
    outside = buf[: m.start()] + buf[m.end():]
    # Nothing else is printed for a machine line: no echo, no prompt.
    outside += c.read(4096) if c.in_waiting else b""
    return json.loads(m.group(1).decode()), outside.decode(errors="replace"), len(m.group(1))


def no_echo(line, outside):
    return line not in outside and PROMPT.decode() not in outside


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_port_arg(ap)
    ap.add_argument("--fresh", action="store_true", help="`reset yes` first (wipes progress)")
    ap.add_argument("--no-mode", action="store_true", help="skip the `api mode radio` reboot test")
    args = ap.parse_args()

    with Console(args.port) as c:
        print("boot")
        if args.fresh:
            c.sync()
            c.send("reset yes")
            log = c.read_until(b"type `help`", 15).decode(errors="replace")
            log += c.read_until(PROMPT, 5).decode(errors="replace")
        else:
            log = c.reset_board()
        m = SER01_RE.search(log)
        check(m is not None, "SER-01 flag in the boot banner")
        flag = m.group(1) if m else "ESP{000000000000}"
        time.sleep(1.0)
        c.drain(0.5)
        c.sync()

        print("api info")
        info, out, _ = api(c, "api info")
        print("   ", json.dumps(info))
        check(no_echo("api info", out), "no echo / no prompt for a machine line")
        check(info.get("ok") is True and info.get("fw") == "0.2.0", "ok + fw 0.2.0")
        check(re.fullmatch(r"ESP32-CTF-[0-9A-F]{4}", info.get("board", "")) is not None, "board name")
        check(info.get("mode") in ("radio", "net"), "mode")
        check(info.get("start") == 100 and info.get("total") == 40, "start 100, total 40")
        check(info["points"] == info["start"] + info["earned"] - info["spent"], "points arithmetic")
        if args.fresh:
            check(info["points"] == 100 and info["solved"] == 0, "fresh: 100 points, 0 solved")
        p0 = info["points"]

        print("api list")
        lst, out, n = api(c, "api list", timeout=8)
        print("    %d bytes, first: %s" % (n, json.dumps(lst["challenges"][0])))
        ch = lst.get("challenges", [])
        check(lst.get("ok") is True and len(ch) == 40, "40 challenges")
        check(len({x["id"] for x in ch}) == 40, "unique ids")
        prices_ok = all(x["prices"] == [0, round(0.2 * x["pts"]), round(0.5 * x["pts"])] for x in ch)
        check(prices_ok, "prices = [0, 0.2v, 0.5v] for every challenge")
        modes_ok = all(x["mode"] == {"BLE": "radio", "BTC": "radio", "WEB": "net"}.get(x["track"], "any")
                       for x in ch)
        check(modes_ok, "mode per track")
        check(all(x["tier"] in (1, 2, 3) and isinstance(x["solved"], bool) for x in ch), "tier / solved types")
        check(sum(x["pts"] for x in ch) == 7300, "values sum to 7300")
        check(next(x for x in ch if x["id"] == "HW-03")["kit"] == "logic analyzer", "kit label")
        ser01 = next(x for x in ch if x["id"] == "SER-01")
        t0 = ser01["tier"]

        print("api hint")
        h3, out, _ = api(c, "api hint SER-01 3")
        print("   ", json.dumps(h3))
        if t0 == 1:
            check(h3 == {"ok": False, "error": "locked", "need": 50, "points": p0}, "tier 3 before 2 -> locked")
        h2, out, _ = api(c, "api hint SER-01 2")
        print("   ", json.dumps(h2)[:160])
        check(h2.get("ok") is True and h2.get("tier") == 2 and isinstance(h2.get("text"), str), "tier 2 ok")
        p1 = p0 - (20 if t0 == 1 else 0)
        check(h2.get("points") == p1, "tier 2 costs 20 (points %d)" % p1)
        if args.fresh:
            check(h2.get("points") == 80, "fresh: 80 points")
        again, _, _ = api(c, "api hint ser-01 2")
        check(again.get("ok") is True and again.get("points") == p1, "owned tier is free (lower-case id)")
        h1, _, _ = api(c, "api hint SER-01 1")
        check(h1.get("ok") is True and h1.get("tier") == 1, "tier 1 free")
        bad, _, _ = api(c, "api hint SER-01 9")
        check(bad == {"ok": False, "error": "bad tier"}, "bad tier")
        unk, _, _ = api(c, "api hint NOPE-01 2")
        check(unk == {"ok": False, "error": "unknown challenge"}, "unknown challenge")

        print("api submit")
        w, out, _ = api(c, "api submit ESP{000000000000}")
        print("   ", json.dumps(w))
        check(w == {"ok": True, "result": "wrong", "points": p1}, "wrong flag")
        s, out, _ = api(c, "api submit " + flag)
        print("   ", json.dumps(s))
        new = not ser01["solved"]
        check(s.get("result") == ("new" if new else "already") and s.get("id") == "SER-01"
              and s.get("pts") == 100, "SER-01 flag accepted")
        p2 = p1 + (100 if new else 0)
        check(s.get("points") == p2, "points after solve %d" % p2)
        if args.fresh:
            check(s.get("points") == 180, "fresh: 180 points")
        s2, _, _ = api(c, "api submit " + flag.lower())
        check(s2.get("result") == "already" and s2.get("points") == p2, "resubmit -> already")

        print("api answer / errors")
        a, _, _ = api(c, "api answer HW-03 1")
        check(a == {"ok": True, "correct": False}, "wrong answer")
        a, _, _ = api(c, "api answer NOPE-01 1")
        check(a == {"ok": False, "error": "unknown challenge"}, "answer unknown id")
        e, _, _ = api(c, "api bogus")
        check(e == {"ok": False, "error": "unknown command"}, "unknown api command")
        e, _, _ = api(c, "status")
        check(e == {"ok": False, "error": "unknown command"}, "non-api machine line")
        e, _, _ = api(c, "api mode")
        check(e.get("ok") is False, "api mode without argument")

        print("interleaving")
        # Human command output right before the frame, in the same write.
        c.sync()
        info2, out, _ = api(c, "api info", prefix=b"help\r")
        check(info2.get("points") == p2 and "status" in out, "frame parsed amid `help` output")
        # SER-04 escape hook output right after the frame (hook sees bytes first).
        c.sync()
        c.write(SOH + b"api info\r" + b"\x1ddbg")
        c.flush()
        raw = c.read_until(b"exiting debug monitor", 5)
        m2 = FRAME_RE.search(raw)
        check(m2 is not None and b"session key" in raw[m2.end():], "frame + SER-04 output both intact")
        # Machine line in the middle of a half-typed human line.
        c.sync()
        c.write(b"sta")
        c.flush()
        time.sleep(0.2)
        info3, out, _ = api(c, "api info")
        c.write(b"tus\r")
        c.flush()
        rest = c.read_until(PROMPT, 3).decode(errors="replace")
        check(info3.get("ok") is True and "Points:" in rest, "half-typed human line survives a machine line")

        print("human console")
        st = c.cmd("status")
        print("\n".join("    | " + x for x in st.splitlines()))
        check(st.startswith("Points: %d (started with 100, +" % p2), "status first line")
        check("SER-01 (2)" in st, "status lists bought hint")
        hl = c.cmd("hint SER-01")
        print("\n".join("    | " + x for x in hl.splitlines()))
        check("Walkthrough" in hl and "[buy: hint SER-01 3]" in hl, "hint tier list")
        hp = c.cmd("hint SER-01 3")
        print("\n".join("    | " + x for x in hp.splitlines()))
        check("costs 50 points" in hp and "hint SER-01 3 yes" in hp, "tier 3 price prompt")

        if not args.no_mode:
            print("api mode (reboot)")
            c.sync()
            mode = info["mode"]
            md, out, _ = api(c, "api mode " + mode)
            print("   ", json.dumps(md))
            check(md == {"ok": True, "mode": mode, "rebooting": True}, "mode reply")
            boot = c.read_until(b"type `help`", 15).decode(errors="replace")
            check("mode: " + mode in boot, "board rebooted into %s mode" % mode)
            c.read_until(PROMPT, 5)
            time.sleep(1.0)
            c.drain(0.5)
            info4, _, _ = api(c, "api info")
            check(info4.get("points") == p2 and info4.get("mode") == mode, "progress kept across reboot")

    print("%s: %d failure(s)" % ("PASS" if not failures else "FAIL", failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
