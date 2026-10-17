#!/usr/bin/env python3
"""CRY-03 Reused nonce: two AES-CTR messages share one keystream.

C1 xor P1 = keystream, so P2 = C2 xor C1 xor P1 (P1 is known and longer).

usage: cry03_reused_nonce.py [port]   (default /dev/ttyACM0)
"""
import re
import sys

from _util import FLAG_RE, cmd, open_console, port_arg, submit, sync


def main():
    s = open_console(port_arg())
    sync(s)
    out = cmd(s, "msgs")
    print(out)
    p1 = re.search(r"msg 1 plaintext \(recovered earlier\): (.*)", out).group(1).encode()
    c1 = bytes.fromhex(re.search(r"msg 1 ciphertext: ([0-9a-f]+)", out).group(1))
    c2 = bytes.fromhex(re.search(r"msg 2 ciphertext: ([0-9a-f]+)", out).group(1))
    p2 = bytes(a ^ b ^ c for a, b, c in zip(c1, c2, p1)).decode(errors="replace")
    print("msg 2:", p2)
    m = FLAG_RE.search(p2)
    if not m:
        return 1
    return submit(s, m.group(0))


if __name__ == "__main__":
    sys.exit(main())
