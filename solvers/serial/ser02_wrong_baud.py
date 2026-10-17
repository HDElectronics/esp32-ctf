#!/usr/bin/env python3
"""SER-02 Wrong baud: read the second UART at a non-standard speed.

Kit: a 3.3 V USB-UART adapter. Wire adapter RX -> board GPIO17 (UART2 TX) and
GND -> GND. The board sends a line every 5 s at 28800 8N1; at any other baud
you only see garbage. This script scans common and odd rates and stops at the
one that yields a flag, then submits it on the board console.

usage: ser02_wrong_baud.py <adapter_port> [console_port]
       e.g. ser02_wrong_baud.py /dev/ttyUSB0 /dev/ttyACM0

Note: the reference setup has no USB-UART adapter, so this solver was checked
against the firmware source only, not on the wire.
"""
import sys

import serial

from _util import FLAG_RE, open_console, submit, sync

RATES = [9600, 14400, 19200, 28800, 38400, 57600, 74880, 115200, 230400]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    adapter = sys.argv[1]
    console = sys.argv[2] if len(sys.argv) > 2 else "/dev/ttyACM0"
    flag = None
    for baud in RATES:
        with serial.Serial(adapter, baud, timeout=6.5) as a:
            a.reset_input_buffer()
            data = a.read(200)  # one period is 5 s; the line is ~45 bytes
        text = data.decode(errors="replace")
        m = FLAG_RE.search(text)
        print("%6d baud: %r" % (baud, text[:60]))
        if m:
            flag = m.group(0)
            print("flag at %d baud: %s" % (baud, flag))
            break
    if not flag:
        print("no flag found; check wiring (RX to GPIO17, shared GND)")
        return 1
    s = open_console(console)
    sync(s)
    return submit(s, flag)


if __name__ == "__main__":
    sys.exit(main())
