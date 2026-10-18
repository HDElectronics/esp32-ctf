# Serial in three minutes

A serial port is the simplest way two chips can talk: bytes sent one bit at a time down a wire. Routers, 3D printers and almost every embedded board have one, often as a few unlabelled pads for logs and a debug shell. On this board the serial console is the home base: it prints the boot log, takes your commands and accepts flags. It works in both modes.

## How it works

The usual kind of serial port is a **UART**. It needs three wires: **TX** (transmit), **RX** (receive) and **GND** (a shared ground). TX on one side goes to RX on the other, and the grounds must be joined, otherwise the voltages mean nothing. The ESP32 works at 3.3 V, so any adapter you wire to its pins must use 3.3 V levels, not 5 V.

Your laptop has no UART pins, so boards like this one carry a **USB-to-serial bridge** chip. Plug in the USB cable and the bridge appears as a port: `/dev/ttyUSB0` or `/dev/ttyACM0` on Linux, `/dev/cu.usbserial-*` on macOS, `COMn` on Windows. On Linux, add yourself to the `dialout` group (`uucp` on Arch) to open it without root.

A UART has no clock wire. Both sides agree in advance on a speed, the **baud rate**, measured in bits per second, and each side times the bits on its own. A byte travels as a start bit, eight data bits and a stop bit, the frame known as **8N1**. If the two speeds differ, the receiver samples at the wrong moments and reads the wrong bits. You see garbage: random symbols, odd accented letters, or nothing useful at all. Common speeds include 9600, 57600 and 115200.

What you type is sent byte by byte, and keys like Enter and Backspace are bytes too. Terminal programs keep one key combination for their own menu, which is also how you quit them.

Only one program can hold a serial port at a time. Close your terminal before running esptool, a script or the player app on the same port, and close those before opening the terminal again.

## Words you'll meet

**UART**: the hardware that sends and receives serial bytes.

**TX / RX**: the transmit and receive lines; one side's TX goes to the other's RX.

**Baud rate**: the agreed speed in bits per second, 115200 for this console.

**8N1**: 8 data bits, no parity bit, 1 stop bit, the most common frame.

**Console**: a text interface on a serial port, here with the prompt `ctf> `.

**DTR / RTS**: control lines; on dev boards they can reset the chip when a terminal opens the port.

## Get set up

**tio** (a modern serial terminal): `sudo apt install tio`

```sh
tio -b 115200 /dev/ttyUSB0
```

Quit with `ctrl-t q`. Add `--log --log-file session.log` to keep a copy of everything you see.

**picocom** (small and plain): `sudo apt install picocom`, then `picocom -b 115200 /dev/ttyUSB0`. Quit with `ctrl-a ctrl-x`.

**pyserial** (Python, for scripts): `pipx install pyserial` gives you `pyserial-miniterm /dev/ttyUSB0 115200`. For your own scripts, `pip install pyserial` in a virtual environment, then `import serial`.

## Where to start

Start with **SER-01 Boot log**. The board says a lot when it boots: press EN/RST with the console open, and read all of it.
