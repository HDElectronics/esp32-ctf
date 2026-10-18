# Bluetooth Classic in three minutes

Bluetooth Classic, also called BR/EDR, is the older and faster half of Bluetooth. Headphones, car kits, game controllers and wireless keyboards use it, because it is good at steady streams of data. The board runs Classic and BLE side by side in radio mode: if `mode` on the console says `net`, run `mode radio` and let it reboot.

## How it works

Finding a Classic device is called an **inquiry**. Your adapter calls out, and every device that is **discoverable** answers. The answer is more than a name: it includes the device's address, its **Class of Device** (a small number that says "phone", "headset", "computer" and so on) and an **extended inquiry response** that can carry a few more fields. This is what your laptop's Bluetooth settings show when you click "add device".

To talk to a device you usually **pair** with it first. Pairing sets up shared keys so the link can be encrypted. Many simple devices pair with no PIN at all; your system just asks you to confirm.

Once paired, you ask the device what it offers. Each device keeps a list of **service records**, and the protocol for asking about them is called **SDP**. A record says, for example, "I offer a serial port, and you'll find it on this RFCOMM channel".

**RFCOMM** is the part of Classic that behaves like a serial cable over radio. The **Serial Port Profile (SPP)** builds on it: open the channel and you get a two-way stream of bytes, exactly like a USB serial console. Anything you would do with a wired console, you can do over SPP: read what it prints, type commands, script it.

One detail helps later: the board uses the same address for BLE and Classic, so BlueZ shows a single device for both. If you see old data after a re-flash, remove the device and scan again.

## Words you'll meet

**BR/EDR**: the official name for Bluetooth Classic (Basic Rate / Enhanced Data Rate).

**Inquiry**: a scan for nearby discoverable Classic devices.

**Class of Device**: a short code that tells others what kind of device this is.

**EIR**: extended inquiry response, extra data a device sends when it answers an inquiry.

**SDP**: the service discovery protocol, used to list what a device offers.

**RFCOMM**: serial-cable emulation over Bluetooth, organised in numbered channels.

**SPP**: the Serial Port Profile, a serial console carried over RFCOMM.

## Get set up

**bluetoothctl** (BlueZ's shell): `sudo apt install bluez`

```sh
bluetoothctl
scan bredr
```

Then `pair <address>` and `info <address>`, which lists the services the device announces.

**bluetuith** (terminal UI for scanning and pairing): `go install github.com/darkhz/bluetuith@latest`, then run `bluetuith`.

**Python sockets** (for scripting an RFCOMM connection): use your distro's own `python3`, because conda and some pyenv builds lack Bluetooth support. Check yours first:

```sh
/usr/bin/python3 -c "import socket; print(socket.AF_BLUETOOTH)"
```

If that prints a number, you are ready. Older guides use `rfcomm`, `hcitool` and `sdptool`; they still work but are legacy and may be missing on new distros.

## Where to start

Start with **BTC-01 SPP console**. The board offers a serial-style console over Bluetooth Classic: find it, pair, and get a terminal on it.
