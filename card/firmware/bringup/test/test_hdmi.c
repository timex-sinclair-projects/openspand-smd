// SPDX-License-Identifier: GPL-3.0-or-later
// Host test for hdmi_packet.h: cc -std=c11 -Wall -o build/test_hdmi test/test_hdmi.c
#include <stdio.h>
#include <stdlib.h>
#include "../dvi_frame.h"

static int fails;
#define CHECK(c, ...) do { if (!(c)) { fails++; printf("FAIL %s:%d: ", __FILE__, __LINE__); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

// TERC4 codes are balanced or nearly, and all distinct from each other and from the
// control and guard symbols.
static void test_terc4(void)
{
    for (int i = 0; i < 16; i++) {
        int ones = __builtin_popcount(hdmi_terc4[i]);
        CHECK(ones >= 4 && ones <= 6, "terc4[%d] has %d ones", i, ones);
        for (int j = 0; j < i; j++)
            CHECK(hdmi_terc4[i] != hdmi_terc4[j], "terc4 %d == %d", i, j);
        for (int c = 0; c < 4; c++)
            CHECK(hdmi_terc4[i] != hdmi_ctrl[c], "terc4[%d] is a control symbol", i);
    }
    CHECK(hdmi_terc4[8] == 0x2cc, "video guard is TERC4 8");
}

// Single-byte BCH values, as in the table both reference implementations carry.
static void test_bch(void)
{
    static const struct { uint8_t in, out; } t[] = {
        {1, 0xd9}, {2, 0xb5}, {4, 0x6d}, {8, 0xda}, {16, 0xb3}, {32, 0x61}, {64, 0xc2},
        {128, 0x83}, {3, 0x6c}, {7, 0x01},
    };
    for (unsigned i = 0; i < sizeof t / sizeof t[0]; i++)
        CHECK(hdmi_bch(&t[i].in, 1) == t[i].out, "bch(%u) = %02x, want %02x", t[i].in,
              hdmi_bch(&t[i].in, 1), t[i].out);
    // A codeword followed by its ECC leaves no remainder.
    uint8_t w[8] = {0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde};
    w[7] = hdmi_bch(w, 7);
    CHECK(hdmi_bch(w, 8) == 0, "codeword remainder %02x", hdmi_bch(w, 8));
}

static void test_infoframes(void)
{
    hdmi_packet_t p;
    hdmi_packet_avi(&p);
    unsigned sum = p.header[0] + p.header[1] + p.header[2];
    for (unsigned n = 0; n <= 13; n++)
        sum += p.sub[n / 7][n % 7];
    CHECK((sum & 0xff) == 0, "AVI checksum sum %02x", sum & 0xff);
    CHECK(p.sub[0][4] == 1, "AVI VIC");
    hdmi_packet_audio_info(&p);
    sum = p.header[0] + p.header[1] + p.header[2];
    for (unsigned n = 0; n <= 10; n++)
        sum += p.sub[n / 7][n % 7];
    CHECK((sum & 0xff) == 0, "audio InfoFrame checksum sum %02x", sum & 0xff);
    hdmi_packet_acr(&p, 6144, 25200);
    CHECK(p.sub[2][2] == 0x62 && p.sub[2][3] == 0x70 && p.sub[2][5] == 0x18 &&
          p.sub[2][6] == 0x00, "ACR bytes");
    CHECK(25200000ull * 6144 / (128 * 25200) == 48000, "N/CTS give 48 kHz");
}

static void test_audio(void)
{
    hdmi_packet_t p;
    int16_t lr[3][2] = {{0x1234, -2}, {0, 1}, {-32768, 32767}};
    hdmi_packet_audio(&p, lr, 3, 190);
    CHECK(p.header[1] == 0x07, "sample_present %02x", p.header[1]);
    CHECK(p.header[2] == 0x40, "B flag on sample 2 (frame 0): %02x", p.header[2]);
    for (int s = 0; s < 3; s++) {
        // Each subframe, V U C P and the sample, has even parity.
        unsigned l = (uint16_t)lr[s][0], r = (uint16_t)lr[s][1], f = p.sub[s][6];
        CHECK(((__builtin_popcount(l) + __builtin_popcount(f & 0x0f)) & 1) == 0, "L parity %d", s);
        CHECK(((__builtin_popcount(r) + __builtin_popcount(f & 0xf0)) & 1) == 0, "R parity %d", s);
        CHECK(p.sub[s][0] == 0 && p.sub[s][3] == 0, "low sample bytes zero");
    }
    CHECK(p.sub[3][6] == 0 && p.sub[3][1] == 0, "unused subpacket empty");
    CHECK(hdmi_channel_status(2) == 1 && hdmi_channel_status(25) == 1 &&
          hdmi_channel_status(24) == 0 && hdmi_channel_status(191) == 0, "channel status");
}

// The lane 1/2 mapping, done the way pico_hdmi does it (byte-wise bit shuffle), must
// agree with the bit-by-bit version in hdmi_island_encode.
static void test_island(void)
{
    hdmi_packet_t p;
    srand(1);
    for (int trial = 0; trial < 100; trial++) {
        for (int i = 0; i < 3; i++)
            p.header[i] = (uint8_t)rand();
        for (int s = 0; s < 4; s++)
            for (int i = 0; i < 7; i++)
                p.sub[s][i] = (uint8_t)rand();
        hdmi_packet_seal(&p);
        unsigned hv = (unsigned)trial & 3;
        uint32_t w[HDMI_ISLAND_WORDS];
        hdmi_island_encode(w, &p, hv);
        for (int i = 0; i < 8; i++) {
            uint32_t v = (uint32_t)p.sub[0][i] | (uint32_t)p.sub[1][i] << 8 |
                         (uint32_t)p.sub[2][i] << 16 | (uint32_t)p.sub[3][i] << 24;
            uint32_t t = (v ^ (v >> 7)) & 0x00aa00aa; v = v ^ t ^ (t << 7);
            t = (v ^ (v >> 14)) & 0x0000cccc; v = v ^ t ^ (t << 14);
            unsigned l1[4] = {v & 15, v >> 16 & 15, v >> 4 & 15, v >> 20 & 15};
            unsigned l2[4] = {v >> 8 & 15, v >> 24 & 15, v >> 12 & 15, v >> 28 & 15};
            for (int j = 0; j < 4; j++) {
                uint32_t word = w[2 + i * 4 + j];
                CHECK((word >> 10 & 0x3ff) == hdmi_terc4[l1[j]], "lane 1 byte %d pixel %d", i, j);
                CHECK((word >> 20 & 0x3ff) == hdmi_terc4[l2[j]], "lane 2 byte %d pixel %d", i, j);
            }
        }
        for (int k = 0; k < 32; k++) {
            unsigned want = hv | (p.header[k / 8] >> (k % 8) & 1) << 2 | (k ? 8 : 0);
            CHECK((w[2 + k] & 0x3ff) == hdmi_terc4[want], "lane 0 pixel %d", k);
        }
        CHECK(w[0] == HDMI_ISLAND_GUARD(hv) && w[35] == HDMI_ISLAND_GUARD(hv), "guards");
        if (fails)
            break;
    }
}

// Walk a line's command list as the HSTX expander would: every line is 800 pixels,
// with active video (TMDS) starting at pixel 160 on picture lines, and the island
// inside the hsync pulse.
static void test_lines(void)
{
    hdmi_packet_t p;
    hdmi_packet_null(&p);
    for (unsigned parts = 0; parts <= HDMI_ALL; parts++)
    for (unsigned line = 0; line < V_TOTAL; line++) {
        uint32_t w[HDMI_SLOT_WORDS];
        unsigned used = hdmi_line_build_parts(w, line, &p, parts);
        CHECK(used <= HDMI_SLOT_WORDS, "line %u uses %u words", line, used);
        unsigned px = 0, i = 0, tmds_at = 0, island_at = 0;
        bool vsync = line >= V_FRONT && line < V_FRONT + V_SYNC;
        while (i < used) {
            uint32_t cmd = w[i++], op = cmd >> 12, len = cmd & 0xfff;
            CHECK(op != 0xf, "line %u: NOP in a slot", line);
            if (op == 0) {           // raw: len data words
                if (len == HDMI_ISLAND_WORDS)
                    island_at = px;
                i += len; px += len;
            } else if (op == 1) {    // raw repeat: one data word
                uint32_t d = w[i++];
                unsigned c = d & 0x3ff;
                bool in_sync = px >= H_FRONT && px < H_FRONT + H_SYNC;
                // Control periods carry the right sync levels on lane 0.
                if ((d >> 10 & 0x3ff) == 0x354 && (d >> 20 & 0x3ff) == 0x354)
                    CHECK(c == hdmi_ctrl[(vsync ? 0u : 2u) | (in_sync ? 0u : 1u)],
                          "line %u px %u sync levels", line, px);
                px += len;
            } else if (op == 2) {    // TMDS from the pixel block
                tmds_at = px;
                px += len;
            }
        }
        CHECK(px == H_TOTAL && i == used, "line %u is %u pixels", line, px);
        CHECK(island_at == ((parts & HDMI_ISLAND) ? H_FRONT + 8 : 0), "line %u island at %u",
              line, island_at);
        if (line >= V_TOTAL - V_ACTIVE) {
            CHECK(tmds_at == H_TOTAL - H_ACTIVE, "line %u video at %u", line, tmds_at);
            CHECK(w[used - 1] == (CMD_TMDS | H_ACTIVE),
                  "line %u: the TMDS command must be the slot's last word", line);
        }
        if (fails)
            break;
    }
}

int main(void)
{
    test_lines();
    test_terc4();
    test_bch();
    test_infoframes();
    test_audio();
    test_island();
    if (fails) {
        printf("%d failures\n", fails);
        return 1;
    }
    printf("ok: TERC4, BCH, InfoFrames, ACR, audio samples, island lanes, 525 line lists\n");
    return 0;
}
