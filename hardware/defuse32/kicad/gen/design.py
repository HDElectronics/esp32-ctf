"""Defuse32 carrier rev 0: single source of truth for parts, nets and placement.

Used by gen_sch.py (schematic) and gen_pcb.py (board). Net names follow
hardware/defuse32/SPEC.md. Pin numbers are symbol pin numbers == footprint pad numbers.
"""

# MCP23017 GPA7/GPB7 are output-only on current silicon. True (as SPEC.md now says):
# U3 GPA7 carries WA6 (an output) and ENC_B moves to GPA5; GPB7 stays a spare.
FIX_U3_GPA7 = True

NC = None          # explicit no-connect flag on that pin
POWER = ("5V", "3V3", "GND", "DK_5V")

R_FP = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
C_FP = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
XH = "Connector_JST:JST_XH_B%dB-XH-A_1x%02d_P2.50mm_Vertical"

PARTS = []

# SPEC.md connector names -> KiCad references. KiCad's annotation check rejects references
# that do not end in a number (J1_A, J_PWR), so the SPEC name goes into the Value field
# and onto the silkscreen. Jn_A -> Jn1, Jn_B -> Jn2.
REFMAP = {"J_PWR": "J7", "J_KEY": "J8", "J_SERVO": "J9", "J_SPARE": "J10"}
for _n in range(1, 7):
    REFMAP["J%d_A" % _n] = "J%d1" % _n
    REFMAP["J%d_B" % _n] = "J%d2" % _n


def part(ref, lib, sym, value, fp, nets, sch, rot=0, unit_pos=None, pcb=None, note=None):
    spec = ref
    if ref in REFMAP:
        ref = REFMAP[ref]
        value = "%s %s" % (spec, value)
    PARTS.append(dict(ref=ref, spec=spec, lib=lib, sym=sym, value=value, fp=fp, nets=nets, sch=sch, rot=rot,
                      unit_pos=unit_pos, pcb=pcb, note=note))


# ------------------------------------------------------------------ power input
part("J_PWR", "Connector", "Screw_Terminal_01x02", "5V in",
     "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
     {"1": "5V", "2": "GND"}, (30.48, 35.56))
part("D1", "Diode", "1N5822", "1N5822", "Diode_THT:D_DO-201AD_P15.24mm_Horizontal",
     {"1": "DK_5V", "2": "5V"}, (55.88, 33.02), rot=180)
part("C1", "Device", "C_Polarized", "470uF/10V", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm",
     {"1": "5V", "2": "GND"}, (86.36, 35.56))
part("C2", "Device", "C_Polarized", "10uF", "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm",
     {"1": "3V3", "2": "GND"}, (101.6, 35.56))
part("C3", "Device", "C", "100nF", C_FP, {"1": "3V3", "2": "GND"}, (22.86, 81.28), note="U2")
part("C4", "Device", "C", "100nF", C_FP, {"1": "3V3", "2": "GND"}, (35.56, 81.28), note="U3")
part("C5", "Device", "C", "100nF", C_FP, {"1": "5V", "2": "GND"}, (48.26, 81.28), note="U4")
for i, (x, y) in enumerate([(71.12, 73.66), (96.52, 73.66), (71.12, 88.9), (96.52, 88.9)]):
    part("H%d" % (i + 1), "Mechanical", "MountingHole", "MountingHole_M3", "MountingHole:MountingHole_3.2mm_M3",
         {}, (x, y))

# ------------------------------------------------------------------ ESP32 DevKitC
U1 = {str(i): NC for i in range(1, 39)}
U1.update({"1": "3V3", "3": "LDR", "4": "MPU_INT", "5": "IR", "6": "MCP_INT", "7": "TM_CLK", "8": "TM_DIO",
           "9": "WS_DATA", "10": "BUZZ", "11": "SERVO_SIG", "12": "T6", "14": "GND", "15": "T4", "19": "DK_5V",
           "20": "GND", "21": "MOSI", "22": "SCL", "25": "SDA", "26": "GND", "27": "MISO", "28": "SCK",
           "29": "CS", "30": "U2TX", "31": "U2RX", "32": "T0", "35": "T3"})
part("U1", "defuse32", "ESP32-DevKitC-32E", "ESP32-DevKitC-32E", "defuse32:ESP32-DevKitC_Socket",
     U1, (180.34, 53.34))

# ------------------------------------------------------------------ pull-ups, IMU
part("R2", "Device", "R", "4.7k", R_FP, {"1": "3V3", "2": "SDA"}, (248.92, 40.64), note="I2C SDA pull-up")
part("R3", "Device", "R", "4.7k", R_FP, {"1": "3V3", "2": "SCL"}, (259.08, 40.64), note="I2C SCL pull-up")
part("R4", "Device", "R", "10k", R_FP, {"1": "3V3", "2": "MCP_INT"}, (269.24, 40.64), note="GPIO35 pull-up")
part("R5", "Device", "R", "10k", R_FP, {"1": "3V3", "2": "IR"}, (279.4, 40.64), note="GPIO34 pull-up")
part("R6", "Device", "R", "10k", R_FP, {"1": "LDR", "2": "GND"}, (289.56, 40.64), note="LDR divider")
part("A1", "defuse32", "GY-521", "GY-521 (MPU-6050)", "defuse32:GY-521_Socket",
     {"1": "3V3", "2": "GND", "3": "SCL", "4": "SDA", "5": NC, "6": NC, "7": "GND", "8": "MPU_INT"},
     (317.5, 50.8))

# ------------------------------------------------------------------ WS2812 buffer
part("U4", "74xx", "74AHCT125", "74AHCT125", "Package_DIP:DIP-14_W7.62mm",
     {"1": "GND", "2": "WS_DATA", "3": "WS_5V",
      "4": "5V", "5": "GND", "6": NC,
      "10": "5V", "9": "GND", "8": NC,
      "13": "5V", "12": "GND", "11": NC,
      "14": "5V", "7": "GND"},
     None, unit_pos={1: (360.68, 30.48), 2: (360.68, 55.88), 3: (360.68, 81.28), 4: (386.08, 55.88),
                     5: (396.24, 81.28)})
part("R1", "Device", "R", "330", R_FP, {"1": "WS_5V", "2": "LDI"}, (398.78, 30.48), note="WS2812 data series R")

# ------------------------------------------------------------------ expanders
U2 = {"9": "3V3", "10": "GND", "12": "SCL", "13": "SDA", "15": "GND", "16": "GND", "17": "GND",
      "18": "3V3", "19": "MCP_INT", "20": "MCP_INT",
      "21": "ROW1", "22": "ROW2", "23": "ROW3", "24": "ROW4",
      "25": "COL1", "26": "COL2", "27": "COL3", "28": "COL4",
      "1": "SIM1", "2": "SIM2", "3": "SIM3", "4": "SIM4", "5": "KEY",
      "6": "SPARE1", "7": "SPARE2", "8": "SPARE3"}
U3 = {"9": "3V3", "10": "GND", "12": "SCL", "13": "SDA", "15": "3V3", "16": "GND", "17": "GND",
      "18": "3V3", "19": "MCP_INT", "20": "MCP_INT",
      "21": "WA1", "22": "WA2", "23": "WA3", "24": "WA4", "25": "WA5", "26": "WA6",
      "27": "ENC_A", "28": "ENC_B",
      "1": "WB1", "2": "WB2", "3": "WB3", "4": "WB4", "5": "WB5", "6": "WB6",
      "7": "ENC_SW", "8": NC}
if FIX_U3_GPA7:
    U3["26"], U3["28"] = "ENC_B", "WA6"
part("U2", "Interface_Expansion", "MCP23017x-x-SP", "MCP23017-E/SP (0x20)", "Package_DIP:DIP-28_W7.62mm",
     U2, (66.04, 158.75))
part("U3", "Interface_Expansion", "MCP23017x-x-SP", "MCP23017-E/SP (0x21)", "Package_DIP:DIP-28_W7.62mm",
     U3, (172.72, 158.75))

# ------------------------------------------------------------------ buzzer
part("R7", "Device", "R", "1k", R_FP, {"1": "BUZZ", "2": "BUZZ_B"}, (254.0, 147.32), note="Q1 base")
part("Q1", "Transistor_BJT", "2N3904", "2N3904", "Package_TO_SOT_THT:TO-92_Inline",
     {"1": "GND", "2": "BUZZ_B", "3": "BUZZ-"}, (279.4, 152.4))
part("D2", "Diode", "1N4148", "1N4148", "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
     {"1": "5V", "2": "BUZZ-"}, (299.72, 144.78), rot=270)

# ------------------------------------------------------------------ carrier headers
part("J_KEY", "Connector_Generic", "Conn_01x02", "KEY", XH % (2, 2), {"1": "KEY", "2": "GND"}, (337.82, 139.7))
part("J_SERVO", "Connector_Generic", "Conn_01x03", "SERVO", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     {"1": "GND", "2": "5V", "3": "SERVO_SIG"}, (365.76, 139.7))
part("J_SPARE", "Connector_Generic", "Conn_01x03", "U2 GPB5-7",
     "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     {"1": "SPARE1", "2": "SPARE2", "3": "SPARE3"}, (391.16, 139.7))

# ------------------------------------------------------------------ plate connectors
PLATE_B = {
    1: ("Radio", ["ENC_A", "ENC_B", "ENC_SW"]),
    2: ("Timer", ["TM_CLK", "TM_DIO", "BUZZ-", "5V"]),
    3: ("Keypad", ["ROW1", "ROW2", "ROW3", "ROW4", "COL1", "COL2", "COL3", "COL4"]),
    4: ("Wires", ["WA%d" % i for i in range(1, 7)] + ["WB%d" % i for i in range(1, 7)]),
    5: ("Probe", ["U2TX", "U2RX", "SCK", "MOSI", "MISO", "CS"]),
    6: ("Sensors", ["T0", "T4", "T6", "T3", "LDR", "IR", "SIM1", "SIM2", "SIM3", "SIM4", "SERVO_SIG"]),
}
PLATE_B_PINNAMES = {2: ["TM_CLK", "TM_DIO", "BUZZ-", "BUZZ+ (5V)"]}
# WS2812 chain: buffer -> R1 -> LDI (M1) -> LDO1 (M1 out = M2 in) ... -> M6 LDO (chain end, NC)
LD_IN = {1: "LDI", 2: "LDO1", 3: "LDO2", 4: "LDO3", 5: "LDO4", 6: "LDO5"}
LD_OUT = {1: "LDO1", 2: "LDO2", 3: "LDO3", 4: "LDO4", 5: "LDO5", 6: NC}
PLATE_SCH = {1: (45.72, 231.14), 2: (137.16, 231.14), 3: (228.6, 231.14),
             4: (45.72, 264.16), 5: (137.16, 264.16), 6: (228.6, 264.16)}
for n in range(1, 7):
    name, pins = PLATE_B[n]
    x, y = PLATE_SCH[n]
    part("J%d_A" % n, "Connector_Generic", "Conn_01x07", "M%d %s common" % (n, name), XH % (7, 7),
         {"1": "5V", "2": "3V3", "3": "GND", "4": "SDA", "5": "SCL", "6": LD_IN[n], "7": LD_OUT[n]}, (x, y))
    k = len(pins)
    part("J%d_B" % n, "Connector_Generic", "Conn_01x%02d" % k, "M%d %s" % (n, name), XH % (k, k),
         {str(i + 1): p for i, p in enumerate(pins)}, (x + 45.72, y))


# ------------------------------------------------------------------ PCB placement
# (x, y, rotation) in board coordinates: origin = board top-left corner, x right, y down (mm).
# Back edge (y=0) = toward the lid hinge = plates M1-M3; front edge (y=140) = M4-M6.
PCB = {
    "J1_A": (14, 7.5, 0), "J1_B": (36.5, 7.5, 0),
    "J2_A": (72, 7.5, 0), "J2_B": (94.5, 7.5, 0),
    "J3_A": (126, 7.5, 0), "J3_B": (148.5, 7.5, 0),
    "J4_A": (14, 133, 0), "J4_B": (36.5, 133, 0),
    "J5_A": (78, 133, 0), "J5_B": (100.5, 133, 0),
    "J6_A": (120, 133, 0), "J6_B": (142.5, 133, 0),
    "U1": (130, 88, 0),
    "J_PWR": (182, 110, 90),
    "D1": (150, 112, 0),
    "C1": (172, 28, 0),
    "J_SERVO": (185, 40, 0),
    "C2": (136, 96, 0),
    "J_KEY": (180, 122, 0),
    "U4": (16, 22, 0),
    "C5": (28, 22, 90),
    "R1": (12, 42, 0),
    "U3": (40, 40, 0),
    "C4": (52, 40, 90),
    "U2": (76, 40, 0),
    "C3": (88, 40, 90),
    "J_SPARE": (92, 52, 0),
    "R2": (52, 82, 0), "R3": (52, 87.08, 0),
    "R4": (70, 82, 0), "R5": (70, 87.08, 0), "R6": (70, 92.16, 0),
    "A1": (14, 62, 0),
    "Q1": (114, 22, 0), "R7": (100, 26, 0), "D2": (110, 30, 0),
    "H1": (5, 5, 0), "H2": (185, 5, 0), "H3": (5, 135, 0), "H4": (185, 135, 0),
}
for p in PARTS:
    p["pcb"] = PCB.get(p["spec"])

BOARD_W, BOARD_H = 190.0, 140.0
# Antenna keepout (board coords): under and beyond the DevKit antenna overhang (left of U1)
KEEPOUT = (104.0, 58.0, 129.0, 92.0)
