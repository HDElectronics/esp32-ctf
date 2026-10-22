idf_component_register(SRCS "board.c" "board_i2c.c" "board_mcp.c" "board_input.c"
                            "board_tm1637.c" "board_oled.c" "board_font5x7.c" "board_leds.c"
                            "board_pwm.c" "board_touch.c" "board_ir.c" "board_ldr.c"
                            "board_lis3dh.c" "board_tilt.c" "board_sd.c" "board_uart2.c" "board_nfc.c"
                       INCLUDE_DIRS "include"
                       REQUIRES esp_driver_gpio esp_driver_i2c
                       PRIV_REQUIRES esp_driver_ledc esp_driver_rmt esp_driver_touch_sens
                                     esp_driver_uart esp_driver_spi esp_driver_sdspi esp_adc
                                     fatfs sdmmc esp_timer esp_rom freertos log)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror=implicit-function-declaration)
