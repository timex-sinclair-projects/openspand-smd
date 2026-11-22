// SPDX-License-Identifier: GPL-3.0-or-later
// Host test: follows the DMA list as the two channels would, feeds the words to a
// model of the HSTX command expander, and checks every pixel clock of two frames.
#include <assert.h>
#include <stdio.h>

#include "../../pins.h"
#include "../dvi_frame.h"

enum { BLANK = 0x1000, VSYNC = 0x2000, ACTIVE = 0x3000, ROWS = 0x100000,
       FIFO = 0xf000, RESTART = 0xe000, LIST_PTR = 0xd000, DATA = 7, AGAIN = 9 };

static uint32_t row_addr(unsigned y) { return ROWS + y * H_ACTIVE; }

static dma_block_t blocks[DVI_BLOCKS + 1];
static unsigned block, word;
static int frames;

static uint32_t next_word(uint32_t *from)
{
    if (blocks[block].ctrl == AGAIN) {
        assert(blocks[block].write_addr == RESTART && blocks[block].count == 1);
        assert(blocks[block].read_addr == LIST_PTR && block == DVI_BLOCKS - 1);
        block = 0;
        frames++;
    }
    const dma_block_t *b = &blocks[block];
    assert(b->ctrl == DATA && b->write_addr == FIFO);
    uint32_t at = b->read_addr + word * 4, value = 0;
    if (b->read_addr >= ROWS) assert(b->count == H_ACTIVE / 4);
    else if (b->read_addr == BLANK) value = line_blank[word];
    else if (b->read_addr == VSYNC) value = line_vsync[word];
    else { assert(b->read_addr == ACTIVE); value = line_active[word]; }
    if (++word == b->count) { word = 0; block++; }
    *from = at;
    return value;
}

int main(void)
{
    const dvi_addrs_t a = {DATA, FIFO, BLANK, VSYNC, ACTIVE, AGAIN, RESTART, LIST_PTR};
    blocks[DVI_BLOCKS].ctrl = 0xdead;
    assert(dvi_build(blocks, &a, row_addr) == DVI_BLOCKS);
    assert(blocks[DVI_BLOCKS].ctrl == 0xdead);

    const long frame = H_TOTAL * V_TOTAL;
    long clocks = 0, hsync = 0, vsync = 0, pixels = 0;
    while (clocks < 2 * frame) {
        uint32_t at, cmd = next_word(&at);
        assert(at < ROWS); // pixels must never be taken for a command
        unsigned op = cmd & 0xf000, n = cmd & 0xfff;
        if (op == CMD_NOP) continue;
        if (op == CMD_RAW_REPEAT) {
            uint32_t symbol = next_word(&at);
            assert(at < ROWS);
            for (unsigned i = 0; i < n; i++, clocks++) {
                long x = clocks % H_TOTAL, y = clocks / H_TOTAL % V_TOTAL;
                int h = !(x >= H_FRONT && x < H_FRONT + H_SYNC);
                int v = !(y >= V_FRONT && y < V_FRONT + V_SYNC);
                assert(y < V_TOTAL - V_ACTIVE || x < H_TOTAL - H_ACTIVE);
                assert(symbol == (v ? (h ? V1_H1 : V1_H0) : (h ? V0_H1 : V0_H0)));
                hsync += !h;
                vsync += !v;
            }
        } else {
            assert(op == CMD_TMDS && n == H_ACTIVE);
            for (unsigned i = 0; i < n; i += 4, clocks += 4) {
                long x = clocks % H_TOTAL, y = clocks / H_TOTAL % V_TOTAL;
                assert(x == H_TOTAL - H_ACTIVE + (long)i && y >= V_TOTAL - V_ACTIVE);
                next_word(&at);
                assert(at == row_addr((unsigned)(y - (V_TOTAL - V_ACTIVE))) + i);
                pixels += 4;
            }
        }
    }
    assert(clocks == 2 * frame && frames == 1);
    assert(H_TOTAL == 800 && V_TOTAL == 525);
    assert(hsync == 2 * 525 * 96 && vsync == 2 * 2 * 800 && pixels == 2 * 640 * 480);

    // Socket wiring from pins.h: CK-, CK+, D0-, D0+, D1-, D1+, D2-, D2+ from GPIO12.
    const int lanes[8] = {-1, -1, 0, 0, 1, 1, 2, 2};
    for (unsigned bit = 0; bit < 8; bit++) {
        assert(dvi_lane(bit) == lanes[bit]);
        assert(dvi_negative(bit) == (bit % 2 == 0));
    }
    assert(HSTX_PIN_0 == 12 && HSTX_PIN_7 == 19);

    // The patch's address read, over every address and with all other pins both ways.
    const int pin[16] = {Z80_A0, Z80_A1, Z80_A2, Z80_A3, Z80_A4, Z80_A5, Z80_A6, Z80_A7,
                         Z80_A8, Z80_A9, Z80_A10, Z80_A11, Z80_A12, Z80_A13, Z80_A14, Z80_A15};
    uint32_t mask = 0;
    for (int i = 0; i < 16; i++) mask |= 1u << pin[i];
    for (uint32_t addr = 0; addr < 0x10000; addr++) {
        for (int noise = 0; noise < 2; noise++) {
            uint32_t lo = noise ? ~mask : 0, r = 0;
            for (int i = 0; i < 16; i++) lo |= (addr >> i & 1) << pin[i];
            for (int i = 0; i < 32; i++) r |= (lo >> i & 1) << (31 - i);
            assert((uint16_t)(((lo >> Z80_ADDR_LO_SHIFT) & 0xf) | ((r << 4) & 0xfff0)) == addr);
        }
    }
    printf("ok: %ld pixel clocks, lane map, 65536 addresses\n", clocks);
    return 0;
}
