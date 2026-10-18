#!/usr/bin/env python3
"""Build docs/img/src/i2c.html (README HW-04 waveform) from a real sigrok capture.

    python3 docs/img/src/make_i2c.py CAPTURE.sr      # SCL = D1, SDA = D2, 1 MHz
    scripts/render-images.sh i2c

Draws the first I2C frame only up to the end of the 4th data byte ('{'): the
START, the address byte and 'E' 'S' 'P' '{', each with its NACK. The waveform is
cut at the SCL falling edge that ends that NACK, before SDA starts the next
byte, so nothing past '{' ever reaches the HTML. The capture itself is not in
the repo (it holds a board's full flag).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "i2c.html")
EXPECT = [0x45, 0x53, 0x50, 0x7B]  # E S P {

# layout (CSS px)
W, H = 1200, 360
X0, X1 = 118, 990           # plot area
PRE = 34                     # idle samples shown before START
SCL_Y, SDA_Y = (110, 142), (186, 218)   # (high, low)
ANN_Y, ANN_H = 252, 26


def decode(cap):
    out = subprocess.run(
        ["sigrok-cli", "-i", cap, "-P", "i2c:scl=D1:sda=D2", "--protocol-decoder-samplenum",
         "-A", "i2c=start:stop:ack:nack:address-write:data-write"],
        check=True, capture_output=True, text=True).stdout
    anns = []
    for line in out.splitlines():
        m = re.match(r"(\d+)-(\d+) i2c-1: (.+)$", line)
        if m:
            anns.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    anns.sort(key=lambda a: a[0])
    # first frame: from the first Start to the following Stop
    i0 = next(i for i, a in enumerate(anns) if a[2] == "Start")
    frame = []
    for a in anns[i0:]:
        frame.append(a)
        if a[2] == "Stop":
            break
    return frame


def samples(cap, s0, s1):
    """SCL/SDA for sample numbers s0..s1-1 (sigrok CSV, one row per sample)."""
    p = subprocess.Popen(["sigrok-cli", "-i", cap, "-C", "D1,D2", "-O", "csv"],
                         stdout=subprocess.PIPE, text=True)
    scl, sda, n = [], [], 0
    for line in p.stdout:
        if line.startswith(";") or line.startswith("logic"):
            continue
        if n >= s0:
            a, b = line.strip().split(",")
            scl.append(int(a))
            sda.append(int(b))
        n += 1
        if n >= s1:
            break
    p.kill()
    p.wait()
    return scl, sda


def steps(vals, x_of, hi, lo):
    pts = []
    prev = None
    for i, v in enumerate(vals):
        y = hi if v else lo
        x = x_of(i)
        if prev is None:
            pts.append((x, y))
        elif y != prev:
            pts.append((x, prev))
            pts.append((x, y))
        prev = y
    pts.append((x_of(len(vals)), prev))
    return " ".join("%.1f,%d" % p for p in pts), prev


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    cap = sys.argv[1]
    frame = decode(cap)

    start = next(a for a in frame if a[2] == "Start")
    addr = next(a for a in frame if a[2].startswith("Address write"))
    data = [a for a in frame if a[2].startswith("Data write")]
    vals = [int(a[2].split(":")[1], 16) for a in data[:4]]
    assert vals == EXPECT, "unexpected first bytes"
    more = len(data) - 4

    # the NACK after the 4th data byte, then the SCL falling edge that ends it
    nack4 = next(a for a in frame if a[2] in ("NACK", "ACK") and a[0] > data[3][0])
    s0 = start[0] - PRE
    scl, sda = samples(cap, s0, nack4[1] + 200)
    i = nack4[0] - s0
    while not (scl[i - 1] == 1 and scl[i] == 0):
        i += 1
    cut = i                              # first sample with SCL low again
    scl, sda = scl[:cut] + [0], sda[:cut] + [sda[cut - 1]]
    n = len(scl)
    k = (X1 - X0) / n
    x_of = lambda j: X0 + j * k

    scl_pts, scl_end = steps(scl, x_of, *SCL_Y)
    sda_pts, sda_end = steps(sda, x_of, *SDA_Y)

    # decoder boxes (only annotations inside the cut window)
    boxes = []
    win_end = s0 + cut
    for ss, es, txt in frame:
        if ss >= win_end:
            break
        if txt == "Start":
            ss, es, cls, label = ss, addr[0], "op", "S"
        elif txt.startswith("Address write"):
            cls, label = "byte", "Address write: " + txt.split(":")[1].strip()
        elif txt in ("Write", "Read"):
            cls, label = "op", txt[0]
        elif txt in ("NACK", "ACK"):
            cls, label = "nack", "N" if txt == "NACK" else "A"
        elif txt.startswith("Data write"):
            v = int(txt.split(":")[1], 16)
            cls, label = "byte", "'%s' · 0x%02X" % (chr(v), v)
        else:
            continue
        x = x_of(ss - s0)
        w = max(x_of(es - s0) - x, 10)
        boxes.append('<g class="%s"><rect x="%.1f" y="%d" width="%.1f" height="%d" rx="4"/>'
                     '<text x="%.1f" y="%d">%s</text></g>'
                     % (cls, x + 0.5, ANN_Y, w - 1, ANN_H, x + w / 2, ANN_Y + 17, label))

    # time ruler every 100 us (1 MHz -> 1 sample = 1 us)
    ticks = []
    for us in range(0, n, 100):
        x = x_of(us)
        ticks.append('<path d="M%.1f 74 V82"/>' % x)
        ticks.append('<text x="%.1f" y="68">%s</text>' % (x, "%d µs" % us if us else "0"))

    dash_scl = SCL_Y[0] if scl_end == SCL_Y[0] else SCL_Y[1]
    html = TEMPLATE.format(
        W=W, H=H, X0=X0, X1=X1, scl=scl_pts, sda=sda_pts,
        scl_hi=SCL_Y[0], scl_lo=SCL_Y[1], sda_hi=SDA_Y[0], sda_lo=SDA_Y[1],
        scl_end=dash_scl, sda_end=sda_end, xd=X1 + 32, xt=X1 + 28,
        boxes="\n  ".join(boxes), ticks="\n    ".join(ticks),
        ann_y=ANN_Y, ann_t=ANN_Y + 17, more=more, span=n,
        mid_scl=(SCL_Y[0] + SCL_Y[1]) // 2 + 5, lane_w=X1 - X0 + 40,
        mid_more=ANN_Y + 17, lane1=SCL_Y[0] - 16, lane2=SDA_Y[0] - 16, mid_sda=(SDA_Y[0] + SDA_Y[1]) // 2 + 5)
    with open(OUT, "w") as f:
        f.write(html)
    print("wrote %s (%d samples, %d boxes, %d more bytes)" % (OUT, n, len(boxes), more))


TEMPLATE = """<!doctype html>
<!-- GENERATED by docs/img/src/make_i2c.py from a real sigrok capture; do not edit.
     README HW-04 waveform: START, address 0x5A W, and the first 4 data bytes only. -->
<html lang="en">
<head>
<meta charset="utf-8">
<title>HW-04 I2C capture</title>
<script>if (/[?&]theme=dark/.test(location.search) || location.hash === "#dark") document.documentElement.dataset.theme = "dark";</script>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Martian+Mono:wdth,wght@75..112.5,400..500&display=block">
<style>
  :root {{
    --bg: #f6f4f8; --surface: #ffffff; --ink: #221b2e; --muted: #6a6178; --line: #ddd6e6;
    --accent: #4b2a7a; --gold: #a87414; --gold-soft: #f4e7c9; --accent-soft: #ece4f6;
  }}
  :root[data-theme="dark"] {{
    --bg: #17121f; --surface: #211a2c; --ink: #ece6f4; --muted: #a79cb8; --line: #3a3048;
    --accent: #b99ae8; --gold: #e2b450; --gold-soft: #3a2f17; --accent-soft: #2e2340;
  }}
  html, body {{ margin: 0; }}
  body {{ width: {W}px; height: {H}px; overflow: hidden; background: var(--bg); }}
  svg {{ display: block; font-family: "Martian Mono", monospace; }}
  .silk {{ font-size: 12px; font-weight: 500; letter-spacing: 0.16em; fill: var(--gold); }}
  .ch {{ font-size: 15px; font-weight: 500; fill: var(--ink); }}
  .pin {{ font-size: 11px; fill: var(--muted); }}
  .ruler path {{ stroke: var(--line); stroke-width: 1; }}
  .ruler text {{ font-size: 10px; fill: var(--muted); text-anchor: middle; }}
  .lane {{ fill: var(--surface); stroke: var(--line); stroke-width: 1; }}
  .scl {{ fill: none; stroke: var(--accent); stroke-width: 1.6; stroke-linejoin: miter; }}
  .sda {{ fill: none; stroke: var(--gold); stroke-width: 1.6; stroke-linejoin: miter; }}
  .dash {{ stroke: var(--muted); stroke-width: 1.6; stroke-dasharray: 2 5; fill: none; }}
  g text {{ font-size: 11px; text-anchor: middle; font-stretch: 80%; font-weight: 500; }}
  .byte rect {{ fill: var(--accent-soft); stroke: var(--accent); }}
  .byte text {{ fill: var(--ink); }}
  .nack rect {{ fill: var(--gold-soft); stroke: var(--gold); }}
  .nack text {{ fill: var(--gold); }}
  .op rect {{ fill: var(--surface); stroke: var(--muted); }}
  .op text {{ fill: var(--muted); }}
  .more {{ font-size: 13px; fill: var(--muted); }}
  .legend {{ font-size: 11px; fill: var(--muted); }}
</style>
</head>
<body>
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <text class="silk" x="40" y="34">HW-04 · CAPTURED ON A $10 FX2 LOGIC ANALYZER WITH SIGROK</text>
  <g class="ruler">
    {ticks}
  </g>
  <rect class="lane" x="{X0}" y="{lane1}" width="{lane_w}" height="64" rx="4"/>
  <rect class="lane" x="{X0}" y="{lane2}" width="{lane_w}" height="64" rx="4"/>
  <text class="ch" x="40" y="{mid_scl}">SCL</text><text class="pin" x="80" y="{mid_scl}">D1</text>
  <text class="ch" x="40" y="{mid_sda}">SDA</text><text class="pin" x="80" y="{mid_sda}">D2</text>
  <text class="ch" x="40" y="{ann_t}">I2C</text>
  <polyline class="scl" points="{scl}"/>
  <polyline class="sda" points="{sda}"/>
  <path class="dash" d="M{X1} {scl_end} H{xd} M{X1} {sda_end} H{xd}"/>
  <text class="more" x="{xt}" y="{mid_more}">…{more} more bytes</text>
  {boxes}
  <text class="legend" x="{X0}" y="318">S start · W write · N NACK · 1 MHz sample rate · {span} µs shown</text>
</svg>
</body>
</html>
"""

if __name__ == "__main__":
    main()
