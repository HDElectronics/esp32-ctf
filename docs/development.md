# Development and organizer notes

Build from source, dev-only options, the release script and notes for whoever
runs the CTF. Moved here from the README. Spoilers live in
[`solvers/`](../solvers/README.md) and [`docs/SPEC.md`](SPEC.md), not here.

## Building from source

Requires ESP-IDF v6.1 (target `esp32`). The firmware version is 0.2.0
(`PROJECT_VER` in the top-level `CMakeLists.txt`; it also names the release image).

```sh
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

Release image (clean build in `build-release/` from `sdkconfig.defaults` only,
merged `.bin`, ESP Web Tools manifest and a ready-to-host flasher site):

```sh
scripts/release.sh
# -> dist/esp32-ctf-v0.2.0.bin, dist/manifest.json, web/flasher/dist-site/
```

Host unit tests for the portable engine:

```sh
cmake -S test/host -B build-host && cmake --build build-host && ctest --test-dir build-host --output-on-failure
```

Player app (`web/app/`, an offline guide and scoreboard that never opens the
board's port): `web/app/content/board-data.json` (flag key, catalogue, hint
texts and prices, HW-03 gate) is generated from the firmware sources and
`web/app/content/challenges.json` (briefs, tools) from `docs/players/*.md`.
Regenerate after changing the catalogue, hints, key, HW-03 gate or a player
guide, then run its Node tests (see `web/app/README.md`):

```sh
python3 scripts/build-app-content.py          # regenerate both JSON files
python3 scripts/build-app-content.py --check  # fail if they are stale
node --test web/app/tests/*.test.mjs
```

`scripts/release.sh` runs the `--check` and refuses to package stale content.
Run it locally with `python3 -m http.server -d web 8000`, then
<http://localhost:8000/app/>. The firmware also has a machine channel on the
console (`api …` lines framed with SOH/STX/ETX, SPEC "Machine channel"); it
stays in the firmware for tools, but the app does not use it.

Browser flashing: `scripts/release.sh` also builds a self-hostable ESP Web Tools
flasher page in `web/flasher/dist-site/` (desktop Chrome or Edge; Web Serial).

README images: `scripts/render-images.sh` renders `docs/img/src/*.html` with
headless Chrome into `docs/img/*.png` (light and dark). `docs/img/src/i2c.html`
is generated from a sigrok capture by `docs/img/src/make_i2c.py`; the console
text in `docs/img/src/console.html` is a real board session with the MAC
replaced by the example `24:0A:C4:12:34:56`. `scripts/render-images.sh app`
serves the repo on port 8012 and screenshots the real player app, seeded by
`docs/img/src/app-seed.html` (`docs/img/app.png`).

### Dev options

Never enable these in a build you hand to players; `scripts/release.sh`
refuses to package one.

- `CONFIG_CTF_HW_DEV` (`hwdev` command: derived HW values, touch/LED/bus self-tests)
- `CONFIG_CTF_CRYPTO_DEV` (prints the CRY-01 key shards at boot)
- `CONFIG_CTF_WEB_DEV_STA` (+ `_SSID`, `_PASS`): in net mode the board also
  joins a test network so a LAN host can reach the web track. Put the three
  options in a git-ignored overlay, e.g. `sdkconfig.dev.local`:

  ```
  CONFIG_CTF_WEB_DEV_STA=y
  CONFIG_CTF_WEB_DEV_STA_SSID="my-test-net"
  CONFIG_CTF_WEB_DEV_STA_PASS="..."
  ```

  and build it in its own directory:

  ```sh
  idf.py -B build-dev -DSDKCONFIG=build-dev/sdkconfig \
      -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.dev.local" build
  ```

  **The dev image stores that Wi-Fi password in flash, and the RE track
  teaches players to dump flash.** Before a board goes to a player, wipe it
  and flash the release image:
  `esptool --chip esp32 -p <PORT> erase-flash`, then
  `esptool --chip esp32 -p <PORT> write-flash 0x0 dist/esp32-ctf-v0.2.0.bin`.

- `CONFIG_CTF_SIZE_PROBE` (links unused stack stubs to measure image size)

## For organizers

- `solvers/` holds one reference solver per challenge. They are full
  spoilers: do not hand them to players.
- `docs/SPEC.md` describes every challenge's mechanism, also a spoiler.
- `reset yes` on the console wipes all progress and bought hints and reboots;
  the firmware-reversing artefacts are re-provisioned on the next boot.
  Flashing the merged image also wipes progress (it covers the NVS
  partition); a full chip erase (`esptool --chip esp32 erase-flash`) before
  flashing gives a completely fresh board.
- Flags are derived from each board's MAC, so two boards never share flags.
