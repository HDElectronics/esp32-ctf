# SER track (Serial)

4 challenges, 800 points. Always on (both modes).

## Connecting

The console is the board's USB serial port at **115200 baud, 8N1**, no flow control.

| OS | Port |
|----|------|
| Linux | `/dev/ttyUSB0` or `/dev/ttyACM0` (add yourself to the `dialout` group, or `uucp` on Arch) |
| macOS | `/dev/cu.usbserial-*` or `/dev/cu.SLAB_USBtoUART` |
| Windows | `COMn` (Device Manager) |

```sh
tio -b 115200 /dev/ttyUSB0        # quit: ctrl-t q
picocom -b 115200 /dev/ttyUSB0    # quit: ctrl-a ctrl-x
pyserial-miniterm /dev/ttyUSB0 115200
```

Press EN/RST on the board to see the boot log and banner. Some terminals
toggle the DTR/RTS lines when they open the port, which also resets the board;
that is harmless. The console prompt is `ctf> `; `help` lists all commands.

## Challenges

### SER-01 Boot log (100)
The board says a lot when it boots. Did you read all of it?
Tools: `tio` (with logging), `idf.py monitor`

### SER-02 Wrong baud (200) · Kit: USB-UART adapter
The board has a second serial port that nobody connected. Skip this one if you have neither a 3.3 V USB-UART adapter nor a logic analyzer (an analyzer on GPIO17 plus GND, with sigrok's UART decoder, works too).
UART2 pins: board TX = GPIO17, board RX = GPIO16; connect GND too (see [hw.md](hw.md#pin-map)).
Tools: `tio`, `picocom`; with an analyzer: `sigrok-cli -P uart`, `PulseView`

### SER-03 Debug login (300)
A debug login with a per-board password. Guessing by hand is hopeless. Needs scripting.
Tools: `pwntools`, `pyserial`

### SER-04 Escape sequence (200)
Some consoles hide a back door behind the right keys.
Tools: `picocom`, `pwntools`
