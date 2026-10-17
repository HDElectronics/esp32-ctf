#!/usr/bin/env python3
"""WEB-02 View source: part 1 (first 6 hex) sits in an HTML comment on /,
part 2 (last 6 hex) behind the path that /robots.txt disallows."""
import re

import requests

import _util as u


def main():
    a = u.args(__doc__, default_via="web")
    page = requests.get(u.url(a, "/"), timeout=10).text
    p1 = re.search(r"<!--.*?part 1/2 = ([0-9A-F]{6})", page, re.S)
    robots = requests.get(u.url(a, "/robots.txt"), timeout=10).text
    print(robots.strip())
    path = re.search(r"Disallow: (\S+)", robots).group(1)
    hidden = requests.get(u.url(a, path), timeout=10).text
    print(hidden.strip())
    p2 = re.search(r"part 2/2 = ([0-9A-F]{6})", hidden)
    flag = f"ESP{{{p1.group(1)}{p2.group(1)}}}" if p1 and p2 else None
    u.finish("WEB-02", flag, a)


main()
