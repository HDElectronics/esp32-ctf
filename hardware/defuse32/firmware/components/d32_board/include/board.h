/* Defuse32 carrier board: pin map, device addresses, init/teardown and the
 * device presence table. Authoritative source: hardware/defuse32/SPEC.md
 * (rev 1b pin map; rev 2 carrier: LIS3DH tilt sensor). Every driver tolerates its device being absent: it probes at init,
 * logs once, and afterwards returns an error (ESP_ERR_INVALID_STATE) without
 * blocking or crashing.
 *
 * Including this header pulls in every driver header. */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ---- ESP32 GPIOs (SPEC "ESP32 pin map", rev 1b) ------------------------ */
#define BOARD_PIN_I2C_SDA       GPIO_NUM_21   /* carrier I2C bus (4.7k to 3V3P) */
#define BOARD_PIN_I2C_SCL       GPIO_NUM_22
#define BOARD_PIN_MCP_INT       GPIO_NUM_35   /* U2/U3 INTA/INTB mirrored, open-drain, wired-OR; input-only, 10k pull-up */
#define BOARD_PIN_ENC_SW        GPIO_NUM_39   /* rev 1b: KY-040 switch, active low; input-only, 10k pull-up to 3V3P.
                                                 LIS3DH INT pins are not connected: it is polled over I2C */
#define BOARD_PIN_IR            GPIO_NUM_34   /* VS1838B out, active low; input-only, 10k pull-up */
#define BOARD_PIN_LDR           GPIO_NUM_36   /* VP, ADC1_CH0; LDR 3V3P->pin, 10k pin->GND */
#define BOARD_PIN_TM_CLK        GPIO_NUM_32   /* TM1637 CLK (timer plate) */
#define BOARD_PIN_TM_DIO        GPIO_NUM_33   /* TM1637 DIO */
#define BOARD_PIN_LED_DATA      GPIO_NUM_25   /* WS2812 chain via U4 74AHCT125 */
#define BOARD_PIN_BUZZER        GPIO_NUM_26   /* passive buzzer via Q1 (high = current) */
#define BOARD_PIN_SERVO         GPIO_NUM_27   /* SG90 signal */
#define BOARD_PIN_TOUCH_T0      GPIO_NUM_4    /* touch pad T0 */
#define BOARD_PIN_TOUCH_T4      GPIO_NUM_13   /* touch pad T4 */
#define BOARD_PIN_TOUCH_T6      GPIO_NUM_14   /* touch pad T6 */
#define BOARD_PIN_TOUCH_T3      GPIO_NUM_15   /* touch pad T3 (strapping pin MTDO) */
#define BOARD_PIN_SPI_SCK       GPIO_NUM_18   /* shared VSPI bus: probe-plate W25Q32 + microSD */
#define BOARD_PIN_SPI_MOSI      GPIO_NUM_23
#define BOARD_PIN_SPI_MISO      GPIO_NUM_19
#define BOARD_PIN_FLASH_CS      GPIO_NUM_5    /* W25Q32 CS on the probe plate (kept deselected: input + pull-up) */
#define BOARD_PIN_SD_CS         GPIO_NUM_2    /* rev 1: microSD CS, 10k pull-down on the carrier (strapping) */
#define BOARD_PIN_UART2_TX      GPIO_NUM_17   /* probe plate UART header */
#define BOARD_PIN_UART2_RX      GPIO_NUM_16
/* GPIO12 unused (strapping). 0, 1, 3, 6-11 reserved (boot, console, flash). */

/* Touch channel numbers (classic ESP32: channel n = Tn). */
#define BOARD_TOUCH_CH_T0       0
#define BOARD_TOUCH_CH_T4       4
#define BOARD_TOUCH_CH_T6       6
#define BOARD_TOUCH_CH_T3       3

/* ---- I2C addresses (7-bit) --------------------------------------------- */
#define BOARD_I2C_ADDR_LIS3DH   0x19  /* rev 2: LIS3DH accelerometer (carrier, SA0 high) */
#define BOARD_I2C_ADDR_MCP_U2   0x20  /* keypad, Simon buttons, key switch, SD detect */
#define BOARD_I2C_ADDR_MCP_U3   0x21  /* wire posts, rotary encoder */
#define BOARD_I2C_ADDR_NFC      0x24  /* PN532 V3 (sensor plate) */
#define BOARD_I2C_ADDR_OLED_M1  0x3C  /* SSD1306 0.96" (radio plate) */
#define BOARD_I2C_ADDR_OLED_M3  0x3D  /* SH1106 1.3" (keypad plate) */
#define BOARD_I2C_ADDR_EEPROM   0x50  /* 24C32 in the probe-plate DIP-8 socket */

/* ---- MCP23017 pin numbers: 0-7 = GPA0-7, 8-15 = GPB0-7 ------------------ */
#define BOARD_MCP_GPA(n)        (n)
#define BOARD_MCP_GPB(n)        (8 + (n))

/* U2 (0x20) */
#define BOARD_U2_KP_ROW1        BOARD_MCP_GPA(0)   /* keypad rows: inputs, pull-ups */
#define BOARD_U2_KP_ROW2        BOARD_MCP_GPA(1)
#define BOARD_U2_KP_ROW3        BOARD_MCP_GPA(2)
#define BOARD_U2_KP_ROW4        BOARD_MCP_GPA(3)
#define BOARD_U2_KP_COL1        BOARD_MCP_GPA(4)   /* keypad columns: strobes */
#define BOARD_U2_KP_COL2        BOARD_MCP_GPA(5)
#define BOARD_U2_KP_COL3        BOARD_MCP_GPA(6)
#define BOARD_U2_KP_COL4        BOARD_MCP_GPB(6)   /* rev 1b (was GPA7) */
#define BOARD_U2_SIM1           BOARD_MCP_GPB(0)   /* Simon buttons, active low */
#define BOARD_U2_SIM2           BOARD_MCP_GPB(1)
#define BOARD_U2_SIM3           BOARD_MCP_GPB(2)
#define BOARD_U2_SIM4           BOARD_MCP_GPB(3)
#define BOARD_U2_KEYSW          BOARD_MCP_GPB(4)   /* J_KEY: switch to GND */
#define BOARD_U2_SD_DET         BOARD_MCP_GPB(5)   /* rev 1: microSD DET (was SPARE1) */
#define BOARD_U2_SPARE_A7       BOARD_MCP_GPA(7)   /* J_SPARE, output-only pin */
#define BOARD_U2_SPARE_B7       BOARD_MCP_GPB(7)   /* J_SPARE, output-only pin */

/* U3 (0x21) */
#define BOARD_U3_WA1            BOARD_MCP_GPA(0)   /* wire posts "A": strobes */
#define BOARD_U3_WA2            BOARD_MCP_GPA(1)
#define BOARD_U3_WA3            BOARD_MCP_GPA(2)
#define BOARD_U3_WA4            BOARD_MCP_GPA(3)
#define BOARD_U3_WA5            BOARD_MCP_GPA(4)
#define BOARD_U3_WA6            BOARD_MCP_GPB(6)   /* rev 1b (was GPA7) */
#define BOARD_U3_ENC_B          BOARD_MCP_GPA(5)
#define BOARD_U3_ENC_A          BOARD_MCP_GPA(6)
#define BOARD_U3_WB1            BOARD_MCP_GPB(0)   /* wire posts "B": inputs, pull-ups */
#define BOARD_U3_WB2            BOARD_MCP_GPB(1)
#define BOARD_U3_WB3            BOARD_MCP_GPB(2)
#define BOARD_U3_WB4            BOARD_MCP_GPB(3)
#define BOARD_U3_WB5            BOARD_MCP_GPB(4)
#define BOARD_U3_WB6            BOARD_MCP_GPB(5)
#define BOARD_U3_SPARE_A7       BOARD_MCP_GPA(7)   /* J_SPARE, output-only pin */
#define BOARD_U3_SPARE_B7       BOARD_MCP_GPB(7)   /* J_SPARE, output-only pin */
/* Rev 1b: GPA7/GPB7 cannot go high impedance, so they are never strobes or
 * inputs. The encoder switch moved to GPIO39 (BOARD_PIN_ENC_SW). */
#define BOARD_MCP_OUTPUT_ONLY   0x8080u

/* ---- Bus settings -------------------------------------------------------- */
#define BOARD_I2C_TIMEOUT_MS    20            /* per transaction; never block longer */
#define BOARD_SD_MOUNT_POINT    "/sd"
#define BOARD_SD_FREQ_KHZ       4000          /* shared bus, 120-230 mm of track plus the probe ribbon, no series resistor: 4 MHz */
#define BOARD_UART2_NUM         2

/* ---- Device presence table ---------------------------------------------- */
typedef struct {
    bool i2c_bus;       /* I2C bus up (SDA/SCL idle high, so the 3V3P rail is powered) */
    bool mcp_u2;        /* 0x20 */
    bool mcp_u3;        /* 0x21 */
    bool oled_m1;       /* 0x3C SSD1306 */
    bool oled_m3;       /* 0x3D SH1106 */
    bool lis3dh;        /* 0x19 LIS3DH (WHO_AM_I 0x33) */
    bool nfc;           /* 0x24 PN532 answered (driver is a stub) */
    bool eeprom;        /* 0x50 24C32 */
    bool tm1637;        /* TM1637 acknowledged */
    bool touch;         /* touch controller up and baselines plausible */
    bool ir;            /* RMT RX channel up (receiver itself cannot be probed) */
    bool ldr;           /* ADC channel up */
    bool leds;          /* RMT TX channel up (WS2812 cannot be probed) */
    bool buzzer;        /* LEDC up */
    bool servo;         /* LEDC up */
    bool sd_card;       /* DET says a card is inserted (or U2 absent: unknown, mount tried) */
    bool sd_mounted;    /* FATFS mounted at /sd */
} board_presence_t;

/* Bring the whole board up. Never fails hard: returns ESP_OK even when
 * devices are missing (see board_presence()). */
esp_err_t board_init(void);
/* Tear everything down (reverse order). */
void board_deinit(void);

const board_presence_t *board_presence(void);
/* Print the presence table to stdout. */
void board_print_presence(void);

#ifdef __cplusplus
}
#endif

#include "board_i2c.h"
#include "board_mcp.h"
#include "board_input.h"
#include "board_tm1637.h"
#include "board_oled.h"
#include "board_leds.h"
#include "board_pwm.h"
#include "board_touch.h"
#include "board_ir.h"
#include "board_ldr.h"
#include "board_lis3dh.h"
#include "board_sd.h"
#include "board_uart2.h"
#include "board_nfc.h"
