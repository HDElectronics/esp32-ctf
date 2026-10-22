#include "board.h"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static const char *TAG = "board_mcp";

/* IOCON: BANK=0, MIRROR=1 (bit 6), SEQOP=0 (sequential), ODR=1 (bit 2). */
#define MCP_IOCON_VALUE 0x44

typedef struct {
    uint8_t addr;
    const char *name;
    uint16_t iodir;   /* 1 = input */
    uint16_t gppu;
    uint16_t gpinten;
    uint16_t olat;
} mcp_cfg_t;

static const mcp_cfg_t s_cfg[BOARD_MCP_COUNT] = {
    [BOARD_MCP_U2] = {
        .addr = BOARD_I2C_ADDR_MCP_U2, .name = "U2",
        /* A: rows GPA0-3 in, cols GPA4-6 strobes, GPA7 spare output.
         * B: Simon GPB0-3, key switch GPB4, SD_DET GPB5 in; COL4 GPB6 strobe;
         * GPB7 spare output. Strobes idle as outputs driven low. */
        .iodir = 0x3F0F, .gppu = 0x3F0F,
        .gpinten = 0x3F0F,
        .olat = 0x0000,
    },
    [BOARD_MCP_U3] = {
        .addr = BOARD_I2C_ADDR_MCP_U3, .name = "U3",
        /* A: WA1-5 GPA0-4 strobes, encoder B/A GPA5/6 in, GPA7 spare output.
         * B: WB1-6 GPB0-5 in, WA6 GPB6 strobe, GPB7 spare output. */
        .iodir = 0x3F60, .gppu = 0x3F60,
        .gpinten = 0x3F60,
        .olat = 0x0000,
    },
};

static i2c_master_dev_handle_t s_dev[BOARD_MCP_COUNT];
static uint16_t s_iodir[BOARD_MCP_COUNT];
static uint16_t s_olat[BOARD_MCP_COUNT];
static SemaphoreHandle_t s_lock;
static SemaphoreHandle_t s_int_sem;
static bool s_isr_added;

void board_mcp_lock(void)
{
    if (s_lock) {
        xSemaphoreTakeRecursive(s_lock, portMAX_DELAY);
    }
}

void board_mcp_unlock(void)
{
    if (s_lock) {
        xSemaphoreGiveRecursive(s_lock);
    }
}

esp_err_t board_mcp_write16(board_mcp_t m, uint8_t reg, uint16_t value)
{
    if (m >= BOARD_MCP_COUNT || !s_dev[m]) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t d[2] = { (uint8_t)(value & 0xFF), (uint8_t)(value >> 8) };
    board_mcp_lock();
    esp_err_t err = board_i2c_write_reg(s_dev[m], reg, d, 2);
    board_mcp_unlock();
    return err;
}

esp_err_t board_mcp_read16(board_mcp_t m, uint8_t reg, uint16_t *value)
{
    if (m >= BOARD_MCP_COUNT || !s_dev[m]) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t d[2];
    board_mcp_lock();
    esp_err_t err = board_i2c_read_reg(s_dev[m], reg, d, 2);
    board_mcp_unlock();
    if (err == ESP_OK) {
        *value = (uint16_t)(d[0] | (d[1] << 8));
    }
    return err;
}

static void IRAM_ATTR mcp_int_isr(void *arg)
{
    (void)arg;
    BaseType_t woken = pdFALSE;
    if (s_int_sem) {
        xSemaphoreGiveFromISR(s_int_sem, &woken);
    }
    if (woken) {
        portYIELD_FROM_ISR();
    }
}

static esp_err_t mcp_configure(board_mcp_t m)
{
    const mcp_cfg_t *c = &s_cfg[m];
    uint8_t iocon = MCP_IOCON_VALUE;
    esp_err_t err = board_i2c_write_reg(s_dev[m], MCP_REG_IOCON, &iocon, 1);
    /* Latch before direction so outputs come up at their idle level. */
    if (err == ESP_OK) err = board_mcp_write16(m, MCP_REG_OLATA, c->olat);
    if (err == ESP_OK) err = board_mcp_write16(m, MCP_REG_IPOLA, 0x0000);
    if (err == ESP_OK) err = board_mcp_write16(m, MCP_REG_GPPUA, c->gppu);
    if (err == ESP_OK) err = board_mcp_write16(m, MCP_REG_IODIRA, c->iodir);
    if (err == ESP_OK) err = board_mcp_write16(m, MCP_REG_INTCONA, 0x0000); /* compare to previous value */
    if (err == ESP_OK) err = board_mcp_write16(m, MCP_REG_DEFVALA, 0x0000);
    if (err == ESP_OK) err = board_mcp_write16(m, MCP_REG_GPINTENA, c->gpinten);
    if (err == ESP_OK) {
        uint16_t dummy;
        err = board_mcp_read16(m, MCP_REG_GPIOA, &dummy); /* clear any pending interrupt */
    }
    if (err == ESP_OK) {
        s_iodir[m] = c->iodir;
        s_olat[m] = c->olat;
    }
    return err;
}

esp_err_t board_mcp_init(void)
{
    if (!s_lock) {
        s_lock = xSemaphoreCreateRecursiveMutex();
    }
    int found = 0;
    for (int m = 0; m < BOARD_MCP_COUNT; m++) {
        if (s_dev[m]) {
            found++;
            continue;
        }
        if (!board_i2c_ready() || board_i2c_probe(s_cfg[m].addr) != ESP_OK) {
            ESP_LOGW(TAG, "%s (0x%02X) not found", s_cfg[m].name, s_cfg[m].addr);
            continue;
        }
        if (board_i2c_add(s_cfg[m].addr, &s_dev[m]) != ESP_OK) {
            s_dev[m] = NULL;
            continue;
        }
        esp_err_t err = mcp_configure((board_mcp_t)m);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "%s config failed: %s", s_cfg[m].name, esp_err_to_name(err));
            board_i2c_remove(s_dev[m]);
            s_dev[m] = NULL;
            continue;
        }
        found++;
    }

    /* GPIO35: input-only, external 10k pull-up (on 3V3P). */
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << BOARD_PIN_MCP_INT,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = found ? GPIO_INTR_NEGEDGE : GPIO_INTR_DISABLE,
    };
    gpio_config(&io);
    if (found && !s_isr_added) {
        if (!s_int_sem) {
            s_int_sem = xSemaphoreCreateBinary();
        }
        esp_err_t err = gpio_install_isr_service(0);
        if (err == ESP_OK || err == ESP_ERR_INVALID_STATE) { /* already installed is fine */
            s_isr_added = gpio_isr_handler_add(BOARD_PIN_MCP_INT, mcp_int_isr, NULL) == ESP_OK;
        }
    }
    return found == BOARD_MCP_COUNT ? ESP_OK : (found ? ESP_ERR_NOT_FINISHED : ESP_ERR_NOT_FOUND);
}

void board_mcp_deinit(void)
{
    if (s_isr_added) {
        gpio_isr_handler_remove(BOARD_PIN_MCP_INT);
        s_isr_added = false;
    }
    gpio_set_intr_type(BOARD_PIN_MCP_INT, GPIO_INTR_DISABLE);
    for (int m = 0; m < BOARD_MCP_COUNT; m++) {
        if (s_dev[m]) {
            /* Leave the expander quiet: no interrupts, everything (except the
             * output-only pins) back to inputs. */
            board_mcp_write16((board_mcp_t)m, MCP_REG_GPINTENA, 0x0000);
            board_mcp_write16((board_mcp_t)m, MCP_REG_IODIRA, 0x7F7F);
            board_i2c_remove(s_dev[m]);
            s_dev[m] = NULL;
        }
    }
}

bool board_mcp_present(board_mcp_t m)
{
    return m < BOARD_MCP_COUNT && s_dev[m] != NULL;
}

esp_err_t board_mcp_read(board_mcp_t m, uint16_t *value)
{
    return board_mcp_read16(m, MCP_REG_GPIOA, value);
}

esp_err_t board_mcp_read_int(board_mcp_t m, uint16_t *intf, uint16_t *intcap)
{
    esp_err_t err = board_mcp_read16(m, MCP_REG_INTFA, intf);
    if (err == ESP_OK) {
        err = board_mcp_read16(m, MCP_REG_INTCAPA, intcap);
    }
    return err;
}

esp_err_t board_mcp_set_pin(board_mcp_t m, int pin, bool level)
{
    if (m >= BOARD_MCP_COUNT || !s_dev[m] || pin < 0 || pin > 15) {
        return ESP_ERR_INVALID_ARG;
    }
    board_mcp_lock();
    uint16_t v = level ? (uint16_t)(s_olat[m] | (1u << pin)) : (uint16_t)(s_olat[m] & ~(1u << pin));
    uint8_t reg = (uint8_t)(MCP_REG_OLATA + (pin >= 8 ? 1 : 0));
    uint8_t b = (uint8_t)(pin >= 8 ? (v >> 8) : (v & 0xFF));
    esp_err_t err = board_i2c_write_reg(s_dev[m], reg, &b, 1);
    if (err == ESP_OK) {
        s_olat[m] = v;
    }
    board_mcp_unlock();
    return err;
}

esp_err_t board_mcp_port(board_mcp_t m, uint16_t mask, uint16_t iodir, uint16_t olat)
{
    if (m >= BOARD_MCP_COUNT || !s_dev[m]) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t err = ESP_OK;
    board_mcp_lock();
    uint16_t new_olat = (uint16_t)((s_olat[m] & ~mask) | (olat & mask));
    /* Never turn an output-only pin (GPA7/GPB7) into an input. */
    uint16_t new_iodir = (uint16_t)(((s_iodir[m] & ~mask) | (iodir & mask)) & ~BOARD_MCP_OUTPUT_ONLY);
    /* Latch first, then direction (no glitch when a pin becomes an output).
     * Only the bytes that changed are written. */
    for (int half = 0; half < 2 && err == ESP_OK; half++) {
        uint8_t now = (uint8_t)(s_olat[m] >> (8 * half));
        uint8_t want = (uint8_t)(new_olat >> (8 * half));
        if (now != want) {
            err = board_i2c_write_reg(s_dev[m], (uint8_t)(MCP_REG_OLATA + half), &want, 1);
            if (err == ESP_OK) {
                s_olat[m] = (uint16_t)((s_olat[m] & ~(0xFFu << (8 * half))) | ((uint16_t)want << (8 * half)));
            }
        }
    }
    for (int half = 0; half < 2 && err == ESP_OK; half++) {
        uint8_t now = (uint8_t)(s_iodir[m] >> (8 * half));
        uint8_t want = (uint8_t)(new_iodir >> (8 * half));
        if (now != want) {
            err = board_i2c_write_reg(s_dev[m], (uint8_t)(MCP_REG_IODIRA + half), &want, 1);
            if (err == ESP_OK) {
                s_iodir[m] = (uint16_t)((s_iodir[m] & ~(0xFFu << (8 * half))) | ((uint16_t)want << (8 * half)));
            }
        }
    }
    board_mcp_unlock();
    return err;
}

bool board_mcp_int_pending(void)
{
    return (s_dev[BOARD_MCP_U2] || s_dev[BOARD_MCP_U3]) && gpio_get_level(BOARD_PIN_MCP_INT) == 0;
}

bool board_mcp_wait_int(uint32_t timeout_ms)
{
    if (!s_isr_added || !s_int_sem) {
        return false;
    }
    if (board_mcp_int_pending()) {
        return true;
    }
    return xSemaphoreTake(s_int_sem, pdMS_TO_TICKS(timeout_ms)) == pdTRUE;
}
