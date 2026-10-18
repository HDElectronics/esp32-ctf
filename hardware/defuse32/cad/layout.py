"""Defuse32 rev 0 plate layouts (plate-local coordinates).

Plate-local frame: origin = plate centre, +x right, +y toward the lid hinge
(back), top view, mm. Every module item is placed by `at` = where its
`anchor` (module coords, default = PCB centre) lands. Module data comes from
data/parts.json; parts not in parts.json are in EXTRA below (assumed values,
measure before cutting).

Rules checked by build.py: everything hanging below the plate stays inside
the panel opening footprint (OPENING, centred) and within 40 mm below the
plate; nothing more than 35 mm above the plate top; >= 3 mm web between
through-cuts and to the plate edge.
"""

PLATE = dict(w=134.0, h=138.0, t=3.0, corner_r=0.0, screw_d=3.4, screw_inset=6.0)
OPENING = dict(w=114.0, h=118.0)            # panel opening under each plate, centred
GRID = dict(col_x=(-138.0, 0.0, 138.0), row_y=(71.0, -71.0))
STATUS_LED_AT = (49.0, 52.0)                # top-right corner of every plate
TITLE_AT = (-52.0, 55.0)                    # bottom-left of the engraved title
TITLE_CAP = 5.5                             # cap height of the title, mm
ENGRAVE_DEPTH = 1.0
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
         "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"]

# Parts that are not in parts.json (status: assumption).
EXTRA = {
    "probe_perfboard": dict(name="70 x 90 mm FR-4 perfboard (probe plate carrier)", w=70.0, h=90.0, t=1.6,
                            hole_d=3.0, holes=[(2.5, 2.5), (67.5, 2.5), (2.5, 87.5), (67.5, 87.5)],
                            status="assumption: common 7 x 9 cm protoboard, corner holes dia 3 at 2.5 mm"),
    "simon_board": dict(name="50 x 50 mm perfboard for the 2 x 2 Simon buttons", w=50.0, h=50.0, t=1.6,
                        hole_d=3.0, holes=[(3.0, 3.0), (47.0, 3.0), (3.0, 47.0), (47.0, 47.0)],
                        status="assumption: cut from protoboard, 4 x dia 3 holes 3 mm from the corners"),
}

# Defaults for options that are proposals, not data.
OPT = dict(
    tact_cap_hole_d=12.5,     # round A24-type cap dia ~11.6 + clearance; depends on the cap bought
    tact_cap_proud=3.0,       # cap top above the plate top
    test_point_hole_d=5.0,    # test-point loop clearance hole
    header_slot_clear=0.3,    # per side around 2.54 mm header plastic
    window_margin_oled=0.5,   # OLED window = active area + this per side
)

M = "module"


def _plates():
    P = {}
    # ---------------------------------------------------------------- M1 Radio
    P["M1"] = dict(title="M1 RADIO", items=[
        dict(kind=M, key="ssd1306_096", id="OLED", at=(-20.0, 22.0),
             opt=dict(window_margin=OPT["window_margin_oled"], window_extra_bottom=1.5)),
        dict(kind="ws2812", id="LinkLED1", at=(10.0, 22.0)),
        dict(kind="ws2812", id="LinkLED2", at=(24.0, 22.0)),
        dict(kind=M, key="ky040", id="Encoder", at=(0.0, -25.0), anchor="shaft"),
    ])
    # ---------------------------------------------------------------- M2 Timer
    P["M2"] = dict(title="M2 TIMER", items=[
        dict(kind=M, key="tm1637_056", id="TM1637", at=(0.0, 18.0)),
        dict(kind="ws2812", id="Strike1", at=(-20.0, -12.0)),
        dict(kind="ws2812", id="Strike2", at=(0.0, -12.0)),
        dict(kind="ws2812", id="Strike3", at=(20.0, -12.0)),
        dict(kind=M, key="buzzer_12mm", id="Buzzer", at=(0.0, -38.0), anchor="origin_centre"),
    ])
    # --------------------------------------------------------------- M3 Keypad
    P["M3"] = dict(title="M3 KEYPAD", items=[
        dict(kind=M, key="sh1106_13", id="OLED", at=(0.0, 18.0 + 33.7 / 2.0),
             opt=dict(window_margin=OPT["window_margin_oled"])),
        # ON TOP of the plate (SPEC M3): 61 mm holes are too close to the 60 mm key field to mount from
        # below. Frame on 4 spacers, M3 screws through the plate, cable slot under the tail header only.
        dict(kind=M, key="keypad_4x4_hard", id="Keypad", at=(0.0, -20.2),
             opt=dict(spacer_h=3.0, slot_h=6.0)),
    ])
    # ---------------------------------------------------------------- M4 Wires
    posts = []
    for row, (y, colour, tag) in enumerate([(18.0, "post_red", "A"), (-22.0, "post_black", "B")]):
        for i in range(6):
            posts.append(dict(kind=M, key="banana_post_4mm", id="Post%s%d" % (tag, i + 1),
                              at=((i - 2.5) * 19.05, y), anchor="origin_centre", opt=dict(colour=colour)))
    P["M4"] = dict(title="M4 WIRES", items=posts)
    # ---------------------------------------------------------------- M5 Probe
    P["M5"] = dict(title="M5 PROBE", items=[
        dict(kind="probe", id="Probe", at=(0.0, -5.0),
             headers={"SPI": (-16.0, 30.0, 6), "I2C": (16.0, 30.0, 4), "UART": (0.0, -14.0, 4)},
             soic=(-16.0, 8.0), dip=(16.0, 8.0),
             test_points=[(-24.0, -34.0), (-8.0, -34.0), (8.0, -34.0), (24.0, -34.0)]),
    ])
    # -------------------------------------------------------------- M6 Sensors
    P["M6"] = dict(title="M6 SENSORS", items=[
        dict(kind="touchpad", id="TouchT0", at=(-40.0, 40.0)),
        dict(kind="touchpad", id="TouchT4", at=(-18.0, 40.0)),
        dict(kind="touchpad", id="TouchT6", at=(-40.0, 18.0)),
        dict(kind="touchpad", id="TouchT3", at=(-18.0, 18.0)),
        dict(kind=M, key="gl5528", id="LDR", at=(0.0, 30.0), anchor="origin_centre"),
        dict(kind=M, key="vs1838b", id="IR", at=(0.0, 12.0)),
        dict(kind=M, key="pn532_v3", id="PN532", at=(30.0, 22.0)),
        dict(kind="simon", id="Simon", at=(-29.0, -33.0)),
        dict(kind="servo", id="Servo", shaft_x=30.0, y_flange=-30.0),
    ])
    return P


PLATES = _plates()
ORDER = ["M1", "M2", "M3", "M4", "M5", "M6"]


def plate_centre(pid):
    i = ORDER.index(pid)
    return GRID["col_x"][i % 3], GRID["row_y"][i // 3]
