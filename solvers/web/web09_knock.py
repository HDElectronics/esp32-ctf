#!/usr/bin/env python3
"""WEB-09 UDP knock: the `wifi` console clue gives three hex UDP ports and the
door (0x7a69 = 31337/tcp). Knock in order (each within 5 s), then connect to
the door within 30 s and read the flag. Checks the door is shut beforehand."""
import socket
import time

import _util as u


def try_door(host, port):
    try:
        with socket.create_connection((host, port), timeout=5) as c:
            c.settimeout(5)
            data = b""
            while True:
                chunk = c.recv(256)
                if not chunk:
                    return data.decode(errors="replace")
                data += chunk
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        return e


def main():
    a = u.args(__doc__)
    info = u.wifi_info(a.serial)
    ports, door = info["knock"], info["door"]
    print(f"knock ports {ports}, door {door}")
    before = try_door(a.host, door)
    print(f"door before knocking: {before!r}")
    if isinstance(before, str) and u.FLAG_RE.search(before):
        print("(door was still open from an earlier knock)")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for p in ports:
            s.sendto(b"knock", (a.host, p))
            time.sleep(0.5)
    time.sleep(0.5)
    text = try_door(a.host, door)
    print(f"door after knocking: {text!r}")
    m = u.FLAG_RE.search(text) if isinstance(text, str) else None
    u.finish("WEB-09", m.group(0) if m else None, a)


main()
