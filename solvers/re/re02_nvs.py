#!/usr/bin/env python3
"""RE-02 NVS secrets.

Player path: dump the `nvs` partition, parse it with ESP-IDF's nvs_tool.py
(`nvs_tool.py -f json -d minimal nvs.bin`), find namespace "vault" key "k",
a 17-byte blob. Flags start with "ESP{", so the single XOR byte is
blob[0] ^ ord('E'); XOR every byte with it.
"""
import sys

import _util


def main():
    args = _util.parse_args(__doc__.splitlines()[0])
    flash = _util.Flash(args)
    entries = _util.nvs_entries(flash.partition_file("nvs"))
    blob = entries.get(("vault", "k"))
    if not isinstance(blob, bytes):
        sys.exit("vault/k not found in NVS")
    print("vault/k = " + blob.hex())
    key = blob[0] ^ ord("E")
    plain = bytes(b ^ key for b in blob)
    print("xor byte 0x%02x -> %r" % (key, plain))
    flag = _util.find_flag(plain)
    if not flag:
        sys.exit("decoded blob is not a flag")
    board = _util.Board(args.port)
    board.reset()
    sys.exit(0 if board.submit("RE-02", flag) else 1)


if __name__ == "__main__":
    main()
