// SPDX-License-Identifier: GPL-3.0-or-later
// 640x480p60 for HSTX as a DMA control-block list. No hardware access in here,
// so test/test_dvi.c runs it on the host.
#pragma once

#include <stdbool.h>
#include <stdint.h>

enum {
    H_ACTIVE = 640, H_FRONT = 16, H_SYNC = 96, H_BACK = 48,
    V_ACTIVE = 480, V_FRONT = 10, V_SYNC = 2, V_BACK = 33,
    H_TOTAL = H_ACTIVE + H_FRONT + H_SYNC + H_BACK,
    V_TOTAL = V_ACTIVE + V_FRONT + V_SYNC + V_BACK,
    // One block per blank line, two per picture line, one to restart the list.
    DVI_BLOCKS = (V_TOTAL - V_ACTIVE) + 2 * V_ACTIVE + 1,
};

#define CMD_RAW        (0x0u << 12)
#define CMD_RAW_REPEAT (0x1u << 12)
#define CMD_TMDS       (0x2u << 12)
#define CMD_NOP        (0xfu << 12)

// Control symbols. Lane 0 carries the syncs (active low); lanes 1 and 2 send 00.
#define CTRL_00 0x354u
#define CTRL_01 0x0abu
#define CTRL_10 0x154u
#define CTRL_11 0x2abu
#define SYNC_WORD(lane0) ((lane0) | CTRL_00 << 10 | CTRL_00 << 20)
#define V0_H0 SYNC_WORD(CTRL_00)
#define V0_H1 SYNC_WORD(CTRL_01)
#define V1_H0 SYNC_WORD(CTRL_10)
#define V1_H1 SYNC_WORD(CTRL_11)

static const uint32_t line_blank[] = {
    CMD_RAW_REPEAT | H_FRONT, V1_H1,
    CMD_RAW_REPEAT | H_SYNC, V1_H0,
    CMD_RAW_REPEAT | (H_BACK + H_ACTIVE), V1_H1,
    CMD_NOP,
};
static const uint32_t line_vsync[] = {
    CMD_RAW_REPEAT | H_FRONT, V0_H1,
    CMD_RAW_REPEAT | H_SYNC, V0_H0,
    CMD_RAW_REPEAT | (H_BACK + H_ACTIVE), V0_H1,
    CMD_NOP,
};
static const uint32_t line_active[] = {
    CMD_RAW_REPEAT | H_FRONT, V1_H1,
    CMD_NOP,
    CMD_RAW_REPEAT | H_SYNC, V1_H0,
    CMD_NOP,
    CMD_RAW_REPEAT | H_BACK, V1_H1,
    CMD_TMDS | H_ACTIVE,
};

// Matches a DMA channel's alias 3 registers; writing read_addr starts the transfer.
typedef struct {
    uint32_t ctrl, write_addr, count, read_addr;
} dma_block_t;

typedef struct {
    uint32_t data_ctrl, fifo;
    uint32_t blank, vsync, active;           // addresses of the lists above
    uint32_t restart_ctrl, restart_reg, list_ptr;
    uint32_t row_words;                      // H_ACTIVE / 4 at 8 bpp
    uint32_t pixel_ctrl;                     // data channel ctrl for picture rows
} dvi_addrs_t;

static inline unsigned dvi_build(dma_block_t *out, const dvi_addrs_t *a,
                                 uint32_t (*row_addr)(unsigned y))
{
    unsigned n = 0;
    for (unsigned line = 0; line < V_TOTAL; line++) {
        bool active = line >= V_TOTAL - V_ACTIVE;
        bool sync = line >= V_FRONT && line < V_FRONT + V_SYNC;
        uint32_t words = active ? sizeof line_active / 4
                                : sync ? sizeof line_vsync / 4 : sizeof line_blank / 4;
        uint32_t from = active ? a->active : sync ? a->vsync : a->blank;
        out[n++] = (dma_block_t){a->data_ctrl, a->fifo, words, from};
        if (active)
            out[n++] = (dma_block_t){a->pixel_ctrl, a->fifo, a->row_words,
                                     row_addr(line - (V_TOTAL - V_ACTIVE))};
    }
    out[n++] = (dma_block_t){a->restart_ctrl, a->restart_reg, 1, a->list_ptr};
    return n;
}

// HSTX output bit to TMDS lane, as routed on the card: CK, D0, D1, D2 from bit 0,
// negative on the even bit. -1 is the clock.
static inline int dvi_lane(unsigned bit)
{
    return (int)(bit / 2) - 1;
}

static inline bool dvi_negative(unsigned bit)
{
    return !(bit & 1);
}

// ---------------------------------------------------------------- HDMI (data islands)
// Each line's blanking is built by the CPU into one of HDMI_SLOTS command lists, so it
// can carry a different data island every line. 525 is a multiple of 15, so a line
// always uses the same slot.
#include "hdmi_packet.h"

enum { HDMI_SLOTS = 15, HDMI_SLOT_WORDS = 52 };

// Line layout (800 pixels): front porch 16, then the hsync pulse (96): island preamble
// 8, island 36, sync 52; back porch 48, ending in the video preamble 8 and guard band 2
// on picture lines; then 640 active. Returns the words used: the DMA block sends
// exactly that many, as NOP padding stalls HSTX (one clock each) and slips the symbols.
// parts: HDMI_ISLAND and HDMI_GUARD, to leave out the data island or the video
// preamble and guard band (bring-up bisection); HDMI_ALL for real HDMI.
enum { HDMI_ISLAND = 1, HDMI_GUARD = 2, HDMI_ALL = 3 };
static inline unsigned hdmi_line_build_parts(uint32_t *slot, unsigned line,
                                             const hdmi_packet_t *p, unsigned parts)
{
    uint32_t *out = slot;
    bool active = line >= V_TOTAL - V_ACTIVE;
    bool vsync = line >= V_FRONT && line < V_FRONT + V_SYNC;
    unsigned idle = vsync ? 1u : 3u;  // wire levels: bit 0 HSYNC, bit 1 VSYNC; low = active
    unsigned sync = idle & ~1u;
    unsigned n = 0;
    out[n++] = CMD_RAW_REPEAT | H_FRONT;
    out[n++] = SYNC_WORD(hdmi_ctrl[idle]);
    if (parts & HDMI_ISLAND) {
        out[n++] = CMD_RAW_REPEAT | 8;
        out[n++] = HDMI_ISLAND_PREAMBLE(sync);
        out[n++] = CMD_RAW | HDMI_ISLAND_WORDS;
        hdmi_island_encode(out + n, p, sync);
        n += HDMI_ISLAND_WORDS;
        out[n++] = CMD_RAW_REPEAT | (H_SYNC - 8 - HDMI_ISLAND_WORDS);
    } else {
        out[n++] = CMD_RAW_REPEAT | H_SYNC;
    }
    out[n++] = SYNC_WORD(hdmi_ctrl[sync]);
    if (active && !(parts & HDMI_GUARD)) {
        out[n++] = CMD_RAW_REPEAT | H_BACK;
        out[n++] = SYNC_WORD(hdmi_ctrl[idle]);
        out[n++] = CMD_TMDS | H_ACTIVE;
    } else if (active) {
        out[n++] = CMD_RAW_REPEAT | (H_BACK - 10);
        out[n++] = SYNC_WORD(hdmi_ctrl[idle]);
        out[n++] = CMD_RAW_REPEAT | 8;
        out[n++] = HDMI_VIDEO_PREAMBLE(idle);
        out[n++] = CMD_RAW | 2;
        out[n++] = HDMI_VIDEO_GUARD;
        out[n++] = HDMI_VIDEO_GUARD;
        out[n++] = CMD_TMDS | H_ACTIVE;
    } else {
        out[n++] = CMD_RAW_REPEAT | (H_BACK + H_ACTIVE);
        out[n++] = SYNC_WORD(hdmi_ctrl[idle]);
    }
    return n;
}

static inline unsigned hdmi_line_build(uint32_t *slot, unsigned line, const hdmi_packet_t *p)
{
    return hdmi_line_build_parts(slot, line, p, HDMI_ALL);
}

// The DMA list for HDMI: per line, its slot, then on picture lines the pixels. Slot
// blocks use slot_ctrl (which raises the line interrupt), pixels use pixel_ctrl.
static inline unsigned hdmi_build(dma_block_t *out, const dvi_addrs_t *a, uint32_t slots,
                                  uint32_t slot_ctrl, uint32_t (*row_addr)(unsigned y),
                                  unsigned parts)
{
    unsigned n = 0;
    hdmi_packet_t p;
    hdmi_packet_null(&p);
    for (unsigned line = 0; line < V_TOTAL; line++) {
        uint32_t slot = slots + (line % HDMI_SLOTS) * HDMI_SLOT_WORDS * 4, scratch[HDMI_SLOT_WORDS];
        uint32_t words = hdmi_line_build_parts(scratch, line, &p, parts);
        out[n++] = (dma_block_t){slot_ctrl, a->fifo, words, slot};
        if (line >= V_TOTAL - V_ACTIVE)
            out[n++] = (dma_block_t){a->pixel_ctrl, a->fifo, a->row_words,
                                     row_addr(line - (V_TOTAL - V_ACTIVE))};
    }
    out[n++] = (dma_block_t){a->restart_ctrl, a->restart_reg, 1, a->list_ptr};
    return n;
}
