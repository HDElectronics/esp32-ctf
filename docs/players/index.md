# Player guides

One page per track: how to reach it, then every challenge with its points, the
kit it needs (if any), a short teaser and the tools that fit it best. The
guides tell you what each challenge is, not how to solve it; for that there are
the in-game hints (three tiers per challenge, see [Points and hints](#points-and-hints)).

| Track | Guide | Challenges | Points | Mode | Interface |
|-------|-------|-----------:|-------:|------|-----------|
| Bluetooth Low Energy | [ble.md](ble.md) | 11 | 2000 | radio | GATT, advertising |
| Bluetooth Classic | [btc.md](btc.md) | 3 | 500 | radio | inquiry, SPP |
| Wi-Fi and web | [web.md](web.md) | 9 | 1500 | net | SoftAP, HTTP, WebSocket, mDNS, UDP |
| Serial | [serial.md](serial.md) | 4 | 800 | always | USB console, UART2 |
| Hardware pins | [hw.md](hw.md) | 6 | 1000 | always | LED, GPIO, touch pads |
| Firmware reversing | [re.md](re.md) | 4 | 900 | always | flash dump, console |
| Crypto | [crypto.md](crypto.md) | 3 | 600 | always | console |

Easy 100, medium 200, hard 300 points. 7300 points to earn, 6400 without the
optional kit; with the 100 you start with, at most 7400.

## Points and hints

- **Points wallet:** every board starts with 100 points. Solving a challenge
  adds its full value; buying a hint subtracts its price.
- **Three hint tiers** per challenge, unlocked in order: 1 Nudge (free), 2 Hint
  (20% of the challenge's points: 20/40/60), 3 Walkthrough (50%: 50/100/150).
  The nudge names no tool, the hint names the technique, the walkthrough goes
  step by step and stops before the flag. You need enough points to buy a
  tier; bought tiers stay unlocked, also after you solve the challenge.

## Two ways to play

- **Console:** `submit <flag>`, `hint <id>` (lists the tiers with their state
  and price), `hint <id> <n>` (shows a free or owned tier, or asks you to
  confirm with `hint <id> <n> yes`), `status` (points and solved challenges).
  BLE (radio mode) and the board's `/submit` page (net mode) take flags too.
- **Player app:** a guide and scoreboard in your browser, served from the repo
  (`python3 -m http.server -d web 8000`, then <http://localhost:8000/app/>).
  It never touches the board: type your board's MAC once, then check flags and
  answers, buy hints and keep your points in the page. Progress stays in your
  browser (Export / Import moves it).

The two scores are separate: the app keeps its own points, the console keeps
the board's. Pick one, or use both.

## Before you start

1. Flash the board (see the [README](../../README.md#quick-start)).
2. Open the serial console at 115200 baud (see [serial.md](serial.md#connecting)).
   Most tracks use it for submitting flags, hints and clues.
3. `help` lists every command, `status` shows your points and solved
   challenges per track, `list [track]` lists challenges with points and state.

## Common commands

| Command | Does |
|---------|------|
| `status` | points (started with 100, + solved, - hints), solved challenges per track |
| `submit <flag>` | submit any challenge's flag (`ESP{…}` or the bare 12-character body, any case) |
| `answer <id> <value>` | for challenges whose answer is a value rather than a flag |
| `hint <id>` / `hint <id> <n>` | list the three hint tiers / show tier `n` (paid tiers ask for `hint <id> <n> yes`) |
| `mode radio` / `mode net` | switch radio mode (BLE, BTC) or net mode (WEB); reboots |
| `reset yes` | wipe all progress and start over |

## Optional kit

SER-02 needs a USB-UART adapter, HW-01 a jumper wire, HW-03, HW-04 and HW-05 a
logic analyzer. These are marked **Kit** in the guides and in `list`. Skip them
if you don't have the hardware; everything else works with a laptop and a phone.

## Scope

Every challenge targets the board and nothing else. The board runs its own
access point and Bluetooth services; no challenge asks you to scan, join,
attack or affect any other network or device. Keep tools like `nmap` and
`hashcat` pointed at the board's own address and data. If you play in a room
with other boards, only touch your own.

## Tools

The [Toolbox](../toolbox.md) lists the recommended tools per track with
install commands. Each challenge below names the one or two that fit
best.
