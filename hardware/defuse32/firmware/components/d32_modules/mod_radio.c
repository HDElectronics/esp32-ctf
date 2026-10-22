/* M1 radio adapter, v0 PLACEHOLDER.
 *
 * v0 has no radio challenge: the M1 code exists (the engine derives it from
 * the pack variant, "ble-read" by default) but is only visible through the
 * game-master console (`round codes`), and is entered on the keypad or with
 * `code <hex6>` like any other.
 *
 * TODO(M1): the BLE / Wi-Fi challenge ("ble-read" and later variants). It
 * belongs to the board only: advertise / serve from the ESP32 itself, never
 * scan for or connect to other devices or networks. The plate has an SSD1306
 * (0x3C), a KY-040 encoder (U3 GPA5/6, switch on GPIO39) and the two radio
 * link LEDs, all unused in v0. */
#include <stdio.h>
#include <string.h>

#include "d32_mod_internal.h"

static bool r_configure(int slot, const char *variant)
{
    (void)slot;
    (void)variant;
    return false; /* every variant is a placeholder in v0 */
}

static void r_gm_print(const d32_t *d, int slot)
{
    (void)slot;
    if (d32_phase(d) != D32_IDLE) {
        printf("  M1 radio: v0 placeholder, no on-board challenge\n");
    }
}

const d32_mod_ops_t d32_mod_radio = {
    .name = "radio",
    .configure = r_configure,
    .gm_print = r_gm_print,
};
