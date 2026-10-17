#!/usr/bin/env python3
"""RE-04 XOR'd asset.

Player path:
1. Dump the `storage` (SPIFFS) partition and grep for the "XBLOB1" magic from
   the operator notes; the 17 bytes after it are the encrypted flag. (Or list
   the filesystem with mkspiffs / spiffsgen and pull /blob.bin.)
2. In Ghidra, the code that writes /storage/blob.bin (xref to the
   "/storage/blob.bin" string) builds a 32-bit seed from MAC bytes 2..5
   (big-endian) XOR 0x5A17C3E9, then for every byte clocks a right-shift
   Galois LFSR 8 times (mask 0x80200003) and XORs the low byte of the state.
3. The MAC is printed in the boot banner; reproduce the keystream.
"""
import sys

import _util

MAGIC = b"XBLOB1"


def keystream(mac, n):
    s = int.from_bytes(mac[2:6], "big") ^ 0x5A17C3E9
    s = s or 1
    out = bytearray()
    for _ in range(n):
        for _ in range(8):
            lsb = s & 1
            s >>= 1
            if lsb:
                s ^= 0x80200003
        out.append(s & 0xFF)
    return bytes(out)


def main():
    args = _util.parse_args(__doc__.splitlines()[0],
                            lambda ap: ap.add_argument("--mac", help="board MAC aa:bb:..; "
                                                       "default: read from the boot banner"))
    flash = _util.Flash(args)
    data = flash.partition("storage")
    board = _util.Board(args.port)
    board.reset()
    mac = bytes.fromhex(args.mac.replace(":", "")) if args.mac else board.mac()
    print("board MAC " + mac.hex(":"))
    ks = keystream(mac, 17)
    flag = None
    pos = data.find(MAGIC)
    while pos >= 0 and not flag:
        ct = data[pos + len(MAGIC):pos + len(MAGIC) + 17]
        print("XBLOB1 at storage+0x%x: %s" % (pos, ct.hex()))
        flag = _util.find_flag(bytes(a ^ b for a, b in zip(ct, ks)))
        pos = data.find(MAGIC, pos + 1)
    if not flag:
        sys.exit("no decodable XBLOB1 blob in storage")
    sys.exit(0 if board.submit("RE-04", flag) else 1)


if __name__ == "__main__":
    main()
