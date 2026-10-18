# Hardware pins in three minutes

Every gadget with a chip inside uses its pins to blink lights, read buttons and talk to sensors. Watching those pins tells you a lot about what a device is doing. This track uses the board's pins, LED and touch pads, with results on the serial console, in both modes.

## How it works

A **GPIO** (general-purpose input/output) pin is either an output or an input. As an output it drives **high** (3.3 V on the ESP32) or **low** (0 V). As an input it reads which of the two it sees. An input wired to nothing floats and reads at random, so chips add a **pull-up** or **pull-down** resistor that gives it a default.

Stay safe: never connect 5 V to a GPIO pin, always join your tool's GND to the board's GND, and don't short 3V3 or 5V/VIN to GND.

**PWM** (pulse-width modulation) is a pin switching high and low over and over, described by the **frequency** (how many cycles per second, in hertz) and the **duty cycle** (the share of each cycle spent high).

Chips talk over **buses**. Both buses here are clocked: one line ticks, and data is read on each tick.

- **I2C** uses two wires, **SCL** (clock) and **SDA** (data), shared by many devices. Each message starts with the address of the device it is for, and that device acknowledges.
- **SPI** uses a clock (**SCK**), a data line from controller to device (**MOSI**), often one back (**MISO**), and a **chip select** line that goes low to say "this message is for you".

A **logic analyzer** records pins as highs and lows over time, and **protocol decoders** turn the trace back into bytes. Sample at least several times faster than the signal you want to see.

**Capacitive touch** pins sense a finger without any button: it changes the pin's capacitance, and the chip measures that. The chip learns its "untouched" reading when it starts, which is why you keep your hands off the pads while the board boots.

Challenges marked **Kit** need a jumper wire or a logic analyzer; skip them if you don't have one.

## Words you'll meet

**GPIO**: a pin the software can use as an input or an output.

**High / low**: the two logic levels, 3.3 V and 0 V here.

**PWM**: a repeating on/off signal with a frequency and a duty cycle (the share of time spent high).

**I2C**: a two-wire bus (SCL, SDA) where devices have addresses.

**SPI**: a bus with clock, data and chip-select lines.

**Logic analyzer**: a tool that records digital signals for decoding.

## Get set up

**sigrok-cli** (record and decode from the terminal) and **PulseView** (its viewer): `sudo apt install sigrok-cli pulseview sigrok-firmware-fx2lafw`. Plug in the analyzer, then:

```sh
sigrok-cli --scan
```

If it lists only the demo device, replug the analyzer. `pulseview` shows traces and decodes them.

**tio** (the console, where results appear): `sudo apt install tio`, then `tio -b 115200 /dev/ttyUSB0`. Only one program can hold the serial port at a time: close tio before the player app or a script uses it.

## Where to start

Start with **HW-02 Blinky Morse**. No kit needed: the onboard LED is trying to tell you something, and a phone's slow-motion video helps you catch it.
