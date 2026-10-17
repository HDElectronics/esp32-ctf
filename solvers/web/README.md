# Web reference solvers

One solver per challenge (WEB-01..09). Each recovers the flag over the network
the way a player would, then submits it (`--via console`: serial `submit`;
`--via web`: the board's `/submit` form) and accepts "Correct!" or
"Already solved".

## Setup

```sh
/usr/bin/python3 -m venv .venv && .venv/bin/pip install requests websockets zeroconf pyserial
.venv/bin/python solvers/web/web01_hidden_ssid.py --host 192.168.4.1
```

- Board in net mode (`mode net` on the console).
- Player path: run `wifi` on the console, decode the base32 SSID and join the
  hidden network (`nmcli dev wifi connect <ssid> password <pw> hidden yes`).
  The board is `192.168.4.1` (the default `--host`).
- Dev testing without joining the AP: build with `CONFIG_CTF_WEB_DEV_STA`
  (see `components/track_web/Kconfig`); the board also joins a test network
  and prints `web dev sta ip: x.x.x.x`. Pass that address as `--host`.
- The console helpers open the port with DTR and RTS left asserted: clearing
  them one at a time (DTR first) briefly pulls EN low and reboots the board.
- `--serial` (default `$CTF_PORT` or `/dev/ttyACM0`): console used by WEB-01
  and WEB-09 for the `wifi` clue and by `--via console`.

| Solver | Default submit | Notes |
|--------|----------------|-------|
| `web01_hidden_ssid.py` | web | `wifi` → base32 SSID + password; flag on `/`; prints CRY-01 shard 4 (footer). On a dev image it also checks the decoded SSID against the driver's active AP config |
| `web02_view_source.py` | web | part 1 in the HTML comment on `/`, part 2 at the `/robots.txt` disallowed path (`/staging/`); flag = `ESP{` first 6 hex + last 6 hex `}` |
| `web03_cookie.py` | web | `/` sets `role=guest`; `/admin` with `role=admin` |
| `web04_headers.py` | console | `/api/docs` gives the agent name and board key; `/api/secret` with `User-Agent: ESP32-CTF-Agent` + `X-CTF-Key` |
| `web05_jwt.py` | console | `POST /login user=guest` → HS256 JWT cookie `session`; brute-force the secret over `/wordlist.txt` (1000 words), forge `role: admin`, `GET /vault` with `Authorization: Bearer`; checks `alg: none` is rejected |
| `web06_traversal.py` | console | `/diag?file=../secret/flag.txt`; checks `../../etc/passwd` → 403 (confined to `/storage`) |
| `web07_websocket.py` | console | two clients on `/ws`; text noise every 1 s, binary frame with the flag every 30 s (waits ≤ 40 s) |
| `web08_mdns.py` | console | zeroconf browse `_ctf._tcp.local.` → SRV port + TXT `path`, `GET /` there (`avahi-browse -rt _ctf._tcp`) |
| `web09_knock.py` | console | `wifi` knock hint (hex ports, door `7a69` = 31337); UDP to the 3 ports in order (≤ 5 s apart), then TCP 31337 within 30 s |

## Board side

- SoftAP: hidden SSID `ctf-` + 6 lowercase letters, WPA2-PSK, 12-char password,
  all derived per board (`WEB-01:ssid`, `WEB-01:pass`).
- HTTP :80 (embedded pages), WS `/ws`, mDNS host `esp32-ctf`, service
  `_ctf._tcp` on a per-board port 8000..8999 (`WEB-08:port`).
- WEB-05 wordlist: same on every board (two CV syllables + optional ending,
  generated in code); the secret index is `WEB-05:secret` mod 1000.
- WEB-06: `/storage/diag/{boot,net,ping}.log` and `/storage/secret/flag.txt`
  are written at boot (only when changed). The secret file is stored XOR'd with
  a per-board mask (`WEB-06:mask`), so a flash dump does not show the flag;
  `/diag` unmasks that one path when serving it. The path is the naive concatenation
  `/storage/diag/<file>`, normalised; anything resolving outside `/storage` is 403.
- WEB-09: ports `WEB-09:ports` in 20000..40000. Wrong port resets the sequence
  (the first port restarts it). The door listens only while a window is open
  and serves only the IP that knocked.
