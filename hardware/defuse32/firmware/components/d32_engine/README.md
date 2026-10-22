# d32_engine

Portable game engine for the Defuse32 training case. Rules: `hardware/defuse32/FIRMWARE.md`
("Game rules the engine implements"). C11, no IDF/FreeRTOS headers, no heap, no globals:
all state is one `d32_t` the caller owns (about 1.5 KB; static storage is fine). Not thread
safe: call it from one task or behind a mutex. Codes are derived with `ctf_derive`, so call
`ctf_init(mac, backend)` before `d32_arm`.

## API overview (`include/d32_engine.h`)

| Area | Calls |
|---|---|
| Config | `d32_config_default`, `d32_config_sanitize` (returns fields fixed, for a pack warning), `d32_init(d, cfg)`, `d32_set_config` (IDLE only), `d32_config` |
| Round | `d32_arm(d, seed)` (IDLE only; `esp_random()` on the board), `d32_reset` (any phase to IDLE), `d32_tick(d, dt_ms)` |
| Inputs | `d32_submit_code(d, text, &slot)`, `d32_wire_pulled(d, i)`, `d32_tilt(d, now_ms)`, `d32_strike(d, reason)` |
| State | `d32_phase`, `d32_end_reason`, `d32_time_left_ms`, `d32_time_str` (MM:SS, seconds rounded up), `d32_strikes`, `d32_rate_permille` / `d32_rate_ppm`, `d32_slot_state`, `d32_enabled_count`, `d32_disarmed_count`, `d32_score` |
| Fragments | `d32_slot_frags`, `d32_revealed_mask`, `d32_revealed_word` (e.g. `B__E`), `d32_colour_len`, `d32_frag_str` (`"3:L"`) |
| Game master | `d32_code_for(d, slot, out)` and `d32_target_wire(d)`: debug only (console `round codes`), never shown to players |
| Names | `d32_slot_id` (`M1`..`M6`), `d32_slot_name`, `d32_wire_colour`, `d32_phase_name` |
| Events | `d32_poll_event(d, &ev)`, `d32_event_count`, `d32_events_dropped` |

Results: `d32_submit_code` returns `DISARMED`, `ALREADY` (no strike), `REJECTED` (strike),
`INVALID` (not 6 hex chars once whitespace is removed; no strike) or `NOT_ARMED`.
`d32_wire_pulled` returns `EARLY` (strike), `WON`, `LOST`, `INVALID` or `NOT_ARMED`.

Events, in the order they happen: `PHASE`, `DISARMED` (slot + its fragments), `STRIKE`
(reason, strikes, rate), `REJECTED`, `TICK` (displayed second changed; one event per tick
call), `RESULT` (end reason, time left, strikes). A loss queues `STRIKE`/`TICK`, then
`PHASE(LOST)`, then `RESULT`. The ring holds `D32_EVQ_LEN` (32) events; when full, a new
event overwrites the oldest and `d32_events_dropped` grows. `d32_reset` clears the queue
and queues `PHASE(IDLE)`.

## Details

- Time is integer ms. The clock rate is kept in ppm (1000000 = 1x); each strike multiplies
  it by `strike_rate_permille / 1000`, rounded half up to the ppm (1250 → 1250000, 1562500,
  1953125 ppm), capped at 1000x. `d32_tick` carries the sub-ms remainder, so many small
  ticks give exactly the same time as one large tick.
- Codes: first 3 bytes of `ctf_derive("D32:<SEED>:<Mn>:<variant>")` as 6 upper hex, with
  `<SEED>` = 8 upper hex digits. Target wire: `ctf_derive_u32("D32:<SEED>:wire") % 6`.
- Fragments: the letter positions and the enabled slots are shuffled with bytes of
  `ctf_derive("D32:<SEED>:frag")`; letter k goes to slot k mod n. Every letter is on exactly
  one enabled slot; each slot carries floor or ceil of len/n letters (0 to 2 with 3 or more
  modules, more with 1 or 2 modules).
- Training: the timer does not run and strikes are not applied (`REJECTED` is still
  queued for UI feedback). A wrong wire in FINAL still loses.
- Tilt strikes at most once per 5 s, measured from the last tilt that struck.

## Host tests

From the repo root:

```sh
cmake -S hardware/defuse32/firmware/test/host -B build-d32-host
cmake --build build-d32-host
ctest --test-dir build-d32-host --output-on-failure
```

Each group (`config phase timer codes wires frags events`) is its own ctest entry;
`build-d32-host/d32_engine_tests [group]` runs one group or all of them.
