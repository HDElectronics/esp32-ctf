#!/usr/bin/env python3
"""WEB-01 Hidden SSID: `wifi` on the console gives the SSID in base32 and the
WPA2 password; join the hidden network (e.g. `nmcli dev wifi connect <ssid>
password <pw> hidden yes`, done by the player, not this script), then the
landing page shows the flag. Also prints CRY-01 shard 4 from the page footer."""
import re

import requests

import _util as u


def main():
    a = u.args(__doc__, default_via="web")
    info = u.wifi_info(a.serial)
    print(info["raw"])
    print(f"decoded ssid: {info.get('ssid')!r}  password: {info.get('password')!r}")
    if "dev_ssid" in info:  # dev image: the driver's own AP config, for cross-checking
        ok = info["dev_ssid"] == info.get("ssid")
        print(f"board reports active AP ssid {info['dev_ssid']!r}: {'match' if ok else 'MISMATCH'}")
        if not ok:
            raise SystemExit("WEB-01: decoded SSID does not match the board's AP")
    page = requests.get(u.url(a, "/"), timeout=10).text
    m = re.search(r"WEB-01: <code>(ESP\{[0-9A-F]{12}\})</code>", page)
    s = re.search(r"cipher shard 4/4: ([A-Z]{2})", page)
    print(f"CRY-01 shard 4: {s.group(1) if s else '?'}")
    u.finish("WEB-01", m.group(1) if m else None, a)


main()
