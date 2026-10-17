# HW track solvers

Python 3 + pyserial (`pip install pyserial`, or the ESP-IDF python env).
All scripts default to `--port /dev/ttyACM0` and submit the recovered flag with
the console `submit` command (success = "Correct!" or "Already solved").
Offline decoder checks: `hw02_morse.py --selftest`, `hw04_i2c.py --selftest`,
`hw05_spi.py --selftest`.

Pin map: jumper GPIO26 -> GPIO33, LED GPIO2, PWM GPIO25, I2C SDA21/SCL22,
SPI SCK18/MOSI23/CS5, touch pads A=GPIO4 (T0), B=GPIO13 (T4), C=GPIO27 (T7),
D=GPIO32 (T9).

## Dev self-test build (not for release)

`CONFIG_CTF_HW_DEV=y` (menuconfig: "CTF hardware track") adds `hwdev`:

| Command | Prints |
|---------|--------|
| `hwdev` | derived PWM Hz, LEDC Hz, PCNT-measured Hz on GPIO25, touch code, touch baselines, Morse length |
| `hwdev touch [s]` | raw/smooth/threshold per pad once a second (default 10 s) |
| `hwdev morse [s]` | samples the LED pin, prints `[hwdev] m <level> <ms>` runs (default 65 s) |
| `hwdev bus` | PCNT counts of SCL/SCK clock edges over 10.5 s (163 per I2C frame, 136 per SPI frame) and the last burst durations |

`hw02_morse.py --dev` and `hw03_pwm.py --dev` use these to solve without
external kit.

## HW-01 Jumper it (jumper wire)

1. Power off or keep running; put a jumper wire between GPIO26 and GPIO33.
2. `python3 hw01_jumper.py` (resets the board over RTS and reads the boot log).
   Without the jumper the log says `pin check GPIO26->GPIO33: open`.

## HW-02 Blinky Morse (eyes / phone camera)

The LED on GPIO2 blinks the 12-char flag body at 12 WPM (unit 100 ms: dot 1,
dash 3, gaps 1/3, then 7 units + 2 s pause before it repeats; ~21 s per loop).

1. Film the LED for ~45 s (slow motion helps), step through the frames and
   note `on <ms>` / `off <ms>` lines in a text file (one full loop at least).
2. `python3 hw02_morse.py durations.txt`

## HW-03 PWM frequency (logic analyzer)

Analyzer GND -> GND, D0 -> GPIO25.

    sigrok-cli -d fx2lafw --config samplerate=1m --samples 1m -C D0 -O csv > pwm.csv
    python3 hw03_pwm.py --csv pwm.csv --rate 1000000
    # or measure in PulseView and pass the number:
    python3 hw03_pwm.py 4321

The answer gate accepts +-1%.

## HW-04 I2C chatter (logic analyzer)

D0 -> GPIO22 (SCL), D1 -> GPIO21 (SDA), GND -> GND. ~50 kHz, one write to
0x5A every 5 s, nobody ACKs.

    sigrok-cli -d fx2lafw --config samplerate=1m --time 6s -C D0,D1 \
        -P i2c:scl=D0:sda=D1 -A i2c=address-write:data-write > i2c.txt
    python3 hw04_i2c.py --annotations i2c.txt
    # or raw samples:
    sigrok-cli -d fx2lafw --config samplerate=1m --time 6s -C D0,D1 -O csv > i2c.csv
    python3 hw04_i2c.py i2c.csv --scl D0 --sda D1

## HW-05 SPI dump (logic analyzer)

D0 -> GPIO18 (SCK), D1 -> GPIO23 (MOSI), D2 -> GPIO5 (CS, active low),
GND -> GND. Mode 0, ~100 kHz, one 17-byte frame every 10 s.

    sigrok-cli -d fx2lafw --config samplerate=1m --time 11s -C D0,D1,D2 \
        -P spi:clk=D0:mosi=D1:cs=D2:cpol=0:cpha=0 -A spi=mosi-data > spi.txt
    python3 hw05_spi.py --annotations spi.txt
    # or raw samples:
    sigrok-cli -d fx2lafw --config samplerate=1m --time 11s -C D0,D1,D2 -O csv > spi.csv
    python3 hw05_spi.py spi.csv --sck D0 --mosi D1 --cs D2

## HW-06 Touch pad code (fingers)

Touch thresholds are calibrated at boot, so do not touch the pads while the
board boots.

1. `python3 hw06_keypad.py` prints the `keypad` clue and the decoded sequence
   (clue number in base 4, 6 digits, A=0 B=1 C=2 D=3).
2. Touch the bare pins in that order, one at a time, at most 3 s apart.
   The board prints `HW-06 flag: ...`; the script submits it.
   If nothing happens, check `hwdev touch` on a dev build: the smooth value
   of a touched pad must drop below the printed threshold (2/3 of baseline).
