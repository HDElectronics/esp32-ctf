#include "board.h"

#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"

static const char *TAG = "board_ldr";

#define LDR_UNIT    ADC_UNIT_1
#define LDR_CHANNEL ADC_CHANNEL_0   /* GPIO36 */
#define LDR_ATTEN   ADC_ATTEN_DB_12

static adc_oneshot_unit_handle_t s_adc;
static adc_cali_handle_t s_cali;

esp_err_t board_ldr_init(void)
{
    if (s_adc) {
        return ESP_OK;
    }
    adc_oneshot_unit_init_cfg_t uc = { .unit_id = LDR_UNIT };
    esp_err_t err = adc_oneshot_new_unit(&uc, &s_adc);
    if (err == ESP_OK) {
        adc_oneshot_chan_cfg_t cc = { .atten = LDR_ATTEN, .bitwidth = ADC_BITWIDTH_DEFAULT };
        err = adc_oneshot_config_channel(s_adc, LDR_CHANNEL, &cc);
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "ADC init failed: %s", esp_err_to_name(err));
        board_ldr_deinit();
        return err;
    }
#if ADC_CALI_SCHEME_LINE_FITTING_SUPPORTED
    adc_cali_line_fitting_config_t cal = {
        .unit_id = LDR_UNIT,
        .atten = LDR_ATTEN,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    if (adc_cali_create_scheme_line_fitting(&cal, &s_cali) != ESP_OK) {
        s_cali = NULL; /* no eFuse calibration: raw values only */
    }
#endif
    return ESP_OK;
}

void board_ldr_deinit(void)
{
#if ADC_CALI_SCHEME_LINE_FITTING_SUPPORTED
    if (s_cali) {
        adc_cali_delete_scheme_line_fitting(s_cali);
        s_cali = NULL;
    }
#endif
    if (s_adc) {
        adc_oneshot_del_unit(s_adc);
        s_adc = NULL;
    }
}

bool board_ldr_ready(void)
{
    return s_adc != NULL;
}

esp_err_t board_ldr_read(int *raw, int *mv)
{
    if (!s_adc) {
        return ESP_ERR_INVALID_STATE;
    }
    int r = 0;
    esp_err_t err = adc_oneshot_read(s_adc, LDR_CHANNEL, &r);
    if (err != ESP_OK) {
        return err;
    }
    if (raw) {
        *raw = r;
    }
    if (mv) {
        *mv = -1;
        if (s_cali) {
            int v;
            if (adc_cali_raw_to_voltage(s_cali, r, &v) == ESP_OK) {
                *mv = v;
            }
        }
    }
    return ESP_OK;
}
