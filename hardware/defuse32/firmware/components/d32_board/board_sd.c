#include "board.h"

#include <stdio.h>
#include "driver/sdspi_host.h"
#include "driver/spi_common.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"

static const char *TAG = "board_sd";

#define SD_SPI_HOST SPI3_HOST   /* VSPI: native pins 18/23/19 */

static bool s_bus_ready;
static sdmmc_card_t *s_card;

static esp_err_t sd_bus_init(void)
{
    if (s_bus_ready) {
        return ESP_OK;
    }
    spi_bus_config_t bc = {
        .mosi_io_num = BOARD_PIN_SPI_MOSI,
        .miso_io_num = BOARD_PIN_SPI_MISO,
        .sclk_io_num = BOARD_PIN_SPI_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4096,
    };
    esp_err_t err = spi_bus_initialize(SD_SPI_HOST, &bc, SPI_DMA_CH_AUTO);
    if (err == ESP_ERR_INVALID_STATE) {
        err = ESP_OK; /* already initialised by someone else: share it */
    }
    s_bus_ready = (err == ESP_OK);
    return err;
}

esp_err_t board_sd_mount(void)
{
    if (s_card) {
        return ESP_OK;
    }
    esp_err_t err = sd_bus_init();
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "SPI bus: %s", esp_err_to_name(err));
        return err;
    }
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.slot = SD_SPI_HOST;
    host.max_freq_khz = BOARD_SD_FREQ_KHZ;
    sdspi_device_config_t slot = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot.host_id = SD_SPI_HOST;
    slot.gpio_cs = BOARD_PIN_SD_CS;
    esp_vfs_fat_mount_config_t mc = VFS_FAT_MOUNT_DEFAULT_CONFIG();
    mc.format_if_mount_failed = false;
    mc.max_files = 4;
    err = esp_vfs_fat_sdspi_mount(BOARD_SD_MOUNT_POINT, &host, &slot, &mc, &s_card);
    if (err != ESP_OK) {
        s_card = NULL;
        ESP_LOGW(TAG, "mount failed: %s", esp_err_to_name(err));
        return err;
    }
    char info[48];
    board_sd_info(info, sizeof(info));
    ESP_LOGI(TAG, "mounted at %s: %s", BOARD_SD_MOUNT_POINT, info);
    return ESP_OK;
}

void board_sd_park_cs(void)
{
    /* The carrier pulls GPIO2 down (strapping), which would leave the card
     * selected and answering on MISO while players use the probe plate's SPI
     * header. Drive CS high instead whenever the card is not mounted. */
    gpio_reset_pin(BOARD_PIN_SD_CS);
    gpio_set_level(BOARD_PIN_SD_CS, 1);
    gpio_set_direction(BOARD_PIN_SD_CS, GPIO_MODE_OUTPUT);
}

esp_err_t board_sd_unmount(void)
{
    if (!s_card) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t err = esp_vfs_fat_sdcard_unmount(BOARD_SD_MOUNT_POINT, s_card);
    s_card = NULL;
    if (s_bus_ready) {
        spi_bus_free(SD_SPI_HOST);
        s_bus_ready = false;
    }
    board_sd_park_cs();
    return err;
}

bool board_sd_mounted(void)
{
    return s_card != NULL;
}

void board_sd_info(char *buf, int len)
{
    if (!s_card) {
        snprintf(buf, len, "-");
        return;
    }
    uint64_t bytes = (uint64_t)s_card->csd.capacity * s_card->csd.sector_size;
    snprintf(buf, len, "%.8s, %lu MB", s_card->cid.name, (unsigned long)(bytes / (1024 * 1024)));
}
