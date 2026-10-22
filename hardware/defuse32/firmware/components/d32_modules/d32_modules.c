/* Module registry: dispatches the game task's calls to the six adapters,
 * plus the buzzer arbiter shared by the adapters and the game UI. */
#include "d32_modules.h"

#include <stdio.h>

#include "board.h"
#include "d32_mod_internal.h"
#include "esp_log.h"

static const char *TAG = "d32_mod";

static const d32_mod_ops_t *const s_ops[D32_SLOTS] = {
    &d32_mod_radio, &d32_mod_timer, &d32_mod_keypad,
    &d32_mod_wires, &d32_mod_probe, &d32_mod_sensors,
};

static bool s_enabled[D32_SLOTS];
static bool s_known[D32_SLOTS];

/* Two adapters always run, even when their slot is disabled in the pack
 * (they then get a NULL variant): the keypad is the code-entry device for
 * every module, and the wire matrix detects the final wire. */
static bool runs(int slot)
{
    return s_enabled[slot] || slot == D32_M3 || slot == D32_M4;
}

void d32_modules_configure(const d32_config_t *cfg)
{
    for (int i = 0; i < D32_SLOTS; i++) {
        s_enabled[i] = cfg->slot[i].enabled;
        s_known[i] = false;
        const d32_mod_ops_t *o = s_ops[i];
        if (!runs(i) || !o->configure) {
            continue;
        }
        const char *variant = s_enabled[i] ? cfg->slot[i].variant : NULL;
        s_known[i] = o->configure(i, variant);
        if (s_enabled[i] && !s_known[i]) {
            ESP_LOGW(TAG, "%s %s: variant \"%s\" not supported in v0, code via console only",
                     d32_slot_id(i), o->name, variant);
        }
    }
}

void d32_modules_arm(d32_t *d, uint32_t seed)
{
    /* Slot order matters: M4 derives its patch pattern before M5 prints it. */
    for (int i = 0; i < D32_SLOTS; i++) {
        if (runs(i) && s_ops[i]->arm) {
            s_ops[i]->arm(d, i, seed);
        }
    }
}

void d32_modules_poll(d32_t *d, uint32_t now_ms)
{
    for (int i = 0; i < D32_SLOTS; i++) {
        if (runs(i) && s_ops[i]->poll) {
            s_ops[i]->poll(d, i, now_ms);
        }
    }
}

void d32_modules_event(d32_t *d, const d32_event_t *ev, uint32_t now_ms)
{
    for (int i = 0; i < D32_SLOTS; i++) {
        if (runs(i) && s_ops[i]->event) {
            s_ops[i]->event(d, i, ev, now_ms);
        }
    }
}

void d32_modules_reset(void)
{
    for (int i = 0; i < D32_SLOTS; i++) {
        if (runs(i) && s_ops[i]->reset) {
            s_ops[i]->reset(i);
        }
    }
}

void d32_modules_gm_print(const d32_t *d)
{
    for (int i = 0; i < D32_SLOTS; i++) {
        if (runs(i) && s_ops[i]->gm_print) {
            s_ops[i]->gm_print(d, i);
        }
    }
}

bool d32_modules_variant_known(int slot)
{
    return slot >= 0 && slot < D32_SLOTS && s_enabled[slot] && s_known[slot];
}

const d32_mod_ops_t *d32_modules_ops(int slot)
{
    return (slot >= 0 && slot < D32_SLOTS) ? s_ops[slot] : NULL;
}

/* ---- buzzer arbiter ---- */

static d32_buzz_prio_t s_buzz_prio;
static uint32_t s_buzz_end;
static bool s_buzz_on;

static bool sounding(uint32_t now_ms)
{
    return s_buzz_on && (int32_t)(s_buzz_end - now_ms) > 0;
}

bool d32_buzz(d32_buzz_prio_t prio, uint32_t hz, uint32_t ms, uint32_t now_ms)
{
    if (sounding(now_ms) && prio < s_buzz_prio) {
        return false;
    }
    if (board_buzzer_tone(hz, ms) != ESP_OK) {
        return false;
    }
    s_buzz_prio = prio;
    s_buzz_end = now_ms + ms;
    s_buzz_on = true;
    return true;
}

bool d32_buzz_active(d32_buzz_prio_t prio, uint32_t now_ms)
{
    return sounding(now_ms) && s_buzz_prio == prio;
}
