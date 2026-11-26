// SPDX-License-Identifier: GPL-3.0-or-later
// HDMI data island packets for HSTX raw words (lane 0 in bits 0-9, lane 1 in 10-19,
// lane 2 in 20-29, each symbol sent LSB first). No hardware access in here, so
// test/test_hdmi.c runs it on the host.
//
// Written from HDMI 1.3a's description of data islands, checked against two open
// implementations: pico_hdmi (Unlicense) and pico_lib's dvi (MIT, Shuichi TAKANO).
// Nothing is copied from either.
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

// TERC4: the 4-bit data symbols used inside data islands.
static const uint16_t hdmi_terc4[16] = {
    0x29c, 0x263, 0x2e4, 0x2e2, 0x171, 0x11e, 0x18e, 0x13c,
    0x2cc, 0x139, 0x19c, 0x2c6, 0x28e, 0x271, 0x163, 0x2c3,
};

#define HDMI_WORD(l0, l1, l2) ((uint32_t)(l0) | (uint32_t)(l1) << 10 | (uint32_t)(l2) << 20)

// Control symbols, indexed by (C1 << 1) | C0. On lane 0, C0 is HSYNC and C1 VSYNC,
// at their wire levels.
static const uint16_t hdmi_ctrl[4] = {0x354, 0x0ab, 0x154, 0x2ab};

// The 8-pixel preambles before a data island and before active video, and the
// 2-pixel guard bands that open and close them. hv is the sync wire levels.
#define HDMI_ISLAND_PREAMBLE(hv) HDMI_WORD(hdmi_ctrl[hv], 0x0ab, 0x0ab)
#define HDMI_VIDEO_PREAMBLE(hv)  HDMI_WORD(hdmi_ctrl[hv], 0x0ab, 0x354)
#define HDMI_VIDEO_GUARD         HDMI_WORD(0x2cc, 0x133, 0x2cc)
#define HDMI_ISLAND_GUARD(hv)    HDMI_WORD(hdmi_terc4[0xc | (hv)], 0x133, 0x133)

enum { HDMI_ISLAND_WORDS = 36 }; // guard 2, packet 32, guard 2

typedef struct {
    uint8_t header[4];        // HB0..HB2 and the ECC
    uint8_t sub[4][8];        // four subpackets: 7 bytes and the ECC
} hdmi_packet_t;

// BCH ECC over the header (24 bits) and each subpacket (56 bits): the generator is
// x^8 + x^7 + x^6 + 1, taken LSB first, which is a reflected CRC-8 with polynomial
// 0x83, starting at 0.
static inline uint8_t hdmi_bch(const uint8_t *p, unsigned n)
{
    uint8_t crc = 0;
    for (unsigned i = 0; i < n; i++) {
        crc ^= p[i];
        for (int b = 0; b < 8; b++)
            crc = (crc & 1) ? (uint8_t)((crc >> 1) ^ 0x83) : (uint8_t)(crc >> 1);
    }
    return crc;
}

static inline void hdmi_packet_seal(hdmi_packet_t *p)
{
    p->header[3] = hdmi_bch(p->header, 3);
    for (int s = 0; s < 4; s++)
        p->sub[s][7] = hdmi_bch(p->sub[s], 7);
}

// The same ECC a byte at a time, for use once per video line: fill the table with
// hdmi_bch_table_init() first.
static uint8_t hdmi_bch_table[256];

static inline void hdmi_bch_table_init(void)
{
    for (unsigned i = 0; i < 256; i++) {
        uint8_t b = (uint8_t)i;
        hdmi_bch_table[i] = hdmi_bch(&b, 1);
    }
}

static inline __attribute__((always_inline)) uint8_t hdmi_bch_fast(const uint8_t *p, unsigned n)
{
    uint8_t crc = 0;
    for (unsigned i = 0; i < n; i++)
        crc = hdmi_bch_table[crc ^ p[i]];
    return crc;
}

static inline __attribute__((always_inline)) void hdmi_packet_seal_fast(hdmi_packet_t *p)
{
    p->header[3] = hdmi_bch_fast(p->header, 3);
    for (int s = 0; s < 4; s++)
        p->sub[s][7] = hdmi_bch_fast(p->sub[s], 7);
}

// A null packet: HB0 = 0, all zero.
static inline void hdmi_packet_null(hdmi_packet_t *p)
{
    memset(p, 0, sizeof *p);
    hdmi_packet_seal(p);
}

// InfoFrame payload byte n goes to subpacket n / 7, byte n % 7; PB0 is a checksum
// that makes HB0..HB2 and all the payload bytes sum to 0.
static inline void hdmi_infoframe(hdmi_packet_t *p, uint8_t type, uint8_t version,
                                  const uint8_t *pb, unsigned len) // pb = PB1..PBlen
{
    memset(p, 0, sizeof *p);
    p->header[0] = type;
    p->header[1] = version;
    p->header[2] = (uint8_t)len;
    unsigned sum = type + version + len;
    for (unsigned n = 1; n <= len; n++) {
        p->sub[n / 7][n % 7] = pb[n - 1];
        sum += pb[n - 1];
    }
    p->sub[0][0] = (uint8_t)(0x100 - (sum & 0xff));
    hdmi_packet_seal(p);
}

// AVI InfoFrame: RGB full range, 4:3, VIC 1 (640x480p60).
static inline void hdmi_packet_avi(hdmi_packet_t *p)
{
    static const uint8_t pb[13] = {0x10, 0x18, 0x08, 1, 0};
    hdmi_infoframe(p, 0x82, 2, pb, sizeof pb);
}

// Audio InfoFrame: 2-channel PCM, 16-bit, 48 kHz.
static inline void hdmi_packet_audio_info(hdmi_packet_t *p)
{
    static const uint8_t pb[10] = {0x11, 0x0d, 0, 0, 0};
    hdmi_infoframe(p, 0x84, 1, pb, sizeof pb);
}

// Audio Clock Regeneration: the sink makes its audio clock from the TMDS clock as
// f_tmds * N / (128 * CTS). At 25.2 MHz and 48 kHz that's N 6144, CTS 25200.
static inline void hdmi_packet_acr(hdmi_packet_t *p, uint32_t n, uint32_t cts)
{
    memset(p, 0, sizeof *p);
    p->header[0] = 0x01;
    uint8_t sb[7] = {0, (uint8_t)(cts >> 16 & 0x0f), (uint8_t)(cts >> 8), (uint8_t)cts,
                     (uint8_t)(n >> 16 & 0x0f), (uint8_t)(n >> 8), (uint8_t)n};
    for (int s = 0; s < 4; s++)
        memcpy(p->sub[s], sb, 7);
    hdmi_packet_seal(p);
}

static inline unsigned hdmi_parity16(uint16_t v)
{
    v ^= v >> 8; v ^= v >> 4; v ^= v >> 2; v ^= v >> 1;
    return v & 1;
}

// IEC 60958 channel status, one bit per frame of a 192-frame block: consumer use,
// PCM, and in byte 3 the sample rate (0x02 for 48 kHz).
static inline unsigned hdmi_channel_status(unsigned frame)
{
    static const uint8_t cs[5] = {0x04, 0, 0, 0x02, 0};
    unsigned byte = frame / 8;
    return byte < 5 ? (cs[byte] >> (frame % 8)) & 1 : 0;
}

// An Audio Sample packet of n (1..4) stereo 16-bit samples. frame is the IEC 60958
// frame number (0..191) of the first sample; frame 0 of each block gets the B flag.
// Without the ECC: seal it with hdmi_packet_seal or hdmi_packet_seal_fast.
static inline __attribute__((always_inline)) void hdmi_packet_audio_unsealed(
    hdmi_packet_t *p, const int16_t (*lr)[2], unsigned n, unsigned frame)
{
    memset(p, 0, sizeof *p);
    p->header[0] = 0x02;
    p->header[1] = (uint8_t)((1u << n) - 1);  // sample_present; layout 0 (2 channels)
    for (unsigned i = 0; i < n; i++) {
        unsigned f = (frame + i) % 192;
        if (f == 0)
            p->header[2] |= (uint8_t)(0x10 << i);
        unsigned c = hdmi_channel_status(f);
        uint16_t l = (uint16_t)lr[i][0], r = (uint16_t)lr[i][1];
        uint8_t *sb = p->sub[i];
        // 24-bit samples, the 16 bits at the top; V = 0 (valid), U = 0.
        sb[1] = (uint8_t)l; sb[2] = (uint8_t)(l >> 8);
        sb[4] = (uint8_t)r; sb[5] = (uint8_t)(r >> 8);
        unsigned pl = hdmi_parity16(l) ^ c, pr = hdmi_parity16(r) ^ c;
        sb[6] = (uint8_t)(c << 2 | pl << 3 | c << 6 | pr << 7);
    }
}

static inline void hdmi_packet_audio(hdmi_packet_t *p, const int16_t (*lr)[2], unsigned n,
                                     unsigned frame)
{
    hdmi_packet_audio_unsealed(p, lr, n, frame);
    hdmi_packet_seal(p);
}

// Encode a packet into an island: guard, 32 packet pixels, guard. hv is the sync wire
// levels during the island. Lane 0 carries hv, a header bit (bit 2) and bit 3, which
// is 0 on the island's first packet pixel. Lanes 1 and 2 carry the even and odd bits
// of the four subpackets: on pixel k, lane 1 bit s is subpacket s bit 2k and lane 2
// bit s is bit 2k + 1.
static inline void hdmi_island_encode(uint32_t *out, const hdmi_packet_t *p, unsigned hv)
{
    out[0] = out[1] = out[34] = out[35] = HDMI_ISLAND_GUARD(hv);
    for (unsigned k = 0; k < 32; k++) {
        unsigned hb = p->header[k / 8] >> (k % 8) & 1;
        unsigned l0 = hv | hb << 2 | (k ? 8u : 0u);
        unsigned l1 = 0, l2 = 0;
        for (unsigned s = 0; s < 4; s++) {
            unsigned byte = p->sub[s][k / 4], bit = (k % 4) * 2;
            l1 |= (byte >> bit & 1) << s;
            l2 |= (byte >> (bit + 1) & 1) << s;
        }
        out[2 + k] = HDMI_WORD(hdmi_terc4[l0], hdmi_terc4[l1], hdmi_terc4[l2]);
    }
}

// hdmi_island_encode, a byte of all four subpackets at a time: the 32 bits are
// shuffled so each nibble holds one pixel's lane 1 or lane 2 bits.
static inline __attribute__((always_inline)) void hdmi_island_encode_fast(
    uint32_t *out, const hdmi_packet_t *p, unsigned hv)
{
    out[0] = out[1] = out[34] = out[35] = HDMI_ISLAND_GUARD(hv);
    uint32_t *o = out + 2;
    for (unsigned i = 0; i < 8; i++, o += 4) {
        uint32_t v = (uint32_t)p->sub[0][i] | (uint32_t)p->sub[1][i] << 8 |
                     (uint32_t)p->sub[2][i] << 16 | (uint32_t)p->sub[3][i] << 24;
        uint32_t t = (v ^ (v >> 7)) & 0x00aa00aau; v = v ^ t ^ (t << 7);
        t = (v ^ (v >> 14)) & 0x0000ccccu; v = v ^ t ^ (t << 14);
        unsigned hb = p->header[i / 2] >> ((i & 1) * 4);
        unsigned l0 = hv | (i ? 8u : 0u);
        o[0] = HDMI_WORD(hdmi_terc4[l0 | (hb & 1) << 2], hdmi_terc4[v & 15],
                         hdmi_terc4[v >> 8 & 15]);
        l0 = hv | 8u;
        o[1] = HDMI_WORD(hdmi_terc4[l0 | (hb >> 1 & 1) << 2], hdmi_terc4[v >> 16 & 15],
                         hdmi_terc4[v >> 24 & 15]);
        o[2] = HDMI_WORD(hdmi_terc4[l0 | (hb >> 2 & 1) << 2], hdmi_terc4[v >> 4 & 15],
                         hdmi_terc4[v >> 12 & 15]);
        o[3] = HDMI_WORD(hdmi_terc4[l0 | (hb >> 3 & 1) << 2], hdmi_terc4[v >> 20 & 15],
                         hdmi_terc4[v >> 28 & 15]);
    }
}
