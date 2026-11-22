// SPDX-License-Identifier: GPL-3.0-or-later
#include "bringup.h"

#include "hardware/gpio.h"
#include "pico/stdlib.h"

static const char *const names[48] = {
#define N(x) [x] = #x
    N(Z80_D0), N(Z80_D1), N(Z80_D2), N(Z80_D3), N(Z80_D4), N(Z80_D5), N(Z80_D6), N(Z80_D7),
    N(Z80_A0), N(Z80_A1), N(Z80_A2), N(Z80_A3), N(Z80_A4), N(Z80_A5), N(Z80_A6), N(Z80_A7),
    N(Z80_A8), N(Z80_A9), N(Z80_A10), N(Z80_A11), N(Z80_A12), N(Z80_A13), N(Z80_A14), N(Z80_A15),
    N(Z80_HALT), N(Z80_MREQ), N(Z80_IORQ), N(Z80_RD), N(Z80_WR), N(Z80_RST), N(Z80_M1), N(Z80_RFSH),
    N(Z80_CLK), N(LED_GREEN), N(I2C_SDA), N(I2C_SCL), N(SD_MISO), N(SD_CS), N(SD_CLK), N(SD_MOSI),
#undef N
    [HSTX_PIN_0] = "TMDS CK-", [HSTX_PIN_1] = "TMDS CK+",
    [HSTX_PIN_2] = "TMDS D0-", [HSTX_PIN_3] = "TMDS D0+",
    [HSTX_PIN_4] = "TMDS D1-", [HSTX_PIN_5] = "TMDS D1+",
    [HSTX_PIN_6] = "TMDS D2-", [HSTX_PIN_7] = "TMDS D2+",
};

const char *board_pin_name(unsigned pin)
{
    return pin < 48 ? names[pin] : "?";
}

void board_all_inputs(void)
{
    for (unsigned pin = 0; pin <= Z80_CLK; pin++) {
        gpio_init(pin); // SIO, input, output value low
        gpio_disable_pulls(pin);
    }
}

// v0.2 has U8's push-pull output on GPIO40. v0.1 and SMD2 have an unconnected UART
// header there, so the pin follows our pulls. This matters because GPIO12..19 are
// DVI on v0.2 but Z80 A4..A11 on the older boards. Only internal pulls are used.
bool board_looks_like_v02(void)
{
    gpio_pull_up(Z80_CLK);
    sleep_ms(2);
    bool followed_up = true;
    for (int i = 0; i < 1000; i++)
        followed_up &= gpio_get(Z80_CLK);

    // RP2350-E9 (A2 silicon): a pull-down only wins while the input buffer is off.
    bool followed_down = true;
    gpio_pull_down(Z80_CLK);
    for (int i = 0; i < 20; i++) {
        gpio_set_input_enabled(Z80_CLK, false);
        sleep_us(100);
        gpio_set_input_enabled(Z80_CLK, true);
        busy_wait_at_least_cycles(4); // input synchroniser
        followed_down &= !gpio_get(Z80_CLK);
    }

    gpio_disable_pulls(Z80_CLK);
    return !(followed_up && followed_down);
}
