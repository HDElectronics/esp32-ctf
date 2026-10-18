# Player app

A static page that is the CTF's guide and scoreboard (SPEC "Player app —
offline guide and scoreboard"). It never opens the board's port: players use
their own serial terminal and tools, type their board's MAC once, and check
flags, buy hints and keep their points in the page. No build step: HTML, CSS
and ES modules, no third-party scripts (fonts from Google Fonts).

## Run it locally

```sh
python3 -m http.server -d web 8000
```

Then open <http://localhost:8000/app/>. Flag checks use WebCrypto, which needs
a secure page: `localhost` counts, a LAN IP over plain HTTP does not.

- Progress is kept in `localStorage` per board MAC (`esp32ctf:v1:<MACHEX>`),
  with the last board remembered. Progress, Export / Import moves it as
  `esp32-ctf-ESP32-CTF-XXXX.json`. If the browser blocks storage the page
  works in memory and says so.
- The page's score is separate from the board's own console score
  (`status`, `submit`, `hint`), which keeps working without the page.

Query parameters, handy for screenshots: `mac=240AC4000000` (open that board),
`sel=BLE-03`, `tab=web` (or `all`), `primer=ble`, `menu=progress`,
`screen=setup`.

## Files

- `index.html`, `app.css`: both screens (Setup, Play), design tokens
- `js/main.js`: state, rendering, actions (hints, flags, answers, Progress menu)
- `js/engine.js`: flag / answer checks with WebCrypto, the same derivation as `ctf_core`
- `js/store.js`: points wallet and per-board progress in `localStorage`, export / import
- `js/markdown.js`: primer renderer
- `content/board-data.json`: flag key, catalogue, hint texts and prices,
  answer gates; generated from the firmware sources (`ctf_core.c`,
  `ctf_core.h`, `ctf_catalog.c`, `track_hw.c`)
- `content/challenges.json`: briefs and tools, generated from `docs/players/*.md`
- `content/primers/<track>.md`: one short primer per track

Both JSON files come from `scripts/build-app-content.py` (do not edit them by
hand; `--check` fails when they are stale).

## Tests

```sh
node --test web/app/tests/*.test.mjs
```

`engine.test.mjs` also checks real boards when `.cache/real-boards.local.json`
(git-ignored, or a path in `$CTF_REAL_BOARDS`) lists them:
`{"boards":[{"mac":"24:0A:C4:12:34:56","flags":{"SER-01":"ESP{…}"},"hw03":1028}]}`,
with the flags copied from each board's boot banner (`selftest token …`).
Without it that test is skipped.

`scripts/release.sh` copies this folder into the hosted site as `app/`, next
to the flasher page.
