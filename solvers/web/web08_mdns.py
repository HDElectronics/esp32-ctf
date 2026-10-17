#!/usr/bin/env python3
"""WEB-08 mDNS discovery: browse _ctf._tcp.local., read the SRV port + TXT,
then GET / on that port (`avahi-browse -rt _ctf._tcp` does the same)."""
import socket
import time

import requests
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

import _util as u

SERVICE = "_ctf._tcp.local."


class Collect(ServiceListener):
    def __init__(self):
        self.names = []

    def add_service(self, zc, type_, name):
        self.names.append(name)

    def update_service(self, zc, type_, name):
        pass

    def remove_service(self, zc, type_, name):
        pass


def main():
    a = u.args(__doc__)
    zc = Zeroconf()
    try:
        col = Collect()
        ServiceBrowser(zc, SERVICE, col)
        end = time.monotonic() + 15
        while not col.names and time.monotonic() < end:
            time.sleep(0.2)
        if not col.names:
            raise SystemExit("WEB-08: no _ctf._tcp service found")
        info = zc.get_service_info(SERVICE, col.names[0], timeout=5000)
    finally:
        zc.close()
    addrs = [socket.inet_ntoa(x) for x in info.addresses]
    txt = {k.decode(): (v or b"").decode() for k, v in info.properties.items()}
    print(f"service {info.name}: host {info.server} addrs {addrs} port {info.port} txt {txt}")
    host = a.host if a.host in addrs else addrs[0]
    r = requests.get(f"http://{host}:{info.port}{txt.get('path', '/')}", timeout=10)
    print(r.text.strip())
    m = u.FLAG_RE.search(r.text)
    u.finish("WEB-08", m.group(0) if m else None, a)


main()
