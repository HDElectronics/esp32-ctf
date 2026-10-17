#!/usr/bin/env python3
"""SER-04 Escape sequence: Ctrl-] (0x1D) then "dbg" within one second.

The console watches the raw byte stream for the escape key followed by a short
debugging word; the hidden monitor prints the flag.

usage: ser04_escape.py [port]   (default /dev/ttyACM0)
"""
import sys

from _util import FLAG_RE, open_console, port_arg, read_until, submit, sync


def main():
    s = open_console(port_arg())
    sync(s)
    s.write(b"\x1ddbg")
    s.flush()
    out = read_until(s, b"exiting", 3.0).decode(errors="replace")
    print(out.strip())
    m = FLAG_RE.search(out)
    if not m:
        print("no hidden prompt")
        return 1
    sync(s)
    return submit(s, m.group(0))


if __name__ == "__main__":
    sys.exit(main())
