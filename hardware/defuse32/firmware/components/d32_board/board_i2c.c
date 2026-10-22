#include "board.h"

#include "esp_log.h"
#include "esp_rom_sys.h"
#include "sdkconfig.h"

static const char *TAG = "board_i2c";
static i2c_master_bus_handle_t s_bus;

esp_err_t board_i2c_init(void)
{
    if (s_bus) {
        return ESP_OK;
    }
    /* The pull-ups sit on 3V3P (rev 1): with only DevKit USB power the rail is
     * off and both lines read low. Check before touching the bus so no
     * transaction ever waits on a dead bus. */
    gpio_config_t in = {
        .pin_bit_mask = (1ULL << BOARD_PIN_I2C_SDA) | (1ULL << BOARD_PIN_I2C_SCL),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&in);
    esp_rom_delay_us(50);
    int sda = gpio_get_level(BOARD_PIN_I2C_SDA);
    int scl = gpio_get_level(BOARD_PIN_I2C_SCL);
    if (!sda || !scl) {
        ESP_LOGW(TAG, "SDA=%d SCL=%d idle low: 3V3P rail off (5 V input not connected?) or bus held; "
                 "I2C devices disabled", sda, scl);
        return ESP_ERR_INVALID_STATE;
    }

    i2c_master_bus_config_t cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = BOARD_PIN_I2C_SDA,
        .scl_io_num = BOARD_PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        /* External 4.7k pull-ups on 3V3P; internal ones would back-feed it. */
        .flags.enable_internal_pullup = false,
    };
    esp_err_t err = i2c_new_master_bus(&cfg, &s_bus);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_new_master_bus: %s", esp_err_to_name(err));
        s_bus = NULL;
        return err;
    }
    ESP_LOGI(TAG, "bus up on SDA=%d SCL=%d at %d Hz", BOARD_PIN_I2C_SDA, BOARD_PIN_I2C_SCL,
             CONFIG_D32_I2C_FREQ_HZ);
    return ESP_OK;
}

void board_i2c_deinit(void)
{
    if (s_bus) {
        i2c_del_master_bus(s_bus);
        s_bus = NULL;
    }
}

bool board_i2c_ready(void)
{
    return s_bus != NULL;
}

i2c_master_bus_handle_t board_i2c_bus(void)
{
    return s_bus;
}

esp_err_t board_i2c_probe(uint8_t addr)
{
    if (!s_bus) {
        return ESP_ERR_INVALID_STATE;
    }
    return i2c_master_probe(s_bus, addr, BOARD_I2C_TIMEOUT_MS);
}

int board_i2c_scan(uint8_t *found, int max)
{
    if (!s_bus) {
        return -1;
    }
    int n = 0;
    for (uint8_t a = 0x08; a <= 0x77; a++) {
        if (i2c_master_probe(s_bus, a, BOARD_I2C_TIMEOUT_MS) == ESP_OK) {
            if (found && n < max) {
                found[n] = a;
            }
            n++;
        }
    }
    return n;
}

esp_err_t board_i2c_add(uint8_t addr, i2c_master_dev_handle_t *out)
{
    if (!s_bus) {
        return ESP_ERR_INVALID_STATE;
    }
    i2c_device_config_t dc = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = addr,
        .scl_speed_hz = CONFIG_D32_I2C_FREQ_HZ,
    };
    return i2c_master_bus_add_device(s_bus, &dc, out);
}

void board_i2c_remove(i2c_master_dev_handle_t dev)
{
    if (dev) {
        i2c_master_bus_rm_device(dev);
    }
}

esp_err_t board_i2c_write_reg(i2c_master_dev_handle_t dev, uint8_t reg, const uint8_t *data, size_t len)
{
    if (!dev) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t buf[17];
    if (len + 1 > sizeof(buf)) {
        return ESP_ERR_INVALID_SIZE;
    }
    buf[0] = reg;
    for (size_t i = 0; i < len; i++) {
        buf[i + 1] = data[i];
    }
    return i2c_master_transmit(dev, buf, len + 1, BOARD_I2C_TIMEOUT_MS);
}

esp_err_t board_i2c_read_reg(i2c_master_dev_handle_t dev, uint8_t reg, uint8_t *data, size_t len)
{
    if (!dev) {
        return ESP_ERR_INVALID_STATE;
    }
    return i2c_master_transmit_receive(dev, &reg, 1, data, len, BOARD_I2C_TIMEOUT_MS);
}
