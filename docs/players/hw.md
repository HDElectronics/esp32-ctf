# HW track (Hardware pins)

6 challenges, 1000 points. Always on (both modes).

## Reaching the track

Everything happens on the board's pins, its onboard LED and its touch pads.
Results and clues appear on the serial console (see [serial.md](serial.md#connecting)).

Safety: the ESP32 is a 3.3 V part. Never connect 5 V to a GPIO pin; always
connect your analyzer's or adapter's GND to the board's GND; don't short 3V3
or 5V/VIN to GND.

## Pin map

DevKit v1 (38-pin) GPIO numbers. On other DevKits the GPIO numbers are the
same; check your board's silkscreen for where they are.

| Use | Pins |
|-----|------|
| Onboard LED (HW-02) | GPIO2 |
| Jumper (HW-01) | GPIO26, GPIO33 |
| UART2 (SER-02) | TX GPIO17, RX GPIO16 |
| PWM (HW-03) | GPIO25 |
| I2C (HW-04) | SDA GPIO21, SCL GPIO22 |
| SPI (HW-05) | SCK GPIO18, MOSI GPIO23, CS GPIO5 |
| Touch keypad (HW-06) | T0 GPIO4, T4 GPIO13, T7 GPIO27, T9 GPIO32 |

Logic analyzer: a cheap 8-channel 24 MHz FX2-based analyzer works with
sigrok (`sigrok-cli -d fx2lafw`) and PulseView. 1 MHz sample rate is plenty
for this track.

On Debian/Ubuntu, `apt install sigrok-cli pulseview sigrok-firmware-fx2lafw`
already installs the USB permission rules in `/usr/lib/udev/rules.d/`. Don't
download rule files from sigrok.org with `wget`: the site serves an error
page to scripts, and a file of the same name in `/etc/udev/rules.d/` hides the
working one. If `sigrok-cli --scan` lists only the demo device, unplug and
replug the analyzer, then check for such files.

## Challenges

### HW-01 Jumper it (100) · Kit: jumper wire
The board checks something about its own pins when it starts. Skip this one if you don't have a jumper wire.
Tools: a jumper wire, `tio`

### HW-02 Blinky Morse (100)
The onboard LED is trying to tell you something.
Tools: phone slow-motion video, CyberChef

### HW-03 PWM frequency (200) · Kit: logic analyzer
A pin is toggling at a frequency unique to your board. The answer is a number (`answer HW-03 <value>`). Skip this one if you don't have a logic analyzer.
Tools: `PulseView`, `sigrok-cli`

### HW-04 I2C chatter (200) · Kit: logic analyzer
The board talks on an I2C bus to a device that isn't there. Skip this one if you don't have a logic analyzer.
Tools: `sigrok-cli -P i2c`, `PulseView`

### HW-05 SPI dump (200) · Kit: logic analyzer
Something is being sent over SPI every few seconds. Skip this one if you don't have a logic analyzer.
Tools: `sigrok-cli -P spi`, `PulseView`

### HW-06 Touch pad code (200)
Four bare pins are a keypad. You need the code. Don't touch the pads while the board boots.
Tools: your fingers, `tio`
