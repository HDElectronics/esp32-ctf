#!/usr/bin/env python3
"""WEB-04 Header check: /api/docs names the client (User-Agent) and shows the
board key; /api/secret wants both headers."""
import re

import requests

import _util as u


def main():
    a = u.args(__doc__)
    docs = requests.get(u.url(a, "/api/docs"), timeout=10).text
    key = re.search(r"Board key: <code>([0-9a-f]{16})</code>", docs).group(1)
    agent = re.search(r"identify itself as <code>([^<]+)</code>", docs).group(1)
    print(f"agent {agent!r}, key {key}")
    r = requests.get(u.url(a, "/api/secret"), timeout=10)
    print(f"without headers: HTTP {r.status_code} {r.text.strip()!r}")
    r = requests.get(u.url(a, "/api/secret"), headers={"User-Agent": agent, "X-CTF-Key": key},
                     timeout=10)
    print(f"with headers: HTTP {r.status_code} {r.text.strip()}")
    m = u.FLAG_RE.search(r.text)
    u.finish("WEB-04", m.group(0) if m else None, a)


main()
