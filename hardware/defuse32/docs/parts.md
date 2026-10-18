# Defuse32 parts: case and module dimensions

Research for rev 0 CAD (October 2026). All values are in mm. **V** = verified: read off a dimensioned drawing or datasheet. **T** = typical: a common value inferred from photos, listings or several clones. Measure every T value on the parts you actually receive before cutting plates. The machine-readable copy for the FreeCAD scripts is `../data/parts.json`; its coordinate convention is stated at the top of that file and repeated in the [module conventions](#module-conventions) below.

## 1. Case

### Candidates

| Case | Interior L x W | Base / lid depth | Exterior | Price (USD) | Panel kit / CAD | Verdict |
|---|---|---|---|---|---|---|
| **Pelican 1520** (1520NF, empty) | 458.7 x 327.4 (18.06 x 12.89 in) V | 125.2 / 45.5 V | 502 x 401 x 188 V | 168-218 (list 217.95) | **1520PF panel frame kit** (US$31.95), official STEP/IGS/DXF/PDF for the 1520 and 1520PF | **Chosen** |
| Nanuk 930 | 459 x 332 (463 x 337 at the rim) V | 124 / 54 V | 499 x 406 x 192 V | 190-210 (EU €279) | Dimensioned assembly drawing; no panel frame kit found | Good alternative |
| Harbor Freight Apache 4800 | 454 x 327 (17-7/8 x 12-7/8 in) V | total 168 V; split not published (forum: lid up to 44 mm, so base about 124) T | 516 x 394 x 187 V | 59.99 | None | Cheapest, US only |
| Pelican 1500 | 425.5 x 284 V | 109.5 / 46 V | 470 x 357 x 176 | ~150 | 1500PF + CAD | Rejected: base 109 < 120 |
| Pelican 1450 | 372.4 x 260.1 V | 111 / 44.5 V | 406 x 330 x 174 | ~130 | 1450PF + CAD | Rejected: too small, too shallow |
| Nanuk 925 | 432 x 300 V | 108 / 53 V | 475 x 376 x 178 V | ~170 | none | Rejected: base 108 |
| Apache 3800 | 378 x 270 V | total 156 V | ~470 x 360 x 180 | ~40 | none | Rejected: too small |

Sources: Pelican 1520 [Full Compass](https://www.fullcompass.com/prod/527190-pelican-cases-1520nf-protector-case-18-1-x12-9-x6-7-protector-case-empty-interior), [Specialty Cases](https://specialtycases.com/amp/pelican-1520-medium-case-with-empty-interior.html), prices from [Markertek](https://www.markertek.com/product/bpl1520s-nf/pelican-1520nf-protector-case-with-no-foam-silver) and [Filmtools](https://www.filmtools.com/pelican-1520-case-1520nf.html); 1520PF frame drawing [1523-314-000 rev A](https://media.pelican.com/cad/protector-panel-frames/1520/1520_pf.pdf); Pelican [CAD downloads](https://pid.pelican.com/ca/en/professional/cad-downloads/) (lists 1450, 1500, 1520 and their PF variants as STEP, IGS, DXF and PDF); Nanuk 930 [Plasticase drawing](https://downloads.gentec-eo.com/prod/2d3c8a87/NAN-930_Drawing.pdf) and [Nanuk EU store](https://nanuk.eu/products/nanuk-930); Apache 4800 [harborfreight.com](https://www.harborfreight.com/4800-weatherproof-protective-case-x-large-black-64250.html) and [forum on the lid depth](https://forums.collectors.com/discussion/comment/13028612/); Pelican 1500 [Roberts Camera](https://robertscamera.com/pel-1500-black-pel-00021); Pelican 1450 [pelican.com sheet](https://www.pelican.com/au/ja/product/cases/1450/pdf); Nanuk 925 [optics-trade](https://www.optics-trade.eu/uk/nanuk-925-case.html); Apache 3800 [Slickdeals quoting HF](https://slickdeals.net/f/15103936-harbor-freight-apache-3800-weatherproof-case-29-99-b-m-or-6-99-shipping). Exterior sizes without a V are approximate.

### Recommendation: Pelican 1520 with the 1520PF panel frame

- **Fit.** The 125 mm base meets the 120 mm minimum, and the 45.5 mm lid leaves room for knobs and posts above the plates. It is the only candidate whose maker sells a panel frame.
- **Documented.** Pelican's 1520PF drawing gives the frame outline, its clear opening and all 16 insert positions, and Pelican publishes STEP files for the case. Nothing has to be guessed for the panel interface.
- **Easy to buy.** Pelican is sold worldwide through camera, pro-audio and industrial distributors. The Apache 4800 is a third of the price but is sold only by Harbor Freight in the US, with no drawings and no lid/base split. The Nanuk 930 is the fallback if a deeper lid (54 mm) matters more than the frame kit.

**Panel support.** The 1520PF frame sits inside the base rim, sealed by its O-ring and held by 4 self-tapping screws into the wall. The panel screws onto the frame's 16 brass inserts, and the panel's top ends up flush with the rim. Nothing goes through the case shell.

| Frame item (1520PF drawing) | Value |
|---|---|
| Frame outer | 454.6 x 323.9, R16.5 corners, 17.5 tall V |
| Clear opening (inside the frame) | 422.6 x 291.2 V |
| Insert holes | 16 x dia 5.2 on a 431.8 x 301.2 rectangle V |
| Long-side insert x (from the left column) | 0, 38.6, 127.3, 215.9, 304.5, 393.2, 431.8 V |
| Short-side insert y (from the bottom row) | 0, 39.9, 150.6, 261.4, 301.2 V |
| Insert thread | Not published; Case Club reports #6-32 for the 1300PF T |

**Panel chosen:** 452 x 321 x 3 mm with R16.5 corners. This is the frame outline less about 1.3 mm per side; test-fit it against the frame. The panel has 16 holes of dia 3.6 at the insert positions (panel coordinates are in `parts.json`). Every plate opening and every hanging module must stay inside the 422.6 x 291.2 clear opening, which is still larger than the 370-400 x 260-300 area the brief started from. Use 3 mm laser-cut acrylic or ply. A metal panel would shield the DevKit's PCB antenna and the PN532.

**Assumptions to check on the real case:**
- The 1520's interior corner radius is not published. R16.5, the frame's own radius, is assumed.
- The floor is assumed to be about 445 x 314 usable, allowing roughly 1° of wall draft plus the floor fillets. The Nanuk 930 drawing shows the walls 2.2-2.5 mm narrower per side at the floor than at the rim, over a similar depth.

### Depth budget (z = 0 at the base interior floor)

| z from | z to | What | Status |
|---|---|---|---|
| 0 | 3 | Floor sled (3 mm ply or printed plate, held by VHB or foam wedges; floor not drilled) | proposal |
| 3 | 11 | M3 x 8 standoffs | proposal |
| 11 | 12.6 | Carrier PCB, 1.6 mm | proposal |
| 12.6 | 23.6 | Female header (8.5) + DevKit male-header spacer (2.5) | T |
| 23.6 | 28.5 | DevKit PCB + WROOM-32E module (3.1); highest part on the carrier | T |
| 12.6 | 40 | JST-XH headers, mated housings and wire bends | T |
| 40 | 85.2 | Free harness zone (45 mm) | derived |
| 85.2 | 122.2 | Modules hanging under the plates (40 mm below the plate underside) | SPEC |
| 122.2 | 125.2 | Panel, 3 mm; top flush with the rim (`z_from_floor` = 122.2) | proposal |
| 125.2 | 128.2 | Module plates, 3 mm, on top of the panel | proposal |
| 128.2 | 163.2 | Knobs, binding posts and antenna; keep these within 35 mm of the plate top | proposal |
| 163.2 | 170.7 | Margin to the lid's inner skin | derived |

**Case wall parts.** The key switch and the USB-C input reach up to 51 mm into the base. Put them in a flat wall area between z 40 and 100, and keep the carrier out of that strip. Pelican walls have ribs, latches and a handle, so pick the spot on the physical case.

## 2. Modules

### Module conventions

- All x, y values are measured from the PCB's bottom-left corner in top view. Top view means looking at the face that points up out of the panel (display, key or shaft side). Each section says which edge is the top.
- Holes are given as centre positions.
- The window is the area the plate cut-out must expose.
- Heights are measured from the PCB faces. Panel hardware (posts, key switch, USB-C) is measured from the panel face instead.

### ESP32-DevKitC-32E (DevKitC V4 board, 38 pin): V

- **PCB:** 27.94 x 48.26 V. The module antenna overhangs the top edge by 6.04 V; it is 18.00 wide and centred, giving 54.30 overall. PCB thickness 1.6 T.
- **Headers:** 2 x 19 pins at 2.54 pitch. **Row spacing is 25.40 V.** The first pin is 1.29 from the USB edge V; pins sit about 1.27 from the long edges (the drawing shows 1.30 on one side).
- **Mounting holes:** none V.
- **Height:** about 3.5 above the PCB (module 3.1 T). Pre-soldered male headers stick out about 8.5 below T.
- **Clone warning:** narrow 38-pin clones (NodeMCU-32S style) use **22.86 mm** rows and measure about 25.5 x 52 mm, so they will not plug into a 25.4 mm footprint.
- Sources: [Espressif dimension drawing](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.pdf), [user guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html), [clone spacing](https://esp32.com/viewtopic.php?p=89735).

### GY-521 MPU-6050: T

- **PCB:** 15.56 x 20.26 (Components101 layout). Clones range 20.3-21.2 x 15.6-16.4.
- **Holes:** 2 x dia 3.0 V on the right edge at (12.96, 2.47) and (12.96, 17.79) T.
- **Header:** 1 x 8 at 2.54 on the left edge at x 1.4, VCC at the top T.
- **Mounting:** plugs into a female 1x8 on the carrier.
- Sources: [Components101](https://components101.com/sensors/mpu6050-module), [Wheeltec listing (dia 3.2 holes)](https://openelab.io/products/wheeltec-gy-521-mpu-6050).

### MCP23017-E/SP (28-lead SPDIP, 300 mil): V

- **Body:** 7.24 x 34.67 x 3.43 nominal, seated height up to 5.08.
- **Pins:** 2 x 14 at 2.54 pitch, rows 7.62 apart.
- **Socket:** 0.3 in DIP-28 socket, about 35.6 x 10.1 x 4.3 T.
- Sources: [DigiKey 28-SPDIP](https://www.digikey.com/en/products/detail/microchip-technology/MCP23017-E-SP/894272), [Master Electronics (34.67 x 7.24 x 3.43)](https://masterelectronics.com/en/microchip-technology/mcp23017esp-44800866.html), Microchip drawing C04-070.

### KY-040 rotary encoder: T

- **PCB:** 26.2 x 18.63 V (about 32 long including the right-angle pins).
- **Encoder:** EC11 type, centre at about (9.2, 10.8) T. Bushing **M7 x 0.75** V, about 7 long. Shaft dia 6 with a D-flat to 4.5. Tip about 26.5 above the PCB with the common 20 mm shaft T.
- **Mounting:** through the bushing. The plate needs a **7.5 mm hole**, and an M7 nut (about 10 AF, 2 thick) goes on top. With a 3 mm plate, the encoder body must sit no more than about 2 mm below the plate.
- **PCB holes:** 2 x dia 2.75, about 1.75 from the bottom edge. Positions are unreliable (one seller says 13.75 mm pitch), so do not depend on them.
- **Header:** 5 pins (CLK, DT, SW, +, GND) at x about 24.1, pointing right T.
- Sources: [Components101 drawing](https://components101.com/modules/KY-04-rotary-encoder-pinout-features-datasheet-working-application-alternative), [Same Sky ACZ11 (M7 x 0.75 bushing)](https://www.sameskydevices.com/product/motion-and-control/rotary-encoders/incremental/panel/mechanical/acz11br1e-20fd1-12c), [Sigmanortec (2.75 holes)](https://sigmanortec.ro/en/rotary-encoder-module-ky-040).

### TM1637 0.56 in 4-digit module: T

- **PCB:** 66.1 x 27.1 (measured by lygte-info).
- **Holes:** 4 x dia 3.2 at (2.9, 2.8), (63.2, 2.8), (2.9, 24.3) and (63.2, 24.3), about 60.3 x 21.5 apart T.
- **Display:** body 50.4 x 19.0 x 8.0. Window at (7.85, 4.3), size 50.4 x 19.0 T.
- **Headers:** 4 pins at each end, at x 2.8 and 63.3 T.
- **Different part:** the 0.36 in module (42.0 x 24.1, holes 2.2 on 38.0 x 20.3) is not interchangeable.
- Sources: [lygte-info module table](https://lygte-info.dk/project/DisplayModuleSpecifications.html), [Probots (4 corner M2/M3 holes)](https://probots.co.in/red-tm1637-056-inch-4-bit-digital-tube-led-display-module.html), [Electrokit 0.36 in](https://electrokit.com/en/seriell-display-7-segment-4-siffror-tm1637).

### SSD1306 0.96 in I2C OLED (4 pin): T

The header edge is the top.

- **PCB:** 27.3 x 27.8 V.
- **Holes:** 4 x M2 (dia 2.0), centres 2.0 in from each edge, so 23.3 x 23.8 apart V. Batches vary between 27 and 27.5 square, and one measured board had holes about 22.3 x 23 apart.
- **Glass and active area:** glass 26.7 x 19.26 V, active area 21.74 x 10.86 V, viewing area 23.74 x 12.86.
- **Window:** the viewing area at (1.78, 9.1). The vertical position is estimated to within ±1.5 mm, so cut the window 2 mm taller and test-fit.
- **Height:** about 1.8 above the PCB. Pins point back, about 8.5.
- **Header:** 4 pins centred, 2.0 below the top edge T.
- Sources: [Components101 drawing](https://components101.com/displays/oled-display-ssd1306), [panel spec](https://marketplace.oled-info.com/view/140/Wc096-12864), [measured footprint](https://git.cuvoodoo.info/kingkevin/qeda_library/src/branch/usb-cable-tester/display/display_oled_0.96in.yaml).

### SH1106 1.3 in I2C OLED (4 pin): T

The header edge is the top.

- **PCB:** 35.5 x 33.7 V.
- **Holes:** centres 2.0 from the sides, 3.0 from the top and 2.0 from the bottom V (ETT drawing), so 31.5 x 28.7 apart. Diameter about 2.2 T. Other sellers quote 30.5 x 29 or 30 x 28.
- **Header:** pin 1 is 13.94 from the left edge and 1.30 below the top edge, 4 pins at 2.54 V.
- **Glass and active area:** glass 34.5 x 23.0 T, active area 29.42 x 14.70 V.
- **Window:** the 31.42 x 16.7 viewing area at (2.04, 9.9) T.
- Sources: [ETT guide with drawing](https://zbotic.in/wp-content/uploads/2023/08/1.3-Inch-I2C-IIC-OLED-LCD-Module-4pin-with-VCC-GND-Blue-1.pdf), [Makers Electronics](https://makerselectronics.com/product/oled-display-module-i2c-4-pin-1-3%E2%80%B3/), [Audiophonics](https://www.audiophonics.fr/en/screens-vu-meters/white-oled-13-screen-128x64-sh1106-interface-i2c--p-11573.html).

### PN532 NFC V3 (Elechouse, red): T

The SPI header edge is the top.

- **PCB:** 42.7 x 40.4, 4 thick including components V.
- **Holes:** 2 x dia 3.0, diagonal, at about (7.0, 33.1) and (35.6, 8.0) T.
- **Headers:** I2C/HSU 4 pins at x about 6.1 (y 16.6-24.2). SPI 8 pins along the top at y about 34.6, from x about 14.6 T.
- **Antenna:** the antenna is the roughly 4 mm white band around the edge. Mount it antenna-up under a non-metal plate no thicker than 3 mm, with no metal over the band.
- Sources: [Elechouse V3 manual](https://www.elechouse.com/elechouse/images/product/PN532_module_V3/PN532_%20Manual_V3.pdf), [Digitec (3 mm holes)](https://www.digitec.ch/en/s1/product/purecrea-pn532-nfc-rfid-module-v3-set-with-rfid-card-and-key-single-board-computer-kits-38957873).

### 4x4 hard-key keypad: T (outline and hole spacing V)

This is the common black ABS keypad with 16 plastic keys and a 10-pad PCB tail.

- **Frame:** 66 x 68.6 x 10 V (AZ-Delivery gives 68 x 66 x 10).
- **Holes:** 4 holes 61 mm apart V, assumed square at (2.5, 3.8) and so on, dia 3 T.
- **Cut-out:** the raised key field fits a 60 x 60 cut-out V. Give it corners of about R6 so the cut-out clears the corner holes.
- **Key pitch:** about 13.5 x 14 T.
- **Pads:** NC C1-C4 R1-R4 NC at 2.54 on the tail below the bottom edge.
- **Legends:** phone-style (1-9, 0, A-D, \*, #), so the SPEC's 0-F labels need an overlay or stickers.
- **Smaller alternative:** a bare 16 x 6 mm tact-switch board (39 x 43, about 9.5 pitch, no holes) also exists.
- Sources: [AZ-Delivery datasheet](https://cdn.shopify.com/s/files/1/1509/1638/files/4x4_Keypad_Tastatur_Datenblatt_AZ-Delivery_Vertriebs_GmbH.pdf), [Vetco (61 mm holes, 60 x 60 cut-out)](https://vetco.net/products/vupn7082_16-button_numeric_keypad_matrix), [Electrokit tact board](https://www.electrokit.com/en/keypad-tact-16-buttons-4x4-matrix).

### VS1838B IR receiver: V

- **Body:** face 6.1 x 7.1, 5.1 deep including the dome.
- **Leads:** 3 at 2.54 pitch, 26.5 long, in the order OUT GND VCC.
- **Mounting:** lens up behind a 6.5 x 7.5 window (a proposal).
- Source: [VS1838B datasheet](https://www.datasheetcafe.com/wp-content/uploads/2015/11/VS1838B.pdf).

### GL5528 LDR: V

- **Body:** dia 5.1 with flats 4.3 apart, 2.1 thick.
- **Leads:** dia 0.5, 3.0 apart (TruOpto), 34 long. JCHL parts use 3.4 mm spacing.
- **Mounting:** press-fit into a 5.4 mm plate hole (a proposal).
- Sources: [TruOpto/Rapid datasheet](https://static.rapidonline.com/pdf/58-0134_v1.pdf), [LCSC JCHL](https://www.lcsc.com/product-detail/C10081.html).

### 12 mm tactile switch: V

- **Body:** 12 x 12, 3.5 tall. Actuator top 7.3 above the PCB; stem 3.8 square, collar dia 7.
- **Pins:** 12.5 x 5.0 apart, PCB holes dia 1.3.
- **Caps:** add about 4.7, giving about 12 overall. The plate opening depends on the translucent cap chosen, which is still open.
- Sources: [Same Sky TS13 datasheet](https://www.sameskydevices.com/product/resource/ts13.pdf), [ProtoSupplies caps](https://protosupplies.com/product/tactile-momentary-pushbutton-black-12mm/).

### SG90 servo: T (main outline V)

- **Outline:** flange 32.2 long, body 22.2 x 11.8. The drawing gives 16 below the flange and 31 overall, so about 15 rises above the flange V.
- **Ear holes:** dia 2 at 27.5 centres T.
- **Output shaft:** about 6 from one body end T. The horn adds about 4.
- Source: [TowerPro SG90 sheet](https://tams.informatik.uni-hamburg.de/lehre/2023ss/vorlesung/es/doc/sg90.pdf).

### 4 mm banana binding post: T

- **Panel hole:** **7.0** for Cliff TP6-class posts V. Cheap M4/M6 posts need 4.5-8 mm, so drill to suit the post actually bought.
- **Height:** about 30 above the panel, with a maximum panel thickness of 7 (RS PRO post). About 18 below the panel for the thread, nuts and solder lug T.
- **Spacing:** use centres of at least 19.05 (0.75 in) so dual plugs fit. A 2 x 6 grid at that pitch needs about 130 x 40.
- **Lid:** posts plus plugged leads exceed the 45.5 mm lid, so leads must be unplugged before closing the case.
- Sources: [Distrelec Cliff (7 mm hole)](https://www.distrelec.ch/en/binding-post-4mm-30a-black-cliff-cl159711a/p/30135735), [RS PRO 4 mm post](https://assets.rs-online.com/v1699820170/Datasheets/605789aa7ae4627d0507610533f33c63.pdf).

### 19 mm key switch (case wall): T

- **Wall hole:** **19.0** V. Some models need a D-cut instead (Alcoswitch 19.3 x 16.3).
- **Size:** bezel about dia 28. Body about dia 22 x 39, up to 51 deep including the solder tabs. Maximum wall thickness 16-19.
- Sources: [Open-Electronics](https://oe2.open-electronics.org/?p=51026), [Sound Imports](https://www.soundimports.eu/en/060-215.html), [Buerklin Alcoswitch](https://www.buerklin.com/en/2-1437597-3/p/19G1492).

### Panel-mount USB-C 5 V input: T (choice open)

- **Option A, Adafruit 4218 round extension:** fits holes of **21.5-27** V, flange dia 29.5 V, walls up to 16 V. It is USB-C to USB-C, so a USB-C power breakout or pigtail is needed inside to reach J_PWR.
- **Option B, ear-mount socket cable (Adafruit 4053/4056 style):** two M3 screws 20 apart, walls up to 6.35 V.
- Sources: [Adafruit 4218](https://www.adafruit.com/products/4218), [Core Electronics (20 mm ears)](https://core-electronics.com.au/panel-mount-cable-usb-c-to-micro-b-male-30cm.html).

### Smaller parts: T

- **12 mm passive buzzer:** dia 12 x 8.5-9.5, pins 7.6 apart (some 6.5). Sources: [Wiltronics](https://www.wiltronics.com.au/product/3795/pcb-mount-piezo-buzzer-12mm/), [Electrokit](https://www.electrokit.com/en/active-piezo-buzzer-90db-8-16vdc-pcb-12x9.5mm).
- **WS2812B:** 5.0 x 5.0 x 1.6 package. On the plates use one of:
  - strip pieces, 10 wide at 16.67 pitch (60 LEDs/m);
  - round breakouts, about dia 10;
  - WS2812D-F5 through-hole LEDs, dia 5 x 8.6.

  Sources: [Maplin](https://pro.maplin.co.uk/products/ws2812b-rgb-programmable-5050-smd-led-plcc-4), [Worldsemi V6](https://www.tinytronics.nl/product_files/000438_WS2812B-V6_datasheet.pdf).
- **SOIC-8 to DIP-8 adapter (W25Q32):** about 12 x 10 (vendors vary from 10 to 15), DIP-8 grid with rows 7.62 apart.
- **DIP-8 socket (24C32):** 10.1 x 10.2 x 4.3, rows 7.62 apart.
- **2.54 headers:** male headers are 2.5 of plastic plus about 6 of pin. Female headers are 8.5 tall.
- **Antenna (optional, DevKitC-32UE):** an RP-SMA bulkhead needs a 6.5 hole (1/4-36 thread). A standard 110 mm rubber duck does **not** fit under the 45 mm lid; use a stubby antenna under 35 mm or a fold-down type.
- **Copper touch pads and test-point loops:** custom, so not covered here.

## 3. Open points

- **DevKit row spacing:** 25.40 is correct for the genuine Espressif DevKitC. Narrow clones use 22.86. Decide whether to buy only the genuine board or lay out both rows on the carrier.
- **Panel size:** the 1520 gives a 452 x 321 panel with a 422.6 x 291.2 clear opening, larger than the 370-400 x 260-300 in the brief.
- **Lid height:** the 45.5 mm lid caps everything above the plates at about 35 mm. Banana leads must come out before the case closes, and the antenna must be a stubby type.
- **Not verified:**
  - the 1520PF insert thread;
  - the exact 1520 interior corner radius and floor size;
  - the KY-040 PCB hole positions;
  - the OLED window offsets;
  - the TM1637 0.56 in hole positions;
  - the keypad key pitch;
  - the SG90 ear-hole spacing;
  - the binding post and key switch depths, and the USB-C inside depth.
