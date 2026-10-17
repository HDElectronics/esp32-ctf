#!/usr/bin/env python3
"""WEB-07 WebSocket chatter: /ws sends a noise text frame every second and the
flag in a binary frame every 30 s. Opens two clients at once (the board must
serve both) and waits up to 40 s for the binary frame on each."""
import threading
import time

from websockets.sync.client import connect

import _util as u


def listen(uri, name, results):
    text = 0
    deadline = time.monotonic() + 40
    with connect(uri, open_timeout=10) as ws:
        while time.monotonic() < deadline:
            try:
                msg = ws.recv(timeout=max(0.1, deadline - time.monotonic()))
            except TimeoutError:
                break
            if isinstance(msg, bytes):
                print(f"[{name}] binary frame after {text} text frames: {msg!r}")
                results[name] = msg.decode(errors="replace")
                return
            text += 1
            if text <= 2:
                print(f"[{name}] text: {msg}")


def main():
    a = u.args(__doc__)
    uri = f"ws://{a.host}/ws"
    results = {}
    threads = [threading.Thread(target=listen, args=(uri, n, results)) for n in ("c1", "c2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if len(results) != 2:
        raise SystemExit(f"WEB-07: only {sorted(results)} got the binary frame")
    m = u.FLAG_RE.search(results["c1"])
    u.finish("WEB-07", m.group(0) if m else None, a)


main()
