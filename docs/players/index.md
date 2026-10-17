# Player guides

One page per track: how to reach it, then every challenge with its points, the
kit it needs (if any), a short teaser and the tools that fit it best. The
guides tell you what each challenge is, not how to solve it; for that there are
the in-game hints (`hint <id>`, then `hint <id> yes`, 25% of the points).

| Track | Guide | Challenges | Points | Mode |
|-------|-------|-----------:|-------:|------|
| Bluetooth Low Energy | [ble.md](ble.md) | 11 | 2000 | radio |
| Bluetooth Classic | [btc.md](btc.md) | 3 | 500 | radio |
| Wi-Fi and web | [web.md](web.md) | 9 | 1500 | net |
| Serial | [serial.md](serial.md) | 4 | 800 | always |
| Hardware pins | [hw.md](hw.md) | 6 | 1000 | always |
| Firmware reversing | [re.md](re.md) | 4 | 900 | always |
| Crypto | [crypto.md](crypto.md) | 3 | 600 | always |

Total 7300 points, 6400 without the optional kit.

## Before you start

1. Flash the board (see the [README](../../README.md#quick-start)).
2. Open the serial console at 115200 baud (see [serial.md](serial.md#connecting)).
   Most tracks use it for submitting flags, hints and clues.
3. `help` lists every command, `status` shows your score and solved
   challenges per track, `list [track]` lists challenges with points and state.

## Common commands

| Command | Does |
|---------|------|
| `submit <flag>` | submit any challenge's flag (`ESP{…}` or the bare 12-character body, any case) |
| `answer <id> <value>` | for challenges whose answer is a value rather than a flag |
| `hint <id>` / `hint <id> yes` | show a hint's cost / reveal it (once, -25% of its points) |
| `mode radio` / `mode net` | switch radio mode (BLE, BTC) or net mode (WEB); reboots |
| `reset yes` | wipe all progress and start over |

## Optional kit

SER-02 needs a USB-UART adapter, HW-01 a jumper wire, HW-03, HW-04 and HW-05 a
logic analyzer. These are marked **Kit** in the guides and in `list`. Skip them
if you don't have the hardware; everything else works with a laptop and a phone.

## Scope

Everything targets your board. No challenge involves any other network or
device; keep your tools pointed at the board only.

## Tools

The [README Toolbox](../../README.md#toolbox) lists the recommended tools per
track with install commands. Each challenge below names the one or two that fit
best.
