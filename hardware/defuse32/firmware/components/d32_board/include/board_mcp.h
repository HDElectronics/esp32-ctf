/* MCP23017 x2 (U2 0x20, U3 0x21). 16-bit port values: low byte = GPA,
 * high byte = GPB (pin numbers as BOARD_MCP_GPA/GPB in board.h).
 *
 * Pin modes set at init (SPEC rev 1b):
 *   U2  GPA0-3 inputs+pull-ups (keypad rows), GPA4-6 + GPB6 strobes (keypad
 *       columns COL1-4), GPB0-5 inputs+pull-ups (Simon, key switch, SD_DET),
 *       GPA7 + GPB7 spare outputs.
 *   U3  GPA0-4 + GPB6 strobes (wire posts WA1-6), GPA5/6 inputs+pull-ups
 *       (encoder B/A), GPB0-5 inputs+pull-ups (wire posts WB1-6), GPA7 + GPB7
 *       spare outputs.
 * GPA7/GPB7 are output-only on current silicon: they are never made inputs
 * and never used as strobes (board_mcp_port() masks them).
 * Interrupts: IOCON MIRROR=1, ODR=1 (INTA/INTB wired-OR to GPIO35),
 * interrupt-on-change on every input pin. Idle state: all strobes driven low
 * (same level, so no two strobes can fight), so a key press or a wire change
 * raises the interrupt. */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BOARD_MCP_U2 = 0,
    BOARD_MCP_U3 = 1,
    BOARD_MCP_COUNT
} board_mcp_t;

/* MCP23017 registers, IOCON.BANK = 0 (A at even, B at odd addresses). */
#define MCP_REG_IODIRA   0x00
#define MCP_REG_IPOLA    0x02
#define MCP_REG_GPINTENA 0x04
#define MCP_REG_DEFVALA  0x06
#define MCP_REG_INTCONA  0x08
#define MCP_REG_IOCON    0x0A
#define MCP_REG_GPPUA    0x0C
#define MCP_REG_INTFA    0x0E
#define MCP_REG_INTCAPA  0x10
#define MCP_REG_GPIOA    0x12
#define MCP_REG_OLATA    0x14

esp_err_t board_mcp_init(void);
void board_mcp_deinit(void);
bool board_mcp_present(board_mcp_t m);

/* Lock for multi-step sequences (scans); the single calls below lock too. */
void board_mcp_lock(void);
void board_mcp_unlock(void);

/* Read GPIOA+GPIOB (also clears a pending interrupt). */
esp_err_t board_mcp_read(board_mcp_t m, uint16_t *value);
/* Read INTF + INTCAP (which pins changed, their level at the interrupt). */
esp_err_t board_mcp_read_int(board_mcp_t m, uint16_t *intf, uint16_t *intcap);
/* Set one output pin (must be an output in the current mode). */
esp_err_t board_mcp_set_pin(board_mcp_t m, int pin, bool level);
/* Set the direction and latch of the pins in `mask` (both ports; latch
 * first, then direction, to avoid glitches). Other pins keep their state.
 * GPA7/GPB7 always stay outputs. Shadowed: only changed bytes are written. */
esp_err_t board_mcp_port(board_mcp_t m, uint16_t mask, uint16_t iodir, uint16_t olat);
/* Raw register access (16-bit pairs: reg = the A register). */
esp_err_t board_mcp_write16(board_mcp_t m, uint8_t reg, uint16_t value);
esp_err_t board_mcp_read16(board_mcp_t m, uint8_t reg, uint16_t *value);

/* GPIO35 interrupt line: true while low (a change is pending). */
bool board_mcp_int_pending(void);
/* Wait for a falling edge on GPIO35; false on timeout or if not set up. */
bool board_mcp_wait_int(uint32_t timeout_ms);

#ifdef __cplusplus
}
#endif
