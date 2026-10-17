#!/usr/bin/env python3
"""BTC-02 Hidden menu: the banner names a verb that `help` leaves out; run it."""
import re

import _util as u


def main():
    addr = u.board_address()
    try:
        spp = u.open_console(addr)
        listed = re.findall(r"^\s+(\w+)\s", spp.cmd("help"), re.M)
        print(f"help lists: {' '.join(listed)}")
        hidden = [v for v in re.findall(r"`(\w+)`", spp.banner) if v not in listed]
        print(f"banner mentions unlisted verb(s): {' '.join(hidden)}")
        flag = None
        for verb in hidden:
            out = spp.cmd(verb)
            print(out.rstrip())
            m = u.FLAG_RE.search(out)
            if m:
                flag = m.group(0)
                break
        spp.close()
    finally:
        u.forget(addr)
    u.finish("BTC-02", flag)


main()
