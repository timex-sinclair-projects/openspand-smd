// SPDX-License-Identifier: GPL-3.0-or-later
// DVI test at the clocks proposed for the real firmware: 208 MHz system clock, as
// upstream, and HSTX at 126 MHz from PLL_USB. That takes USB's 48 MHz away, so the
// test runs from a fresh boot without stdio and reboots to the console afterwards.
#include "bringup.h"
#include "dvi_frame.h"

#include <stdio.h>

#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/pll.h"
#include "hardware/resets.h"
#include "hardware/structs/bus_ctrl.h"
#include "hardware/structs/hstx_ctrl.h"
#include "hardware/structs/hstx_fifo.h"
#include "hardware/watchdog.h"
#include "pico/stdlib.h"

#define REQUEST_MAGIC 0x44564900u
#define RESULT_MAGIC  0x44564f4bu

static dma_block_t blocks[DVI_BLOCKS];
static const dma_block_t *list_start = blocks;
static uint32_t rows[5][H_ACTIVE / 4];
// 1 bpp test card, rendered as OpenSpand will: a 320 x 240 frame at 1 bit per pixel
// (pixel x in bit 7 - x % 8 of byte x / 8, as in a ZX81 byte), expanded line by line
// into 8 bpp RGB332 buffers just before HSTX needs them, doubled both ways.
// HSTX's own 1 bit mode gives grey, not white: a 1-bit lane is the top bit of 8.
enum { FB_W = H_ACTIVE / 2, FB_H = V_ACTIVE / 2, LINE_BUFS = 4 };
static uint8_t frame1[FB_H][FB_W / 8];
static uint32_t line_buf[LINE_BUFS][H_ACTIVE / 4];
static uint32_t expand[256][4]; // one frame byte -> 16 doubled RGB332 pixels
static uint dvi_control_channel, dvi_data_channel;
static bool one_bpp;
// The command lists are read by DMA every line, so keep them out of flash.
static uint32_t ram_blank[count_of(line_blank)];
static uint32_t ram_vsync[count_of(line_vsync)];
static uint32_t ram_active[count_of(line_active)];

void dvi_request(unsigned seconds, bool one_bit)
{
    watchdog_hw->scratch[0] = REQUEST_MAGIC;
    watchdog_hw->scratch[1] = seconds;
    watchdog_hw->scratch[3] = one_bit;
    watchdog_reboot(0, 0, 10);
    for (;;)
        tight_loop_contents();
}

void dvi_print_last_result(void)
{
    if (watchdog_hw->scratch[0] != RESULT_MAGIC)
        return;
    uint32_t khz = watchdog_hw->scratch[1], centihz = watchdog_hw->scratch[2];
    printf("%s last DVI run: HSTX %lu kHz, %lu.%02lu frames/s (expect 126000 and 60.00)\n",
           khz > 125800 && khz < 126200 && centihz > 5980 && centihz < 6020 ? "PASS" : "FAIL",
           (unsigned long)khz, (unsigned long)(centihz / 100), (unsigned long)(centihz % 100));
}

// RGB332 test card: border, colour bars, grey steps, one-pixel checker.
static void make_rows(void)
{
    static const uint8_t bars[8] = {0xff, 0xfc, 0x1f, 0x1c, 0xe3, 0xe0, 0x03, 0x00};
    static const uint8_t greys[4] = {0x00, 0x49, 0xb6, 0xff};
    for (unsigned kind = 0; kind < count_of(rows); kind++) {
        uint8_t *p = (uint8_t *)rows[kind];
        for (unsigned x = 0; x < H_ACTIVE; x++) {
            uint8_t colour = kind == 1 ? bars[x / 80]
                           : kind == 2 ? greys[x / 160]
                           : kind == 3 ? ((x & 1) ? 0xff : 0)
                           : kind == 4 ? ((x & 1) ? 0 : 0xff)
                           : 0xff;
            p[x] = kind && (x < 2 || x >= H_ACTIVE - 2) ? 0xff : colour;
        }
    }
}

// In ZX81 pixels, before doubling. Top half: white with a 2-pixel black frame and a
// 1-pixel diagonal (straight if the bit order is right). Bottom half: left white,
// right black, then a 1-pixel checker, which doubles to 2 x 2 squares.
static void make_frame1(void)
{
    for (unsigned y = 0; y < FB_H; y++) {
        for (unsigned x = 0; x < FB_W; x++) {
            bool white;
            if (y < 120)
                white = x >= 2 && x < FB_W - 2 && y >= 2 && x != y + 40;
            else if (y < 200)
                white = x < FB_W / 2;
            else
                white = (x ^ y) & 1;
            uint8_t bit = 0x80 >> (x % 8);
            if (white)
                frame1[y][x / 8] |= bit;
            else
                frame1[y][x / 8] &= (uint8_t)~bit;
        }
    }
    for (unsigned b = 0; b < 256; b++) {
        uint8_t *out = (uint8_t *)expand[b];
        for (unsigned i = 0; i < 8; i++)
            out[2 * i] = out[2 * i + 1] = (b & (0x80 >> i)) ? 0xff : 0x00;
    }
}

static void render_line(unsigned fb_y)
{
    uint32_t *out = line_buf[fb_y % LINE_BUFS];
    const uint8_t *in = frame1[fb_y];
    for (unsigned i = 0; i < FB_W / 8; i++, out += 4) {
        const uint32_t *e = expand[in[i]];
        out[0] = e[0]; out[1] = e[1]; out[2] = e[2]; out[3] = e[3];
    }
}

// Output lines 2y and 2y + 1 both show frame line y.
static uint32_t row_addr1(unsigned y)
{
    return (uint32_t)line_buf[(y / 2) % LINE_BUFS];
}

// Only the picture-line blocks raise this, as each finishes loading the FIFO. After
// output line L, line L + 1 is already rendered; render the frame line two ahead.
static void __not_in_flash_func(dvi_line_irq)(void)
{
    dma_hw->ints0 = 1u << dvi_data_channel;
    // The picture block of output line L is block blank + 2L + 1. When it finishes,
    // the control channel has loaded block blank + 2L + 2 or, if it has run ahead, the
    // one after, so it points at blank + 2L + 3 or blank + 2L + 4. After the last line
    // it may already have wrapped to the top of the list.
    const unsigned blank = V_TOTAL - V_ACTIVE;
    unsigned next = ((uint32_t)dma_hw->ch[dvi_control_channel].read_addr - (uint32_t)blocks) /
                    sizeof(dma_block_t);
    unsigned line = next >= blank + 3 ? (next - blank - 3) / 2 : V_ACTIVE - 1;
    if (line >= V_ACTIVE - 1) {
        render_line(0); // vertical blank comes next: get the top of the frame ready
        render_line(1);
    } else if (line & 1) {
        unsigned fb_y = (line + 1) / 2 + 1;
        if (fb_y < FB_H)
            render_line(fb_y);
    }
}

static uint32_t row_addr(unsigned y)
{
    unsigned kind = y < 2 || y >= V_ACTIVE - 2 ? 0
                  : y < 240 ? 1
                  : y < 360 ? 2
                  : 3 + (y & 1);
    return (uint32_t)rows[kind];
}

static void clocks_start(void)
{
    // Do this first: the SDK parks clk_sys on PLL_USB while it retunes PLL_SYS.
    set_sys_clock_khz(208000, true);
    uint32_t sys = clock_get_hz(clk_sys);
    clock_configure(clk_peri, 0, CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS, sys, sys);
    clock_stop(clk_usb);
    clock_stop(clk_adc);
    clock_stop(clk_hstx);
    pll_init(pll_usb, 1, 1008 * MHZ, 4, 2); // 126 MHz
    clock_configure(clk_hstx, 0, CLOCKS_CLK_HSTX_CTRL_AUXSRC_VALUE_CLKSRC_PLL_USB,
                    126 * MHZ, 126 * MHZ);
}

static void hstx_start(void)
{
    reset_block_num(RESET_HSTX);
    unreset_block_num_wait_blocking(RESET_HSTX);

    // RGB332: blue on lane 0, green on 1, red on 2.
    hstx_ctrl_hw->expand_tmds =
        2u << HSTX_CTRL_EXPAND_TMDS_L2_NBITS_LSB | 0u << HSTX_CTRL_EXPAND_TMDS_L2_ROT_LSB |
        2u << HSTX_CTRL_EXPAND_TMDS_L1_NBITS_LSB | 29u << HSTX_CTRL_EXPAND_TMDS_L1_ROT_LSB |
        1u << HSTX_CTRL_EXPAND_TMDS_L0_NBITS_LSB | 26u << HSTX_CTRL_EXPAND_TMDS_L0_ROT_LSB;
    hstx_ctrl_hw->expand_shift =
        4u << HSTX_CTRL_EXPAND_SHIFT_ENC_N_SHIFTS_LSB |
        8u << HSTX_CTRL_EXPAND_SHIFT_ENC_SHIFT_LSB |
        1u << HSTX_CTRL_EXPAND_SHIFT_RAW_N_SHIFTS_LSB |
        0u << HSTX_CTRL_EXPAND_SHIFT_RAW_SHIFT_LSB;
    hstx_ctrl_hw->csr = 0;
    hstx_ctrl_hw->csr = HSTX_CTRL_CSR_EXPAND_EN_BITS | 5u << HSTX_CTRL_CSR_CLKDIV_LSB |
                        5u << HSTX_CTRL_CSR_N_SHIFTS_LSB | 2u << HSTX_CTRL_CSR_SHIFT_LSB |
                        HSTX_CTRL_CSR_EN_BITS;

    for (unsigned bit = 0; bit < 8; bit++) {
        int lane = dvi_lane(bit);
        uint32_t config = lane < 0 ? HSTX_CTRL_BIT0_CLK_BITS
                                   : (uint32_t)(lane * 10) << HSTX_CTRL_BIT0_SEL_P_LSB |
                                     (uint32_t)(lane * 10 + 1) << HSTX_CTRL_BIT0_SEL_N_LSB;
        if (dvi_negative(bit))
            config |= HSTX_CTRL_BIT0_INV_BITS;
        hstx_ctrl_hw->bit[bit] = config;
    }
}

static uint dma_start(void)
{
    uint control = dma_claim_unused_channel(true);
    uint data = dma_claim_unused_channel(true);

    dvi_control_channel = control;
    dvi_data_channel = data;
    dma_channel_config d = dma_channel_get_default_config(data);
    channel_config_set_dreq(&d, DREQ_HSTX);
    channel_config_set_chain_to(&d, control);
    channel_config_set_high_priority(&d, true);
    channel_config_set_irq_quiet(&d, true);
    dma_channel_config pixels = d;
    channel_config_set_irq_quiet(&pixels, !one_bpp);

    dma_channel_config restart = dma_channel_get_default_config(data); // chains to itself: none
    channel_config_set_read_increment(&restart, false);
    channel_config_set_high_priority(&restart, true);

    for (unsigned i = 0; i < count_of(line_blank); i++) ram_blank[i] = line_blank[i];
    for (unsigned i = 0; i < count_of(line_vsync); i++) ram_vsync[i] = line_vsync[i];
    for (unsigned i = 0; i < count_of(line_active); i++) ram_active[i] = line_active[i];

    const dvi_addrs_t addrs = {
        .data_ctrl = channel_config_get_ctrl_value(&d),
        .fifo = (uint32_t)&hstx_fifo_hw->fifo,
        .blank = (uint32_t)ram_blank,
        .vsync = (uint32_t)ram_vsync,
        .active = (uint32_t)ram_active,
        .restart_ctrl = channel_config_get_ctrl_value(&restart),
        .restart_reg = (uint32_t)&dma_hw->ch[control].al3_read_addr_trig,
        .list_ptr = (uint32_t)&list_start,
        .row_words = H_ACTIVE / 4,
        .pixel_ctrl = channel_config_get_ctrl_value(&pixels),
    };
    if (one_bpp) {
        make_frame1();
        render_line(0);
        render_line(1);
        dvi_build(blocks, &addrs, row_addr1);
        dma_channel_set_irq0_enabled(data, true);
        irq_set_exclusive_handler(DMA_IRQ_0, dvi_line_irq);
        irq_set_priority(DMA_IRQ_0, 0);
        irq_set_enabled(DMA_IRQ_0, true);
    } else {
        make_rows();
        dvi_build(blocks, &addrs, row_addr);
    }

    dma_channel_config c = dma_channel_get_default_config(control);
    channel_config_set_write_increment(&c, true);
    channel_config_set_ring(&c, true, 4); // the four alias 3 registers
    channel_config_set_high_priority(&c, true);
    bus_ctrl_hw->priority = BUSCTRL_BUS_PRIORITY_DMA_R_BITS | BUSCTRL_BUS_PRIORITY_DMA_W_BITS;
    dma_channel_configure(control, &c, &dma_hw->ch[data].al3_ctrl, blocks, 4, true);
    return control;
}

// The control channel's read address falls back to the top once per frame.
static uint32_t measure_centihz(uint control)
{
    uint32_t last = dma_hw->ch[control].read_addr, wraps = 0;
    uint64_t first = 0, latest = 0;
    absolute_time_t end = make_timeout_time_ms(2000);
    while (!time_reached(end)) {
        uint32_t now = dma_hw->ch[control].read_addr;
        if (now < last) {
            latest = time_us_64();
            if (!wraps++)
                first = latest;
        }
        last = now;
    }
    return wraps > 1 ? (uint32_t)((uint64_t)(wraps - 1) * 100000000 / (latest - first)) : 0;
}

void dvi_run_if_requested(void)
{
    if (watchdog_hw->scratch[0] != REQUEST_MAGIC)
        return;
    uint32_t seconds = watchdog_hw->scratch[1];
    one_bpp = watchdog_hw->scratch[3] == 1;
    watchdog_hw->scratch[0] = 0; // a crash from here on boots to the console
    if (seconds < 3 || seconds > 600 || !board_looks_like_v02())
        return;

    clocks_start();
    hstx_start();
    uint control = dma_start();
    for (unsigned pin = HSTX_PIN_0; pin <= HSTX_PIN_7; pin++)
        gpio_set_function(pin, GPIO_FUNC_HSTX);
    gpio_init(LED_GREEN);
    gpio_set_dir(LED_GREEN, GPIO_OUT);
    gpio_put(LED_GREEN, 1);

    uint32_t khz = frequency_count_khz(CLOCKS_FC0_SRC_VALUE_CLK_HSTX);
    uint32_t centihz = measure_centihz(control);
    sleep_ms((seconds - 2) * 1000);

    board_all_inputs();
    watchdog_hw->scratch[1] = khz;
    watchdog_hw->scratch[2] = centihz;
    watchdog_hw->scratch[0] = RESULT_MAGIC;
    watchdog_reboot(0, 0, 10);
    for (;;)
        tight_loop_contents();
}
