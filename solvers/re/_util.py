"""Shared helpers for the RE track solvers.

Run from the ESP-IDF Python environment (`. ~/esp/esp-idf/export.sh`), which
provides esptool, pyserial and nvs_tool.py.

    python solvers/re/re01_strings.py [--port /dev/ttyACM0] [--image flash.bin]

--image reads partitions from an existing full-flash dump
(`esptool read-flash 0 0x400000 flash.bin`) instead of the board. The board is
still needed to submit the flag.
"""
import argparse
import atexit
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

import serial

DEFAULT_PORT = os.environ.get("CTF_PORT", "/dev/ttyACM0")
PART_TABLE_OFFSET = 0x8000
PART_TABLE_SIZE = 0xC00
FLAG_RE = re.compile(rb"ESP\{[0-9A-Fa-f]{12}\}")


def parse_args(description, extra=None):
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--port", default=DEFAULT_PORT, help="serial port of the board")
    ap.add_argument("--baud", type=int, default=921600, help="esptool read-flash baud rate")
    ap.add_argument("--image", help="use this full-flash dump instead of reading the board")
    ap.add_argument("--out", help="keep partition dumps in this directory (default: temp, removed)")
    if extra:
        extra(ap)
    return ap.parse_args()


class Flash:
    """Reads flash regions from the board (esptool read-flash) or a dump file."""

    def __init__(self, args):
        self.args = args
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            self.tmp = args.out
        else:
            self.tmp = tempfile.mkdtemp(prefix="ctf-re-")
            atexit.register(shutil.rmtree, self.tmp, True)

    def read(self, offset, size):
        if self.args.image:
            with open(self.args.image, "rb") as f:
                f.seek(offset)
                return f.read(size)
        out = os.path.join(self.tmp, "dump_%x_%x.bin" % (offset, size))
        cmd = [sys.executable, "-m", "esptool", "--chip", "esp32", "-p", self.args.port,
               "-b", str(self.args.baud), "read-flash", hex(offset), hex(size), out]
        print("$ esptool " + " ".join(cmd[3:]), flush=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        with open(out, "rb") as f:
            return f.read()

    def partitions(self):
        """Parse the partition table at 0x8000: {label: (type, subtype, offset, size)}."""
        raw = self.read(PART_TABLE_OFFSET, PART_TABLE_SIZE)
        parts = {}
        for i in range(0, len(raw), 32):
            ent = raw[i:i + 32]
            magic = struct.unpack_from("<H", ent)[0]
            if magic != 0x50AA:  # 0xEBEB = MD5 entry, 0xFFFF = end of table
                break
            ptype, subtype, off, size = struct.unpack_from("<BBII", ent, 2)
            label = ent[12:28].split(b"\0")[0].decode()
            parts[label] = (ptype, subtype, off, size)
        return parts

    def partition(self, label):
        parts = self.partitions()
        if label not in parts:
            sys.exit("partition %r not in table: %s" % (label, sorted(parts)))
        _, _, off, size = parts[label]
        print("partition %-8s offset 0x%06x size 0x%06x" % (label, off, size))
        return self.read(off, size)

    def partition_file(self, label):
        """Dump a partition to a file and return its path (for external tools)."""
        data = self.partition(label)
        path = os.path.join(self.tmp, label + ".bin")
        with open(path, "wb") as f:
            f.write(data)
        return path


def nvs_entries(nvs_bin):
    """Parse an NVS dump with ESP-IDF's nvs_tool.py (IDF 6.1:
    components/nvs_flash/nvs_partition_tool/nvs_tool.py -f json -d minimal).
    Returns {(namespace, key): value}; blobs come back as bytes."""
    import base64
    import json

    idf = os.environ.get("IDF_PATH", os.path.expanduser("~/esp/esp-idf"))
    tool = os.path.join(idf, "components", "nvs_flash", "nvs_partition_tool", "nvs_tool.py")
    cmd = [sys.executable, tool, "-f", "json", "-d", "minimal", nvs_bin]
    print("$ python " + " ".join(cmd[1:]), flush=True)
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    out = {}
    for ent in json.loads(res.stdout):
        val = ent["data"]
        if ent["encoding"] in ("blob_data", "blob"):
            val = base64.b64decode(val)
        out[(ent["namespace"], ent["key"])] = val
    return out


class Board:
    """Minimal console client: resets the board, waits for the prompt, runs commands."""

    def __init__(self, port):
        self.s = serial.Serial(port, 115200, timeout=0.1)
        self.boot_log = ""

    def reset(self, timeout=20):
        self.s.dtr = False
        self.s.rts = True
        time.sleep(0.1)
        self.s.rts = False
        self.boot_log = self.read_until(r"ctf> ", timeout)
        if "ctf> " not in self.boot_log:
            sys.exit("no console prompt after reset")
        time.sleep(0.5)
        self.boot_log += self.drain()
        return self.boot_log

    def drain(self):
        buf = b""
        while True:
            chunk = self.s.read(4096)
            if not chunk:
                return buf.decode(errors="replace")
            buf += chunk

    def read_until(self, pattern, timeout):
        buf = ""
        end = time.time() + timeout
        while time.time() < end:
            buf += self.s.read(4096).decode(errors="replace")
            if re.search(pattern, buf):
                break
        return buf

    def cmd(self, line, timeout=5):
        self.s.reset_input_buffer()
        self.s.write((line + "\r").encode())
        out = self.read_until(r"ctf> $", timeout)
        print(">>> " + line + "\n" + re.sub(r"ctf> $", "", out).strip())
        return out

    def mac(self):
        m = re.search(r"board MAC: ([0-9A-Fa-f:]{17})", self.boot_log)
        if not m:
            sys.exit("board MAC not found in banner")
        return bytes.fromhex(m.group(1).replace(":", ""))

    def submit(self, cid, flag):
        out = self.cmd("submit " + flag)
        ok = re.search(r"(Correct! %s|Already solved: %s)" % (cid, cid), out)
        print("%s: %s %s" % (cid, flag, "OK" if ok else "FAILED"))
        return bool(ok)


def find_flag(data):
    m = FLAG_RE.search(data)
    return m.group(0).decode() if m else None
