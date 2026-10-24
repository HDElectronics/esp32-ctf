#!/usr/bin/env python3
"""Renders and 2D plots of the carrier into hardware/defuse32/renders/ (kicad-cli + inkscape).

  /usr/bin/python3 kicad/gen/renders.py

  carrier-top.png, carrier-iso.png, carrier-bottom.png    3D renders (kicad-cli pcb render, high quality)
  carrier-f-cu.png       F.Cu + F.Silkscreen + outline       (2D, 300 dpi)
  carrier-in1-cu.png     In1.Cu, GND plane                   (2D)
  carrier-in2-cu.png     In2.Cu, GND plane                   (2D)
  carrier-b-cu.png       B.Cu + outline, seen from the top   (2D)
  carrier-silk.png       F.Silkscreen + F.Mask + F.Fab + outline (2D)

The 3D renders need the models in kicad/3d/ (gen/fetch_3d.py); without them J7, SW1, SW2 and F1
render without a body. Only writes renders/carrier-*.png (cad/build.py owns renders/cad_*.png).
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.normpath(os.path.join(KDIR, "..", "renders"))
BOARD = os.path.join(KDIR, "defuse32-carrier.kicad_pcb")

RENDERS = [
    ("carrier-top.png", ["--side", "top", "-w", "1568", "-h", "1176"]),
    ("carrier-iso.png", ["--perspective", "--rotate", "-50,0,-35", "--zoom", "0.9", "-w", "1568", "-h", "1064"]),
    ("carrier-bottom.png", ["--side", "bottom", "-w", "1568", "-h", "1176"]),
]
PLOTS = [
    ("carrier-f-cu.png", "F.Cu,F.Silkscreen,Edge.Cuts"),
    ("carrier-in1-cu.png", "In1.Cu,Edge.Cuts"),
    ("carrier-in2-cu.png", "In2.Cu,Edge.Cuts"),
    ("carrier-b-cu.png", "B.Cu,Edge.Cuts"),
    ("carrier-silk.png", "F.Silkscreen,F.Mask,F.Fab,Edge.Cuts"),
]


def run(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, opts in RENDERS:
        run(["kicad-cli", "pcb", "render", "--quality", "high", "--background", "opaque"] + opts +
            ["-o", os.path.join(OUT, name), BOARD])
        print("wrote", name)
    tmp = tempfile.mkdtemp(prefix="d32-plot-")
    for name, layers in PLOTS:
        svg = os.path.join(tmp, name[:-4] + ".svg")
        run(["kicad-cli", "pcb", "export", "svg", "--layers", layers, "--mode-single", "--fit-page-to-board",
             "--exclude-drawing-sheet", "-o", svg, BOARD])
        run(["inkscape", svg, "--export-type=png", "--export-dpi=300", "--export-background=white",
             "-o", os.path.join(OUT, name)])
        os.remove(svg)
        print("wrote", name)
    os.rmdir(tmp)


if __name__ == "__main__":
    sys.exit(main())
