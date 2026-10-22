/* Defuse32 firmware entry point: board bring-up, boot banner, SD + pack,
 * game task, console. */
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "console_cmds.h"
#include "d32_pack.h"
#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_console.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "game.h"

static const char *TAG = "d32";

#define FW_NAME "Defuse32"

static void print_banner(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    uint8_t mac[6] = { 0 };
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    printf("\n==============================================\n");
    printf(" %s firmware %s (ESP-IDF %s)\n", FW_NAME, app->version, app->idf_ver);
    printf(" chip ESP32 rev %d.%d, %d core(s), MAC %02X:%02X:%02X:%02X:%02X:%02X\n",
           chip.revision / 100, chip.revision % 100, chip.cores,
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    printf("==============================================\n");
    board_print_presence();
    printf("==============================================\n");
}

/* Mount the card when DET reports one, or when DET cannot be read (U2 absent). */
static void mount_sd(void)
{
    bool present = false;
    esp_err_t err = board_sd_card_detected(&present);
    if (err == ESP_OK && !present) {
        ESP_LOGI(TAG, "no microSD card inserted");
        return;
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "SD detect unreadable (U2 missing): trying to mount anyway");
    }
    board_sd_mount();
}

/* Boot pack: "default" on the card if present, else the first pack listed,
 * else the built-in default. */
static void load_boot_pack(void)
{
    static d32_pack_t pack;
    static char names[16][D32_PACK_NAME_MAX];
    const char *chosen = D32_PACK_BUILTIN_NAME;
    if (board_sd_mounted()) {
        int n = d32_pack_list(D32_PACK_DIR, names, 16);
        if (n < 0) {
            ESP_LOGW(TAG, "%s not found on the card", D32_PACK_DIR);
        } else if (n > 0) {
            chosen = names[0];
            for (int i = 0; i < n; i++) {
                if (strcmp(names[i], "default") == 0) {
                    chosen = names[i];
                    break;
                }
            }
        }
    }
    if (d32_pack_load(chosen, &pack) != 0) {
        chosen = D32_PACK_BUILTIN_NAME;
        d32_pack_defaults(&pack);
    }
    d32_pack_select(&pack, chosen);
    ESP_LOGI(TAG, "pack: %s (\"%s\" %s)", chosen, pack.title, pack.version);
}

static void start_console(void)
{
    esp_console_repl_t *repl = NULL;
    esp_console_repl_config_t rc = ESP_CONSOLE_REPL_CONFIG_DEFAULT();
    rc.prompt = "d32> ";
    rc.max_cmdline_length = 128;
    esp_console_dev_uart_config_t uc = ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_console_new_repl_uart(&uc, &rc, &repl));
    esp_console_register_help_command();
    console_cmds_register();
    ESP_ERROR_CHECK(esp_console_start_repl(repl));
}

void app_main(void)
{
    board_init();
    print_banner();
    mount_sd();
    load_boot_pack();
    board_leds_clear();
    board_tm1637_text("----", false);

    /* The pack is in RAM now: unmount the card so the shared SPI bus (probe
     * plate header) is quiet during play. `pack list/load` mount it again
     * for the moment they need it. */
    if (board_sd_mounted()) {
        board_sd_unmount();
    }

    /* ---- GAME TASK HOOK: engine + module adapters (main/game.c) ---------- */
    game_init();
    game_start();

    start_console();
}
