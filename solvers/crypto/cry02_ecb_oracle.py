#!/usr/bin/env python3
"""CRY-02 ECB penguin: byte-at-a-time recovery of the appended secret.

`oracle <hex>` returns AES-128-ECB(input || secret, PKCS#7). Pad the input so
the next unknown secret byte is the last byte of a block, then compare that
block with blocks built from our own guesses. Three guess blocks fit in front
of the padding in one query (64-byte input limit), so each query tests three
candidates.

usage: cry02_ecb_oracle.py [port]   (default /dev/ttyACM0)
"""
import re
import string
import sys
import time

from _util import FLAG_RE, cmd, open_console, port_arg, submit, sync

GUESSES_PER_QUERY = 3
# Flag-ish characters first, then the rest of printable ASCII.
CANDIDATES = list(dict.fromkeys("0123456789ABCDEF{}ESP" + string.printable))


def oracle(s, data):
    out = cmd(s, "oracle " + data.hex())
    m = re.search(r"^([0-9a-f]+)$", out, re.M)
    if not m:
        raise RuntimeError("bad oracle reply: %r" % out)
    ct = bytes.fromhex(m.group(1))
    return [ct[i:i + 16] for i in range(0, len(ct), 16)]


def main():
    s = open_console(port_arg())
    sync(s)
    start = time.monotonic()
    # Secret length: grow the input until the ciphertext gains a block.
    base = len(oracle(s, b""))
    for n in range(1, 17):
        if len(oracle(s, b"A" * n)) > base:
            secret_len = base * 16 - n
            break
    print("secret length", secret_len)

    known = b""
    g = GUESSES_PER_QUERY
    while len(known) < secret_len:
        i = len(known)
        pad = b"A" * (15 - i % 16)
        target_block = g + i // 16
        prefix = (pad + known)[-15:].rjust(15, b"A")
        found = None
        for k in range(0, len(CANDIDATES), g):
            cands = CANDIDATES[k:k + g]
            while len(cands) < g:
                cands.append(cands[-1])
            guess = b"".join(prefix + c.encode() for c in cands)
            blocks = oracle(s, guess + pad)
            for j, c in enumerate(cands):
                if blocks[j] == blocks[target_block]:
                    found = c.encode()
                    break
            if found:
                break
        if not found:
            print("stuck after", known)
            return 1
        known += found
        print(known.decode())
    print("recovered in %.1f s" % (time.monotonic() - start))
    m = FLAG_RE.search(known.decode())
    if not m:
        return 1
    return submit(s, m.group(0))


if __name__ == "__main__":
    sys.exit(main())
