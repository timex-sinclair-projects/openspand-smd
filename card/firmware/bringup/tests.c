// SPDX-License-Identifier: GPL-3.0-or-later
#include "bringup.h"

#include <stdio.h>

#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/pio.h"
#include "hardware/structs/pads_bank0.h"
#include "pico/stdlib.h"

#define ADDR_EXPANDER 0x27
#define ADDR_EEPROM   0x50
#define ADDR_RTC      0x68
#define I2C_TIMEOUT_US 10000

#define MCP_IODIR 0x00
#define MCP_GPPU  0x06
#define MCP_GPIO  0x09
#define MCP_OLAT  0x0A
#define MCP_LED_RED (1u << 2)

static void i2c_begin(void)
{
    i2c_init(i2c1, 100000);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
}

static bool i2c_get(uint8_t addr, const uint8_t *reg, size_t reg_len, uint8_t *out, size_t len)
{
    return i2c_write_timeout_us(i2c1, addr, reg, reg_len, true, I2C_TIMEOUT_US) == (int)reg_len &&
           i2c_read_timeout_us(i2c1, addr, out, len, false, I2C_TIMEOUT_US) == (int)len;
}

static bool mcp_put(uint8_t reg, uint8_t value)
{
    uint8_t msg[] = {reg, value};
    return i2c_write_timeout_us(i2c1, ADDR_EXPANDER, msg, 2, false, I2C_TIMEOUT_US) == 2;
}

void test_i2c(void)
{
    i2c_begin();
    bool expander = false, eeprom = false, rtc = false;
    for (uint8_t addr = 0x08; addr < 0x78; addr++) {
        uint8_t byte;
        if (i2c_read_timeout_us(i2c1, addr, &byte, 1, false, I2C_TIMEOUT_US) != 1)
            continue;
        printf("  answer at 0x%02x\n", addr);
        expander |= addr == ADDR_EXPANDER;
        eeprom |= addr == ADDR_EEPROM;
        rtc |= addr == ADDR_RTC;
    }
    printf("%s U4 expander (0x27)\n", expander ? "PASS" : "FAIL");
    printf("%s U6 EEPROM (0x50)\n", eeprom ? "PASS" : "FAIL");
    printf("%s U5 clock (0x68)\n", rtc ? "PASS" : "FAIL");
}

void test_rtc(void)
{
    i2c_begin();
    uint8_t reg = 0, before[19], after[19];
    if (!i2c_get(ADDR_RTC, &reg, 1, before, sizeof before)) {
        printf("FAIL U5 doesn't answer\n");
        return;
    }
    sleep_ms(2100);
    if (!i2c_get(ADDR_RTC, &reg, 1, after, sizeof after)) {
        printf("FAIL U5 stopped answering\n");
        return;
    }
    printf("  20%02x-%02x-%02x %02x:%02x:%02x, %d C\n", after[6], after[5] & 0x1f, after[4],
           after[2], after[1], after[0], (int8_t)after[17]);
    if (after[15] & 0x80)
        printf("  oscillator-stop flag set: normal until the time is first set\n");
    printf("%s U5 %s\n", before[0] != after[0] ? "PASS" : "FAIL",
           before[0] != after[0] ? "is counting seconds" : "seconds are not advancing");
}

void test_eeprom(void)
{
    i2c_begin();
    uint8_t where[] = {0, 0}, data[16];
    if (!i2c_get(ADDR_EEPROM, where, 2, data, sizeof data)) {
        printf("FAIL U6 read\n");
        return;
    }
    printf("PASS U6 read (nothing written):");
    for (unsigned i = 0; i < sizeof data; i++)
        printf(" %02x", data[i]);
    printf("\n");
}

void test_leds(void)
{
    i2c_begin();
    // Latch low, then switch GP2 between output (lit) and input (dark).
    bool ok = mcp_put(MCP_OLAT, 0);
    gpio_init(LED_GREEN);
    gpio_set_dir(LED_GREEN, GPIO_OUT);
    for (int i = 0; i < 10; i++) {
        gpio_put(LED_GREEN, !(i & 1));
        ok &= mcp_put(MCP_IODIR, (i & 1) ? 0xff & ~MCP_LED_RED : 0xff);
        sleep_ms(500);
    }
    ok &= mcp_put(MCP_IODIR, 0xff);
    gpio_set_dir(LED_GREEN, GPIO_IN);
    printf("%s expander writes; green and red should have alternated\n", ok ? "PASS" : "FAIL");
}

void test_inputs(void)
{
    static const char *const bit_names[8] = {"CONFIG", "SPI_CS", "LED", "FIRE",
                                             "RIGHT", "LEFT", "DOWN", "UP"};
    i2c_begin();
    if (!mcp_put(MCP_IODIR, 0xff) || !mcp_put(MCP_GPPU, 0xff & ~MCP_LED_RED)) {
        printf("FAIL U4 doesn't answer\n");
        return;
    }
    gpio_pull_up(Z80_RST);
    sleep_ms(250); // C5 is 1 uF
    printf("  20 seconds: press CONFIG and RESET, work the joystick\n");
    absolute_time_t end = make_timeout_time_ms(20000);
    unsigned last = ~0u, seen = 0;
    while (!time_reached(end)) {
        uint8_t reg = MCP_GPIO, value;
        if (!i2c_get(ADDR_EXPANDER, &reg, 1, &value, 1)) {
            printf("FAIL U4 stopped answering\n");
            break;
        }
        unsigned low = (~value & 0xf9u) | (gpio_get(Z80_RST) ? 0 : 0x100u);
        if (low != last) {
            printf(" ");
            for (int bit = 0; bit < 8; bit++)
                if (low & (1u << bit))
                    printf(" %s", bit_names[bit]);
            printf("%s%s\n", low & 0x100 ? " RESET" : "", low ? "" : " (none pressed)");
            last = low;
            seen |= low;
        }
        sleep_ms(10);
    }
    gpio_disable_pulls(Z80_RST);
    printf("%s all seven inputs seen\n", (seen & 0x1f9) == 0x1f9 ? "PASS" : "INCOMPLETE");
}

// Counts rising edges with PIO at GPIO base 16, as the firmware patch does. A WAIT GPIO
// instruction holds the GPIO number modulo 32 (8 for GPIO40); pio_add_program() turns
// that into the index in the window (24). Encoding 24 here would watch GPIO24, A11.
void test_clock(void)
{
    const uint16_t code[] = {
        pio_encode_wait_gpio(false, Z80_CLK & 31u),
        pio_encode_wait_gpio(true, Z80_CLK & 31u),
        pio_encode_jmp_x_dec(0),
    };
    const pio_program_t program = {
        .instructions = code,
        .length = 3,
        .origin = -1,
        .used_gpio_ranges = 0x4,
    };
    PIO pio = pio0;
    if (pio_set_gpio_base(pio, 16) != PICO_OK || !pio_can_add_program(pio, &program)) {
        printf("FAIL can't set up PIO at GPIO base 16\n");
        return;
    }
    uint at = pio_add_program(pio, &program);
    uint sm = pio_claim_unused_sm(pio, true);
    pio_sm_config config = pio_get_default_sm_config();
    sm_config_set_wrap(&config, at, at + 2);
    pio_sm_init(pio, sm, at, &config);
    pio_sm_exec(pio, sm, pio_encode_mov_not(pio_x, pio_null));

    uint64_t start = time_us_64();
    pio_sm_set_enabled(pio, sm, true);
    sleep_ms(1000);
    pio_sm_set_enabled(pio, sm, false);
    uint64_t took = time_us_64() - start;

    pio_sm_exec(pio, sm, pio_encode_mov_not(pio_isr, pio_x));
    pio_sm_exec(pio, sm, pio_encode_push(false, false));
    uint32_t edges = pio_sm_get(pio, sm);
    pio_remove_program(pio, &program, at);
    pio_sm_unclaim(pio, sm);

    uint32_t hz = (uint32_t)((uint64_t)edges * 1000000 / took);
    printf("%s Z80 clock %lu Hz (expect 3250000 with a running ZX81)\n",
           hz > 3217500 && hz < 3282500 ? "PASS" : "FAIL", (unsigned long)hz);
}

void test_bus(void)
{
    uint64_t high = 0, low = 0;
    absolute_time_t end = make_timeout_time_ms(2000);
    while (!time_reached(end)) {
        for (int i = 0; i < 1000; i++) {
            uint64_t now = gpio_get_all64();
            high |= now;
            low |= ~now;
        }
    }
    for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++) {
        if (pin >= HSTX_PIN_0 && pin <= HSTX_PIN_7)
            continue;
        bool h = high >> pin & 1, l = low >> pin & 1;
        printf("  GPIO%-2u %-10s %s\n", pin, board_pin_name(pin),
               h && l ? "active" : h ? "always high" : "always low");
    }
    printf("  With no ROM the Z80 never halts and does no I/O, so HALT and IORQ stay high:\n"
           "  use 'opens' for those. RESET sits high. Any other line that never moves is suspect.\n");
}

// For a bare card on USB. Every line is pulled up, then one at a time is driven low:
// any other line that follows is bridged to it. Refuses to drive if any line is
// already low, which is what an attached ZX81 or display looks like.
void test_shorts(void)
{
    const uint64_t all = (1ull << BUS_AND_HSTX_PINS) - 1;
    for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
        gpio_pull_up(pin);
    sleep_ms(250); // C5 on RESET is 1 uF

    uint64_t idle = all;
    for (int i = 0; i < 100000; i++)
        idle &= gpio_get_all64();

    unsigned faults = 0;
    if (idle != all) {
        for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
            if (!(idle >> pin & 1))
                printf("  GPIO%u %s is low\n", pin, board_pin_name(pin));
        printf("STOP nothing driven: unplug the bus and HDMI, or those are shorts to ground\n");
    } else {
        for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++) {
            gpio_put(pin, 0);
            gpio_set_dir(pin, GPIO_OUT);
            sleep_us(pin == Z80_RST ? 1000 : 20);
            uint64_t got = gpio_get_all64() & all;
            gpio_set_dir(pin, GPIO_IN);
            if (got >> pin & 1) {
                printf("  GPIO%u %s won't go low\n", pin, board_pin_name(pin));
                faults++;
            }
            for (unsigned other = 0; other < BUS_AND_HSTX_PINS; other++) {
                if (other != pin && !(got >> other & 1)) {
                    printf("  %s pulls %s low\n", board_pin_name(pin), board_pin_name(other));
                    faults++;
                }
            }
            sleep_ms(pin == Z80_RST ? 250 : 1);
        }
        printf("%s shorts test, %u faults (it cannot see open joints; use 'bus' for those)\n",
               faults ? "FAIL" : "PASS", faults);
    }
    for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
        gpio_disable_pulls(pin);
}

// In a powered ZX81 (crashed, since the card disables its ROM): tell an open joint from a working one without a meter. Each line
// gets a weak pull-down (about 50k, harmless to the Z80). A connected line is driven
// high by the ZX81 at least some of the time; an open pad follows the pull and never
// reads high. RESET is left alone, because a pull-down there could reset the machine.
// The input buffers are switched off between samples to dodge RP2350-E9.
void test_opens(void)
{
    uint64_t pins = 0;
    for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
        if ((pin < HSTX_PIN_0 || pin > HSTX_PIN_7) && pin != Z80_RST)
            pins |= 1ull << pin;

    for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
        if (pins >> pin & 1)
            gpio_pull_down(pin);

    enum { SAMPLES = 5000 };
    static uint16_t highs[BUS_AND_HSTX_PINS];
    for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
        highs[pin] = 0;
    for (int i = 0; i < SAMPLES; i++) {
        for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
            if (pins >> pin & 1)
                gpio_set_input_enabled(pin, false);
        sleep_us(20 + (i % 37)); // vary the phase against the Z80's cycles
        for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
            if (pins >> pin & 1)
                gpio_set_input_enabled(pin, true);
        // The pad writes go over the slow peripheral bus; reading a pad register back
        // makes sure they have landed before the input synchroniser is sampled.
        (void)*(volatile uint32_t *)&pads_bank0_hw->io[Z80_RFSH];
        busy_wait_at_least_cycles(20);
        uint64_t now = gpio_get_all64();
        for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++)
            if (pins >> pin & now >> pin & 1)
                highs[pin]++;
    }

    unsigned open = 0;
    for (unsigned pin = 0; pin < BUS_AND_HSTX_PINS; pin++) {
        if (!(pins >> pin & 1))
            continue;
        gpio_disable_pulls(pin);
        printf("  GPIO%-2u %-10s high in %3u%% of samples%s\n", pin, board_pin_name(pin),
               highs[pin] * 100u / SAMPLES, highs[pin] ? "" : "  <- follows the pull: OPEN");
        open += !highs[pin];
    }
    printf("%s opens test, %u lines look unconnected (RESET not tested)\n",
           open ? "FAIL" : "PASS", open);
}
