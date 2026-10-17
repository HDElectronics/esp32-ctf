#!/usr/bin/env python3
"""BTC-01 SPP console: find the board by inquiry, open its SPP channel, read the banner."""
import re

import _util as u


def main():
    addr = u.board_address()
    try:
        spp = u.open_console(addr)
        print(spp.banner.replace("\r", "").rstrip())
        m = re.search(r"cipher shard 3/4: ([A-Z]{2})", spp.banner)
        print(f"CRY-01 shard 3: {m.group(1) if m else '?'}")
        flag = u.FLAG_RE.search(spp.banner)
        spp.close()
    finally:
        u.forget(addr)
    u.finish("BTC-01", flag.group(0) if flag else None)


main()
