#!/usr/bin/env python3
"""CRY-01 Classic cipher: Vigenere with a key made of 4 two-letter shards.

Player path: collect the shards printed as `cipher shard <i>/4: XY` by four
tracks -- 1: serial boot log, 2: BLE CTF service characteristic, 3: BT Classic
SPP banner, 4: web landing page footer -- and pass them as the key, e.g.
    cry01_cipher.py /dev/ttyACM0 ABCDEFGH
Without a key argument the script resets the board and reads shard 1 from the
boot log; shards 2-4 then come from the same log only on a firmware built with
CONFIG_CTF_CRYPTO_DEV=y (dev self-test line), used to test before the radio and
web tracks exist.

Decrypt: letters shift back by the key letter, digits pass through and do not
advance the key. The plaintext is the bare 12-hex flag body.

usage: cry01_cipher.py [port] [KEY8]
"""
import re
import sys

from _util import cmd, open_console, port_arg, reset_and_capture, submit, sync


def shards_from_boot(log):
    shards = {}
    for i, xy in re.findall(r"cipher shard (\d)/4: ([A-Z]{2})", log):
        shards[int(i)] = xy
    m = re.search(r"CRY-01 shards ([A-Z]{2}) ([A-Z]{2}) ([A-Z]{2}) ([A-Z]{2})", log)
    if m:
        for i in range(4):
            shards.setdefault(i + 1, m.group(i + 1))
    return shards


def decrypt(ct, key):
    out, k = [], 0
    for ch in ct:
        if "A" <= ch <= "Z":
            out.append(chr((ord(ch) - ord(key[k % len(key)])) % 26 + ord("A")))
            k += 1
        else:
            out.append(ch)
    return "".join(out)


def main():
    s = open_console(port_arg())
    if len(sys.argv) > 2:
        key = sys.argv[2].upper()
    else:
        shards = shards_from_boot(reset_and_capture(s))
        print("shards:", shards)
        if sorted(shards) != [1, 2, 3, 4]:
            print("missing shards; pass the 8-letter key collected from the other tracks")
            return 1
        key = "".join(shards[i] for i in range(1, 5))
    sync(s)
    out = cmd(s, "cipher")
    print(out)
    m = re.search(r"Intercepted: ([0-9A-Z]{12})", out)
    if not m:
        return 1
    body = decrypt(m.group(1), key)
    print("key %s -> body %s" % (key, body))
    return submit(s, body)


if __name__ == "__main__":
    sys.exit(main())
