#!/usr/bin/env python3
"""BTC-03 Device class clue: rebuild the flag body from what an inquiry shows.

name suffix (6 hex) + Class of Device minor field (1 hex digit) + EIR
manufacturer data (company 0xFFFF, 3 bytes = 6 hex digits whose leading
digit is a 0 placeholder for the CoD digit).
"""
import _util as u


def main():
    addr, p = u.inquiry()  # BR/EDR only, fresh device object
    name, cod = p["Name"], p["Class"]
    mfr = {k: bytes(v.value) for k, v in p.get("ManufacturerData", {}).items()}
    print(f"[{addr}] name {name!r}, class 0x{cod:06x}, manufacturer data "
          + ", ".join(f"0x{k:04x}: {v.hex()}" for k, v in mfr.items()))
    u.forget(addr)

    head = name.split(":", 1)[1]
    minor = (cod >> 2) & 0x3F
    major = (cod >> 8) & 0x1F
    tail = mfr[0xFFFF].hex().upper()
    print(f"name suffix {head}, CoD major 0x{major:02x} minor 0x{minor:02x}, mfr {tail}")
    assert len(head) == 6 and minor < 16 and len(tail) == 6 and tail[0] == "0"
    body = head + f"{minor:X}" + tail[1:]
    u.finish("BTC-03", f"ESP{{{body}}}")


main()
