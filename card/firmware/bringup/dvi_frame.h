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
            out[n++] = (dma_block_t){a->data_ctrl, a->fifo, H_ACTIVE / 4,
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
