"""Defuse32 carrier rev 2: single source of truth for parts, nets, LCSC numbers and placement.

Used by gen_sch.py (schematic, one root sheet + four sub-sheets), gen_pcb.py (board) and
check_netlist.py. Net names follow hardware/defuse32/SPEC.md. Pin numbers are symbol pin
numbers == footprint pad numbers.

Rev 2 (SPEC "Rev 2 carrier (2026-10-23)"): SMD, 100 x 70 mm, ESP32-WROOM-32E soldered at the
left edge, USB-C + CH340C programming port, 2x AMS1117-3.3 (3V3, 3V3P), 2x MCP23017-E/SO,
LIS3DH, push-push microSD, one IDC box header per plate. The ESP32 GPIO map, the MCP23017
allocation (rev 1b), the WS2812 chain and the I2C addresses are unchanged from rev 1b.
"""

NC = None          # explicit no-connect flag on that pin
POWER = ("VBUS", "5V", "3V3", "3V3P", "GND")
# two-pin nets drawn as a direct wire between the two pins (same sheet) instead of labels
DIRECT = ("AR_DTR_B", "AR_RTS_B", "BUZZ_B", "WS_5V", "LIS_SA0")
# power symbol per net (the symbol's Value is the net name)
PWR_SYM = {"VBUS": "VBUS", "5V": "+5V", "3V3": "+3V3", "3V3P": "+3.3VP", "GND": "GND"}

TITLE = "Defuse32 carrier rev 2"
DATE = "2026-10-23"
REV = "2"

R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
IDC = "Connector_IDC:IDC-Header_2x%02d_P2.54mm_Vertical"
PINHDR = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"

# ------------------------------------------------------------------ JLCPCB / LCSC parts
# key -> (LCSC, MPN, manufacturer, JLC tier). Checked 2026-10-23 on the JLCPCB parts API
# (stock > 0, package matches the footprint). "Basic" = no feeder fee at JLCPCB assembly.
LCSC = {
    "R10k": ("C25804", "0603WAF1002T5E", "UNI-ROYAL", "Basic"),
    "R4k7": ("C23162", "0603WAF4701T5E", "UNI-ROYAL", "Basic"),
    "R5k1": ("C23186", "0603WAF5101T5E", "UNI-ROYAL", "Basic"),
    "R1k": ("C21190", "0603WAF1001T5E", "UNI-ROYAL", "Basic"),
    "R330": ("C23138", "0603WAF3300T5E", "UNI-ROYAL", "Basic"),
    "C100n": ("C14663", "CC0603KRX7R9BB104", "YAGEO", "Basic"),
    "C1u": ("C15849", "CL10A105KB8NNNC", "Samsung", "Basic"),
    "C10u": ("C15850", "CL21A106KAYNNNE", "Samsung", "Basic"),
    "C22u": ("C45783", "CL21A226MAQNNNE", "Samsung", "Basic"),
    "C220u": ("C72494", "RVT1A221M0605", "ROQANG", "Extended"),
    "AMS1117": ("C6186", "AMS1117-3.3", "Advanced Monolithic Systems", "Basic"),
    "MMBT3904": ("C20526", "MMBT3904", "Changjiang (CJ)", "Basic"),
    "1N4148WS": ("C2128", "1N4148WS", "Changjiang (CJ)", "Basic"),
    "TS1187A": ("C318884", "TS-1187A-B-A-B", "XKB Connection", "Basic"),
    "PTC2A": ("C18198338", "1812L200/8GR", "LUTE", "Extended"),
    "USBC": ("C165948", "TYPE-C-31-M-12", "Korean Hroparts Elec", "Extended"),
    "USBLC6": ("C7519", "USBLC6-2SC6", "STMicroelectronics", "Extended"),
    "CH340C": ("C84681", "CH340C", "WCH", "Extended"),
    "WROOM32E": ("C701341", "ESP32-WROOM-32E-N4", "Espressif", "Extended"),
    "MCP23017": ("C47023", "MCP23017-E/SO", "Microchip", "Extended"),
    "LIS3DH": ("C15134", "LIS3DHTR", "STMicroelectronics", "Extended"),
    "AHCT1G125": ("C7484", "SN74AHCT1G125DBVR", "Texas Instruments", "Extended"),
    "MICROSD": ("C114218", "DM3AT-SF-PEJM5", "Hirose", "Extended"),
    # through-hole (hand-soldered or JLCPCB THT assembly)
    "IDC10": ("C19193807", "XDFH-0254-2*5P", "Lian Xin", "Extended"),
    "IDC12": ("C18202143", "XDFH-0254-2*6P", "Lian Xin", "Extended"),
    "IDC14": ("C19193808", "XDFH-0254-2*7P", "Lian Xin", "Extended"),
    "IDC16": ("C18202144", "XDFH-0254-2*8P", "Lian Xin", "Extended"),
    "IDC20": ("C18202145", "XDFH-0254-2*10P", "Lian Xin", "Extended"),
    "HDR2": ("C32713268", "HX PZ2.54-1x2P ZZ", "hanxia", "Extended"),
    "HDR3": ("C32713269", "HX PZ2.54-1x3P ZZ", "hanxia", "Extended"),
    "HDR5": ("C32713271", "HX PZ2.54-1x5P ZZ", "hanxia", "Extended"),
}
# Why each Extended SMD part is Extended (no JLCPCB Basic part fits): see README "Parts".

# ------------------------------------------------------------------ sheets
# key -> (sheet name, file, page). Root = page 1 (sheet symbols and notes only).
SHEETS = {
    "power": ("Power, USB, UART", "power_usb.kicad_sch", 2),
    "mcu": ("ESP32 module", "esp32.kicad_sch", 3),
    "io": ("Expanders, tilt, microSD", "io.kicad_sch", 4),
    "conn": ("Plate connectors", "connectors.kicad_sch", 5),
}

PARTS = []

# SPEC connector names -> KiCad references (the SPEC name starts the Value and is on the silkscreen)
REFMAP = {"J_USB": "J7", "J_KEY": "J8", "J_SERVO": "J9", "J_SPARE": "J10", "J_SD": "J11"}


def part(ref, lib, sym, value, fp, nets, sheet, sch, rot=0, lcsc=None, note=None, dnp=False):
    spec = ref
    if ref in REFMAP:
        ref = REFMAP[ref]
        value = "%s %s" % (spec, value)
    PARTS.append(dict(ref=ref, spec=spec, lib=lib, sym=sym, value=value, fp=fp, nets=nets, sheet=sheet,
                      sch=sch, rot=rot, unit_pos=None, lcsc=LCSC[lcsc] if lcsc else None, note=note,
                      pcb=None, dnp=dnp))


def R(ref, value, a, b, sheet, sch, rot=0, note=None):
    key = {"10k": "R10k", "4.7k": "R4k7", "5.1k": "R5k1", "1k": "R1k", "330": "R330"}[value]
    part(ref, "Device", "R", value, R0603, {"1": a, "2": b}, sheet, sch, rot, key, note)


def C(ref, value, a, b, sheet, sch, rot=0, note=None):
    key = {"100nF": "C100n", "1uF": "C1u", "10uF": "C10u", "22uF": "C22u"}[value]
    fp = C0805 if value in ("10uF", "22uF") else C0603
    part(ref, "Device", "C", value, fp, {"1": a, "2": b}, sheet, sch, rot, key, note)


# ================================================================== sheet "power": USB-C, regulators, CH340C
# USB-C receptacle (16P). VBUS/GND pins are stacked in the symbol (hidden duplicates share the stub).
part("J_USB", "Connector", "USB_C_Receptacle_USB2.0_16P", "USB-C",
     "defuse32:USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge",     # official footprint, edge-mount silkscreen
     {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND",
      "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
      "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM",
      "A8": NC, "B8": NC, "SH": "GND"},
     "power", (45.72, 73.66), lcsc="USBC")
R("R14", "5.1k", "CC1", "GND", "power", (91.44, 60.96), note="CC1 sink")
R("R15", "5.1k", "CC2", "GND", "power", (101.6, 60.96), note="CC2 sink")
part("U9", "Power_Protection", "USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
     {"1": "USB_DP", "6": "USB_DP", "3": "USB_DM", "4": "USB_DM", "2": "GND", "5": "VBUS"},
     "power", (96.52, 101.6), lcsc="USBLC6")
part("F1", "Device", "Polyfuse", "PTC 2A", "Fuse:Fuse_1812_4532Metric",
     {"1": "VBUS", "2": "5V"}, "power", (124.46, 60.96), lcsc="PTC2A")
part("C1", "Device", "C_Polarized", "220uF/10V", "Capacitor_SMD:CP_Elec_6.3x5.4",
     {"1": "5V", "2": "GND"}, "power", (144.78, 60.96), lcsc="C220u", note="5V bulk")

# 3V3 (ESP32, CH340C): AMS1117-3.3, SOT-223 (pin 1 GND, 2 VO + tab, 3 VI)
part("U6", "Regulator_Linear", "AMS1117-3.3", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
     {"1": "GND", "2": "3V3", "3": "5V"}, "power", (210.82, 50.8), lcsc="AMS1117")
C("C7", "10uF", "5V", "GND", "power", (180.34, 76.2), note="U6 in")
C("C8", "22uF", "3V3", "GND", "power", (241.3, 76.2), note="U6 out")
# 3V3P (plates, expanders, LIS3DH, microSD): a second AMS1117-3.3 (SOT-223, JLCPCB Basic).
# AMS1117 datasheet: 10 uF on the input, 22 uF minimum on the output for stability.
part("U5", "Regulator_Linear", "AMS1117-3.3", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
     {"1": "GND", "2": "3V3P", "3": "5V"}, "power", (210.82, 106.68), lcsc="AMS1117")
C("C6", "10uF", "5V", "GND", "power", (180.34, 116.84), note="U5 in")
C("C2", "22uF", "3V3P", "GND", "power", (241.3, 116.84), note="U5 out")
C("C19", "100nF", "3V3P", "GND", "power", (254.0, 116.84), note="U5 out")

# CH340C at 3.3 V (V3 tied to VCC), no crystal. TXD -> ESP RXD0 (GPIO3), RXD <- ESP TXD0 (GPIO1).
part("U7", "defuse32", "CH340C_3V3", "CH340C", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm",
     {"1": "GND", "2": "U0RXD", "3": "U0TXD", "4": "3V3", "16": "3V3", "5": "USB_DP", "6": "USB_DM",
      "9": NC, "10": NC, "11": NC, "12": NC, "13": "DTR", "14": "RTS", "15": NC},
     "power", (91.44, 205.74), lcsc="CH340C")
C("C12", "100nF", "3V3", "GND", "power", (33.02, 205.74), note="U7 VCC")
C("C13", "100nF", "3V3", "GND", "power", (45.72, 205.74), note="U7 V3")
# Auto-reset, two NPN (NodeMCU style): Q2 pulls EN low, Q3 pulls IO0 low
R("R12", "10k", "DTR", "AR_DTR_B", "power", (162.56, 182.88), rot=90, note="Q2 base")
part("Q2", "Transistor_BJT", "MMBT3904", "MMBT3904", "Package_TO_SOT_SMD:SOT-23",
     {"1": "AR_DTR_B", "2": "RTS", "3": "EN"}, "power", (180.34, 182.88), lcsc="MMBT3904")
R("R13", "10k", "RTS", "AR_RTS_B", "power", (162.56, 223.52), rot=90, note="Q3 base")
part("Q3", "Transistor_BJT", "MMBT3904", "MMBT3904", "Package_TO_SOT_SMD:SOT-23",
     {"1": "AR_RTS_B", "2": "DTR", "3": "IO0"}, "power", (180.34, 223.52), lcsc="MMBT3904")

# ================================================================== sheet "mcu": WROOM-32E, EN/BOOT, pull-ups, buffer, buzzer
# ESP32 pin map (SPEC "ESP32 pin map", unchanged): module pin -> net
GND_STACK = "[1,15,38,39]"   # stacked GND pin of RF_Module:ESP32-WROOM-32E (pads 1, 15, 38, 39)
U1 = {GND_STACK: "GND", "2": "3V3", "3": "EN",
      "4": "LDR",        # SENSOR_VP GPIO36
      "5": "ENC_SW",     # SENSOR_VN GPIO39 (rev 1b)
      "6": "IR",         # GPIO34
      "7": "MCP_INT",    # GPIO35
      "8": "TM_CLK",     # GPIO32
      "9": "TM_DIO",     # GPIO33
      "10": "WS_DATA",   # GPIO25
      "11": "BUZZ",      # GPIO26
      "12": "SERVO_SIG",  # GPIO27
      "13": "T6",        # GPIO14
      "14": NC,          # GPIO12 strapping, unused
      "16": "T4",        # GPIO13
      "23": "T3",        # GPIO15
      "24": "SD_CS",     # GPIO2
      "25": "IO0",       # GPIO0 boot
      "26": "T0",        # GPIO4
      "27": "U2RX",      # GPIO16
      "28": "U2TX",      # GPIO17
      "29": "CS",        # GPIO5
      "30": "SCK",       # GPIO18
      "31": "MISO",      # GPIO19
      "33": "SDA",       # GPIO21
      "34": "U0RXD",     # RXD0 GPIO3
      "35": "U0TXD",     # TXD0 GPIO1
      "36": "SCL",       # GPIO22
      "37": "MOSI",      # GPIO23
      }
# footprint: official RF_Module:ESP32-WROOM-32E with 0.3 mm thermal-via drills (gen_lib.py)
part("U1", "RF_Module", "ESP32-WROOM-32E", "ESP32-WROOM-32E-N4", "defuse32:ESP32-WROOM-32E_JLC",
     U1, "mcu", (124.46, 101.6), lcsc="WROOM32E")
C("C9", "10uF", "3V3", "GND", "mcu", (60.96, 40.64), note="U1 3V3")
C("C10", "100nF", "3V3", "GND", "mcu", (71.12, 40.64), note="U1 3V3")
R("R10", "10k", "3V3", "EN", "mcu", (40.64, 91.44), note="EN pull-up")
C("C11", "1uF", "EN", "GND", "mcu", (50.8, 91.44), note="EN RC")
part("SW1", "Switch", "SW_Push", "EN", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
     {"1": "EN", "2": "GND"}, "mcu", (45.72, 116.84), rot=270, lcsc="TS1187A")
R("R11", "10k", "3V3", "IO0", "mcu", (76.2, 91.44), note="GPIO0 pull-up")
part("SW2", "Switch", "SW_Push", "BOOT", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
     {"1": "IO0", "2": "GND"}, "mcu", (86.36, 116.84), rot=270, lcsc="TS1187A")

# pull-ups / pull-downs (SPEC "Electronics" R row; rev 1b R9)
R("R2", "4.7k", "3V3P", "SDA", "mcu", (243.84, 48.26), note="I2C SDA pull-up")
R("R3", "4.7k", "3V3P", "SCL", "mcu", (254.0, 48.26), note="I2C SCL pull-up")
R("R4", "10k", "3V3P", "MCP_INT", "mcu", (269.24, 48.26), note="GPIO35 pull-up")
R("R5", "10k", "3V3P", "IR", "mcu", (279.4, 48.26), note="GPIO34 pull-up")
R("R9", "10k", "3V3P", "ENC_SW", "mcu", (289.56, 48.26), note="GPIO39 pull-up")
R("R6", "10k", "LDR", "GND", "mcu", (309.88, 48.26), note="LDR divider low side")
R("R8", "10k", "SD_CS", "GND", "mcu", (325.12, 48.26), note="GPIO2 pull-down")

# WS2812 buffer 3V3 -> 5V: 74AHCT1G125, OE low (pin 1 OE#, 2 A, 3 GND, 4 Y, 5 VCC)
part("U4", "74xGxx", "74AHCT1G125", "74AHCT1G125", "Package_TO_SOT_SMD:SOT-23-5",
     {"1": "GND", "2": "WS_DATA", "3": "GND", "4": "WS_5V", "5": "5V"}, "mcu", (284.48, 134.62),
     lcsc="AHCT1G125")
R("R1", "330", "WS_5V", "LDI", "mcu", (330.2, 134.62), rot=90, note="WS2812 data series R")
C("C5", "100nF", "5V", "GND", "mcu", (358.14, 134.62), note="U4")

# buzzer: Q1 low side, 1k base, 1N4148WS across the buzzer (BUZZ+ = 5V, BUZZ- = collector)
R("R7", "1k", "BUZZ", "BUZZ_B", "mcu", (264.16, 210.82), rot=90, note="Q1 base")
part("Q1", "Transistor_BJT", "MMBT3904", "MMBT3904", "Package_TO_SOT_SMD:SOT-23",
     {"1": "BUZZ_B", "2": "GND", "3": "BUZZ-"}, "mcu", (287.02, 210.82), lcsc="MMBT3904")
part("D1", "Diode", "1N4148WS", "1N4148WS", "Diode_SMD:D_SOD-323",
     {"1": "5V", "2": "BUZZ-"}, "mcu", (325.12, 210.82), rot=270, lcsc="1N4148WS")

# ================================================================== sheet "io": expanders, LIS3DH, microSD
# MCP23017 allocation (SPEC, rev 1b): GPA7/GPB7 output-only -> J_SPARE only
U2 = {"9": "3V3P", "10": "GND", "12": "SCL", "13": "SDA", "15": "GND", "16": "GND", "17": "GND",
      "18": "3V3P", "19": "MCP_INT", "20": "MCP_INT",
      "21": "ROW1", "22": "ROW2", "23": "ROW3", "24": "ROW4",
      "25": "COL1", "26": "COL2", "27": "COL3", "28": "U2_GPA7",
      "1": "SIM1", "2": "SIM2", "3": "SIM3", "4": "SIM4", "5": "KEY",
      "6": "SD_DET", "7": "COL4", "8": "U2_GPB7"}
U3 = {"9": "3V3P", "10": "GND", "12": "SCL", "13": "SDA", "15": "3V3P", "16": "GND", "17": "GND",
      "18": "3V3P", "19": "MCP_INT", "20": "MCP_INT",
      "21": "WA1", "22": "WA2", "23": "WA3", "24": "WA4", "25": "WA5", "26": "ENC_B",
      "27": "ENC_A", "28": "U3_GPA7",
      "1": "WB1", "2": "WB2", "3": "WB3", "4": "WB4", "5": "WB5", "6": "WB6",
      "7": "WA6", "8": "U3_GPB7"}
part("U2", "Interface_Expansion", "MCP23017x-x-SO", "MCP23017-E/SO (0x20)", "Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm",
     U2, "io", (71.12, 78.74), lcsc="MCP23017")
part("U3", "Interface_Expansion", "MCP23017x-x-SO", "MCP23017-E/SO (0x21)", "Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm",
     U3, "io", (185.42, 78.74), lcsc="MCP23017")
C("C3", "100nF", "3V3P", "GND", "io", (27.94, 66.04), note="U2 VDD")
C("C4", "100nF", "3V3P", "GND", "io", (142.24, 66.04), note="U3 VDD")

# LIS3DH, I2C mode (CS high), 0x19 (SA0 high through R20), INT1/INT2 not connected (polled)
part("U8", "Sensor_Motion", "LIS3DH", "LIS3DH (0x19)", "Package_LGA:LGA-16_3x3mm_P0.5mm_LayoutBorder3x5y",
     {"1": "3V3P", "14": "3V3P", "4": "SCL", "6": "SDA", "7": "LIS_SA0", "8": "3V3P",
      "9": NC, "11": NC, "13": NC, "15": NC, "16": NC, "5": "GND", "10": "GND", "12": "GND"},
     "io", (332.74, 63.5), lcsc="LIS3DH")
R("R20", "10k", "3V3P", "LIS_SA0", "io", (284.48, 57.15), note="SA0 high: 0x19")
C("C14", "100nF", "3V3P", "GND", "io", (365.76, 66.04), note="U8 VDD")
C("C15", "10uF", "3V3P", "GND", "io", (375.92, 66.04), note="U8 VDD")
C("C16", "100nF", "3V3P", "GND", "io", (386.08, 66.04), note="U8 VDD_IO")

# microSD push-push (Hirose DM3AT), SPI mode: DAT3/CD = CS, CMD = MOSI, DAT0 = MISO.
# Card detect: DET_A to GND, DET_B -> SD_DET (U2 GPB5) with R19 pull-up.
part("J_SD", "Connector", "Micro_SD_Card_Det_Hirose_DM3AT", "microSD push-push",
     "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5",
     {"1": "SD_DAT2", "2": "SD_CS", "3": "MOSI", "4": "3V3P", "5": "SCK", "6": "GND", "7": "MISO",
      "8": "SD_DAT1", "9": "SD_DET", "10": "GND", "SH": "GND"},
     "io", (360.68, 182.88), lcsc="MICROSD")
R("R16", "10k", "3V3P", "MISO", "io", (269.24, 152.4), note="SD DAT0 pull-up")
R("R17", "10k", "3V3P", "SD_DAT1", "io", (279.4, 152.4), note="SD DAT1 pull-up")
R("R18", "10k", "3V3P", "SD_DAT2", "io", (289.56, 152.4), note="SD DAT2 pull-up")
R("R19", "10k", "3V3P", "SD_DET", "io", (299.72, 152.4), note="card detect pull-up")
C("C17", "100nF", "3V3P", "GND", "io", (269.24, 215.9), note="SD VDD")
C("C18", "10uF", "3V3P", "GND", "io", (279.4, 215.9), note="SD VDD")

# ================================================================== sheet "conn": plate connectors, headers, holes
# Plate signal sets = rev 1 Jn_B table. IDC pinout rule (SPEC rev 2): 1 5V, 2 GND, 3 3V3P, 4 SDA,
# 5 SCL, 6 LDI, 7 LDO, then the plate's signals in this order, spare positions GND.
PLATES = {
    1: ("Radio", 5, ["ENC_A", "ENC_B", "ENC_SW"]),
    2: ("Timer", 6, ["TM_CLK", "TM_DIO", "BUZZ-", "5V"]),     # last = BUZZ+ (5V)
    3: ("Keypad", 8, ["ROW1", "ROW2", "ROW3", "ROW4", "COL1", "COL2", "COL3", "COL4"]),
    4: ("Wires", 10, ["WA%d" % i for i in range(1, 7)] + ["WB%d" % i for i in range(1, 7)]),
    5: ("Probe", 7, ["U2TX", "U2RX", "SCK", "MOSI", "MISO", "CS"]),
    6: ("Sensors", 10, ["T0", "T4", "T6", "T3", "LDR", "IR", "SIM1", "SIM2", "SIM3", "SIM4", "SERVO_SIG"]),
}
PLATE_PINNAMES = {2: {11: "BUZZ+ (5V)"}}
# WS2812 chain: U4 -> R1 -> LDI (M1) -> LDO1 (M1 out = M2 in) ... -> M6 LDO (chain end, NC)
LD_IN = {1: "LDI", 2: "LDO1", 3: "LDO2", 4: "LDO3", 5: "LDO4", 6: "LDO5"}
LD_OUT = {1: "LDO1", 2: "LDO2", 3: "LDO3", 4: "LDO4", 5: "LDO5", 6: NC}
PLATE_SCH = {1: (66.04, 60.96), 2: (193.04, 60.96), 3: (320.04, 60.96),
             4: (66.04, 147.32), 5: (193.04, 147.32), 6: (320.04, 147.32)}


def plate_pins(n):
    name, rows, sig = PLATES[n]
    pins = ["5V", "GND", "3V3P", "SDA", "SCL", LD_IN[n], LD_OUT[n]] + sig
    pins += ["GND"] * (2 * rows - len(pins))
    assert len(pins) == 2 * rows, n
    return pins


for _n in range(1, 7):
    _name, _rows, _ = PLATES[_n]
    part("J%d" % _n, "Connector_Generic", "Conn_02x%02d_Odd_Even" % _rows, "M%d %s" % (_n, _name),
         IDC % _rows, {str(i + 1): p for i, p in enumerate(plate_pins(_n))}, "conn", PLATE_SCH[_n],
         lcsc="IDC%d" % (2 * _rows))

part("J_KEY", "Connector_Generic", "Conn_01x02", "key switch", PINHDR % 2, {"1": "KEY", "2": "GND"},
     "conn", (50.8, 238.76), lcsc="HDR2")
part("J_SERVO", "Connector_Generic", "Conn_01x03", "SG90 GND/5V/SIG", PINHDR % 3,
     {"1": "GND", "2": "5V", "3": "SERVO_SIG"}, "conn", (114.3, 238.76), lcsc="HDR3")
SPARE_PINS = ["U2 GPA7", "U2 GPB7", "U3 GPA7", "U3 GPB7", "GND"]
part("J_SPARE", "Connector_Generic", "Conn_01x05", "outputs only", PINHDR % 5,
     {"1": "U2_GPA7", "2": "U2_GPB7", "3": "U3_GPA7", "4": "U3_GPB7", "5": "GND"},
     "conn", (177.8, 241.3), lcsc="HDR5")
for _i, _xy in enumerate(((215.9, 223.52), (246.38, 223.52), (215.9, 246.38), (246.38, 246.38))):
    part("H%d" % (_i + 1), "Mechanical", "MountingHole", "MountingHole_M3", "MountingHole:MountingHole_3.2mm_M3",
         {}, "conn", _xy)

# ------------------------------------------------------------------ schematic frames and notes
# sheet -> [(x1, y1, x2, y2, title, [(note, x, y), ...])]; note coordinates absolute
BLOCKS = {
    "power": [
        (15.24, 15.24, 160.02, 134.62, "USB-C INPUT, ESD, FUSE, BULK", [
            ("USB-C is the only power input and the programming port (panel-mount extension to the case wall).", 17.78, 22.86),
            ("CC1/CC2 5.1k to GND: 5 V sink. VBUS -> F1 (PTC, 2 A hold) -> 5V. Budget 5 V / 2 A (firmware caps WS2812).", 17.78, 26.67),
            ("U9 USBLC6-2SC6 on D+/D- (pins 1/6 and 3/4 are flow-through pairs). SBU unused. Shield to GND.", 17.78, 125.73),
        ]),
        (165.1, 15.24, 290.83, 134.62, "REGULATORS", [
            ("U6 AMS1117-3.3: 5V -> 3V3 (ESP32 module, CH340C).", 167.64, 22.86),
            ("U5 AMS1117-3.3 (1 A): 5V -> 3V3P (plates, U2/U3, LIS3DH, microSD, pull-ups).", 167.64, 26.67),
            ("Each AMS1117: 10 uF in, 22 uF out (datasheet minimum for stability).", 167.64, 30.48),
            ("10 uF + 100 nF at the module 3V3 pin: C9/C10 (ESP32 sheet).", 167.64, 129.54),
        ]),
        (295.91, 15.24, 405.13, 63.5, "POWER FLAGS (ERC)", []),
        (15.24, 139.7, 290.83, 281.94, "USB-UART (CH340C) AND AUTO-RESET", [
            ("CH340C at 3.3 V: V3 tied to VCC (local symbol CH340C_3V3: pin 4 typed power_in). No crystal.", 17.78, 147.32),
            ("UART0: CH340C TXD -> U0RXD (GPIO3), RXD <- U0TXD (GPIO1). CTS/DSR/RI/DCD, R232 unused.", 17.78, 151.13),
            ("Auto-reset: DTR=0 RTS=1 -> Q2 pulls EN low; DTR=1 RTS=0 -> Q3 pulls IO0 low; both equal -> released.", 129.54, 251.46),
            ("EN RC (R10 10k + C11 1 uF) and the IO0 pull-up R11 are on the ESP32 sheet.", 129.54, 255.27),
        ]),
    ],
    "mcu": [
        (15.24, 15.24, 226.06, 200.66, "ESP32-WROOM-32E (U1)", [
            ("Soldered at the left board edge, antenna end outward: the antenna region is outside the outline,", 17.78, 160.02),
            ("no copper under or around it (keep-out in the footprint).", 17.78, 163.83),
            ("GPIO2 = SD_CS (R8 pull-down keeps the strapping valid). GPIO12: strapping, unused (NC).", 17.78, 167.64),
            ("GPIO0/1/3: boot and UART0 console (CH340C). GPIO6-11: module flash (NC pins).", 17.78, 171.45),
            ("EN: R10 10k + C11 1 uF, SW1. BOOT: SW2 on IO0 with R11 10k pull-up.", 17.78, 175.26),
        ]),
        (231.14, 15.24, 405.13, 95.25, "PULL-UPS, PULL-DOWNS", [
            ("R2/R3 I2C 4.7k; R4 GPIO35 (MCP_INT), R5 GPIO34 (IR), R9 GPIO39 (ENC_SW) 10k to 3V3P.", 233.68, 81.28),
            ("R6: LDR divider low side (LDR on M6 from 3V3P -> GPIO36). R8: GPIO2 (SD_CS) pull-down.", 233.68, 85.09),
        ]),
        (231.14, 100.33, 405.13, 165.1, "WS2812 BUFFER 3V3 -> 5V", [
            ("U4 74AHCT1G125 at 5 V, OE low. R1 330R in series. Chain: LDI -> M1 ... M6 (connectors sheet).", 233.68, 158.75),
        ]),
        (231.14, 170.18, 405.13, 245.11, "BUZZER DRIVER", [
            ("GPIO26 (BUZZ, LEDC PWM) -> R7 -> Q1. Buzzer on M2: BUZZ+ = 5V (J2 pin 11), BUZZ- on J2 pin 10.", 233.68, 237.49),
        ]),
    ],
    "io": [
        (15.24, 15.24, 250.19, 147.32, "I2C EXPANDERS (U2 0x20, U3 0x21)", [
            ("INTA/INTB of both chips: mirrored, open-drain, wired-OR to GPIO35 (MCP_INT).", 17.78, 137.16),
            ("U2: keypad ROW1-4 GPA0-3, COL1-3 GPA4-6, COL4 GPB6, Simon SIM1-4 GPB0-3, KEY GPB4, SD_DET GPB5.", 17.78, 140.97),
            ("U3: wire posts WA1-5 GPA0-4, WA6 GPB6, WB1-6 GPB0-5, ENC_A/B GPA6/5. GPA7/GPB7: output-only -> J_SPARE.", 17.78, 144.78),
        ]),
        (255.27, 15.24, 405.13, 116.84, "TILT SENSOR LIS3DH (I2C 0x19)", [
            ("I2C mode: CS high. SA0 high through R20 -> address 0x19. INT1/INT2 not connected (polled).", 257.81, 106.68),
            ("Replaces the rev 1 GY-521 / MPU-6050.", 257.81, 110.49),
        ]),
        (255.27, 121.92, 405.13, 245.11, "microSD (push-push, SPI mode)", [
            ("VSPI shared with the probe plate: SCK GPIO18, MOSI GPIO23, MISO GPIO19, SD_CS GPIO2.", 257.81, 229.87),
            ("DAT0-2 10k pull-ups to 3V3P. Card detect: DET_A GND, DET_B -> SD_DET (U2 GPB5), R19 pull-up:", 257.81, 233.68),
            ("low = card present: the DM3 detect switch is normally open and closes on insertion (Hirose DM3", 257.81, 237.49),
            ("catalog). Firmware: CONFIG_D32_SD_DET_ACTIVE_HIGH=n.", 257.81, 241.3),
        ]),
    ],
    "conn": [
        (15.24, 15.24, 405.13, 190.5, "PLATE CONNECTORS (2.54 mm keyed IDC box headers, ribbon cable to each plate)", [
            ("Pinout rule: pin 1 5V, pin 2 GND, 3 3V3P, 4 SDA, 5 SCL, 6 LDI, 7 LDO, then the plate signals, spare = GND.", 17.78, 22.86),
            ("WS2812 chain: U4 -> R1 -> LDI (M1) -> LDO1 -> M2 -> LDO2 -> M3 -> LDO3 -> M4 -> LDO4 -> M5 -> LDO5 -> M6 (end).", 17.78, 26.67),
            ("TM1637 on M2 is powered from 3V3P (pin 3): from 5V its pull-ups would put 5 V on GPIO32/33.", 17.78, 30.48),
        ]),
        (15.24, 195.58, 285.75, 281.94, "CARRIER HEADERS, MOUNTING HOLES", [
            ("J_KEY: key switch (case wall) -> U2 GPB4.  J_SERVO: SG90 order GND / 5V / SIG (same net as J6 SERVO_SIG).", 17.78, 203.2),
            ("J_SPARE: U2 GPA7, U2 GPB7, U3 GPA7, U3 GPB7, GND (output-only MCP pins).", 17.78, 207.01),
        ]),
    ],
}
PWR_FLAGS = ("power", [("VBUS", 300.99, 40.64), ("5V", 332.74, 40.64), ("GND", 364.49, 40.64)])

# ------------------------------------------------------------------ PCB placement (rev 2)
BOARD_W, BOARD_H = 100.0, 70.0
HOLE_INSET = 4.0
# (x, y, rotation) in board coordinates: origin = board top-left corner, x right, y down (mm),
# rotation in KiCad degrees (counter-clockwise). Follows the approved preview (SPEC "Rev 2
# carrier", positions within 5 mm). The placement was done for the routing task (2026-10-23);
# the routed board is the reference from now on (gen_pcb.py refuses to overwrite it).
#   - U1 local y = -6.56 (antenna-region boundary) on the board edge x = 0: the antenna and its
#     keep-out zone are outside the outline.
#   - IDC box headers: key notch toward the nearest board edge (top row 270, bottom row 90,
#     J6 180), so pin 1 / the odd row is on the edge side.
#   - Two changes against the preview's labels (same positions): BOOT (SW2) is the upper button,
#     next to module pin 25 (IO0), EN (SW1) the lower one, near pin 3; U3 (wires, J4 + J1) takes
#     the left expander position and U2 (keypad J3, Simon J6, microSD detect) the right one.
PCB = {
    "U1": (6.56, 35.0, 90),
    "H1": (4, 4, 0), "H2": (96, 4, 0), "H3": (4, 66, 0), "H4": (96, 66, 0),
    # plate connectors and edge parts
    # (the footprint's pin-1 marker sits 4.7 mm out on the notch side: rows at 4.9 mm from the edge)
    "J1": (23.24, 4.9, 270), "J2": (49.8, 4.9, 270), "J3": (81.8, 4.9, 270),
    "J4": (13.1, 65.1, 90), "J5": (49.1, 65.1, 90),
    "J6": (95.1, 38.0, 180),
    "J_USB": (96.35, 49.5, 90),           # receptacle front face on the right edge (x = 100)
    "J_SD": (80.0, 61.2, 0),              # card slot on the bottom edge
    "J_KEY": (3.8, 13.3, 0), "J_SERVO": (3.8, 51.5, 0), "J_SPARE": (31.3, 50.3, 90),
    # module: decoupling at pin 2 (3V3), BOOT/EN buttons, EN RC, IO0 pull-up
    "C10": (2.0, 46.0, 180), "C9": (2.0, 48.1, 180),
    "SW2": (24.4, 29.6, 0), "SW1": (24.4, 40.4, 0),
    "R11": (29.6, 29.0, 90), "R8": (31.4, 29.0, 90),
    "C11": (29.6, 40.4, 270), "R10": (31.4, 40.4, 90),
    # pull-ups / pull-down on the module's lower pin row
    "R6": (8.0, 52.5, 90), "R9": (9.9, 52.5, 90), "R5": (11.8, 52.5, 90), "R4": (13.7, 52.5, 90),
    # expanders (SOIC-28W, long axis horizontal) and their 100 nF at VDD/VSS (pins 9/10)
    "U3": (39.0, 21.0, 90), "C4": (41.54, 28.2, 0),
    "U2": (61.0, 21.0, 90), "C3": (63.54, 28.2, 0),
    "R3": (34.6, 34.6, 270), "R2": (36.4, 38.5, 90),      # I2C pull-ups next to the LIS3DH SCL/SDA pads
    # LIS3DH
    "U8": (38.0, 34.5, 0), "C14": (39.28, 31.5, 0), "C16": (36.0, 31.5, 180), "C15": (41.85, 33.0, 270),
    "R20": (38.8, 37.7, 180),
    # WS2812 buffer, buzzer driver
    "U4": (47.5, 32.5, 0), "C5": (50.6, 32.0, 270), "R1": (47.6, 35.6, 180),
    "Q1": (56.2, 33.0, 0), "R7": (53.3, 32.6, 90), "D1": (59.6, 33.0, 90),
    # regulators (2 x AMS1117-3.3, input pins toward the USB side), bulk
    "U6": (66.0, 44.0, 180), "C7": (71.8, 42.6, 270), "C8": (59.5, 44.0, 180),
    "U5": (66.0, 52.0, 180), "C6": (71.8, 50.5, 270), "C2": (59.5, 52.0, 180), "C19": (59.8, 54.4, 180),
    "C1": (52.0, 53.0, 0),
    # USB-C, ESD, fuse, CC resistors (USB area hand-routed in route_prep.PREROUTE)
    "U9": (87.8, 49.5, 0), "F1": (90.0, 59.0, 270),
    "R15": (89.9, 45.2, 90), "R14": (90.2, 54.0, 270),
    # CH340C and auto-reset
    "U7": (82.0, 43.0, 90), "C12": (75.4, 41.6, 270), "C13": (80.6, 48.3, 270),
    "Q2": (79.5, 35.5, 0), "R12": (79.5, 31.8, 0), "Q3": (85.0, 35.5, 0), "R13": (85.0, 31.8, 0),
    # microSD supply and pull-ups
    "C17": (78.4, 51.3, 180), "C18": (75.0, 51.2, 180),
    "R16": (63.0, 57.15, 90), "R17": (64.9, 57.15, 90), "R18": (66.8, 57.15, 90), "R19": (68.7, 57.15, 90),
}
for p in PARTS:
    p["pcb"] = PCB[p["spec"]]
_extra = set(PCB) - {p["spec"] for p in PARTS}
assert not _extra, _extra

# ------------------------------------------------------------------ net classes (rev 2)
POWER_NETS = ["5V", "3V3", "3V3P", "GND", "VBUS"]
NETCLASS = {"Default": (0.2, 0.2), "Power": (0.6, 0.25)}   # (track, clearance) mm


def expand_pin(pin):
    """Pad numbers of a symbol pin: a stacked pin "[1,15,38,39]" stands for pads 1, 15, 38, 39."""
    if pin.startswith("[") and pin.endswith("]"):
        return pin[1:-1].split(",")
    return [pin]


def pad_nets(p):
    """{pad number: net} of part p (stacked pins expanded; NC pins -> None)."""
    return {q: net for pin, net in p["nets"].items() for q in expand_pin(pin)}
