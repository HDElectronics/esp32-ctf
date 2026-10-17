#!/usr/bin/env python3
"""RE-03 Crackme.

Player path:
1. Dump the factory app and load it in Ghidra (see README.md). Search for the
   string "unlock", follow the xref to the esp_console_cmd_t registration and
   from there to the command handler. The handler opens NVS namespace "vault",
   reads blob "chk" (12 bytes), requires a 12-character argument, runs it
   through a small byte routine and compares the result with chk.
2. The routine, as recovered from the Ghidra decompilation:
       r = 0xA7
       for i in 0..11:
           x = in[i] ^ r
           x = rotl8(x, (i & 3) + 1)
           x = (x + 0x33 + i * 0x1D) & 0xFF
           out[i] = x
           r = (r * 5 + x) & 0xFF
   Every step is invertible and r only depends on earlier outputs, so it runs
   backwards byte by byte (inverse below; the player derives it from Ghidra).
3. Dump NVS, read vault/chk with nvs_tool.py, invert -> key, `unlock <key>`
   prints the flag.
"""
import re
import sys

import _util


def rotr8(x, s):
    return ((x >> s) | (x << (8 - s))) & 0xFF


def unfold(chk):
    r = 0xA7
    key = bytearray()
    for i, o in enumerate(chk):
        x = (o - 0x33 - i * 0x1D) & 0xFF
        x = rotr8(x, (i & 3) + 1)
        key.append(x ^ r)
        r = (r * 5 + o) & 0xFF
    return bytes(key)


def main():
    args = _util.parse_args(__doc__.splitlines()[0])
    flash = _util.Flash(args)
    entries = _util.nvs_entries(flash.partition_file("nvs"))
    chk = entries.get(("vault", "chk"))
    if not isinstance(chk, bytes) or len(chk) != 12:
        sys.exit("vault/chk not found in NVS")
    print("vault/chk = " + chk.hex())
    key = unfold(chk).decode("ascii")
    print("recovered key: " + key)
    board = _util.Board(args.port)
    board.reset()
    out = board.cmd("unlock " + key)
    flag = _util.find_flag(out.encode())
    if not flag:
        sys.exit("unlock did not return a flag")
    sys.exit(0 if board.submit("RE-03", flag) else 1)


if __name__ == "__main__":
    main()
