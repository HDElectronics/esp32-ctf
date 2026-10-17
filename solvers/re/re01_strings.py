#!/usr/bin/env python3
"""RE-01 Strings in flash.

Player path: dump the partition table, notice the odd raw data partition
`notes` (subtype 0x40), dump it with `esptool read-flash` and run `strings`.
The operator notes contain the maintenance token (the flag).
"""
import re
import shutil
import subprocess
import sys

import _util


def strings(path):
    if shutil.which("strings"):
        return subprocess.run(["strings", "-n", "6", path], check=True,
                              capture_output=True, text=True).stdout
    with open(path, "rb") as f:
        return "\n".join(m.decode() for m in re.findall(rb"[\x20-\x7e\t]{6,}", f.read()))


def main():
    args = _util.parse_args(__doc__.splitlines()[0])
    flash = _util.Flash(args)
    text = strings(flash.partition_file("notes"))
    print(text)
    flag = _util.find_flag(text.encode())
    if not flag:
        sys.exit("no flag in notes partition")
    board = _util.Board(args.port)
    board.reset()
    sys.exit(0 if board.submit("RE-01", flag) else 1)


if __name__ == "__main__":
    main()
