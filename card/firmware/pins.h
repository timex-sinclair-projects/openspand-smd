/*
Copyright 2024-26 by Adam Klotblixt (adam.klotblixt@gmail.com)

This file is part of OpenSpand.

OpenSpand is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

OpenSpand is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
OpenSpand. If not, see <https://www.gnu.org/licenses/>.
*/

/*
    Pin map for the OpenSpand Card rev 0.2 (RP2350B, chip-down, edge-card form
    factor, DVI out on an HDMI socket).

    HSTX, the RP2350's DVI-capable serialiser, only exists on GPIO12..19, so the
    bus is laid out round it:
      GPIO0..7    Z80 D0..D7   (the low byte of gpio_in, as upstream)
      GPIO8..11   Z80 A0..A3
      GPIO12..19  HSTX, TMDS to the HDMI socket (see HSTX_PIN_n)
      GPIO20..31  Z80 A15..A4, reversed to suit the board: z80_addr_get()
                  recovers A4..A15 with one RBIT
      GPIO32..39  Z80 control lines, in edge-finger order
      GPIO40..47  Z80_CLK (buffered) and the 3.3 V peripherals
    The video PIO uses GPIO base 16 so it can see Z80_CLK on GPIO40.

    Not on this board, so deliberately left undefined (any code that still uses
    them fails to build rather than driving a bus pin):
      VIDEO_SYNC, VIDEO_DATA   composite video; replaced by DVI over HSTX
      I2S_PIN_*                the I2S DAC; sound goes out over HDMI instead
      ZX_SER_TX, ZX_SER_RX     the serial port
      LED_RED                  bit 2 (GP2) of the I/O expander at 0x27, active low
*/

#ifndef _PINS_H_
#define _PINS_H_

#define Z80_ADDR_LO_SHIFT    8 // A0..A3 on GPIO8..11
#define Z80_D0               0 // zx-bus 4A
#define Z80_D1               1 // zx-bus 5A
#define Z80_D2               2 // zx-bus 6A
#define Z80_D3               3 // zx-bus 9A
#define Z80_D4               4 // zx-bus 10A
#define Z80_D5               5 // zx-bus 8A
#define Z80_D6               6 // zx-bus 7A
#define Z80_D7               7 // zx-bus 1A
#define Z80_A0               8 // zx-bus 7B
#define Z80_A1               9 // zx-bus 8B
#define Z80_A2              10 // zx-bus 9B
#define Z80_A3              11 // zx-bus 10B
#define HSTX_PIN_0          12 // HSTX bit 0: TMDS CK- on the HDMI socket
#define HSTX_PIN_1          13 // HSTX bit 1: TMDS CK+ on the HDMI socket
#define HSTX_PIN_2          14 // HSTX bit 2: TMDS D0- on the HDMI socket
#define HSTX_PIN_3          15 // HSTX bit 3: TMDS D0+ on the HDMI socket
#define HSTX_PIN_4          16 // HSTX bit 4: TMDS D1- on the HDMI socket
#define HSTX_PIN_5          17 // HSTX bit 5: TMDS D1+ on the HDMI socket
#define HSTX_PIN_6          18 // HSTX bit 6: TMDS D2- on the HDMI socket
#define HSTX_PIN_7          19 // HSTX bit 7: TMDS D2+ on the HDMI socket
#define Z80_A4              31 // zx-bus 22B
#define Z80_A5              30 // zx-bus 21B
#define Z80_A6              29 // zx-bus 20B
#define Z80_A7              28 // zx-bus 19B
#define Z80_A8              27 // zx-bus 18B
#define Z80_A9              26 // zx-bus 17B
#define Z80_A10             25 // zx-bus 16B
#define Z80_A11             24 // zx-bus 15B
#define Z80_A12             23 // zx-bus 14B
#define Z80_A13             22 // zx-bus 13B
#define Z80_A14             21 // zx-bus 12B
#define Z80_A15             20 // zx-bus 11B
#define Z80_HALT            32 // zx-bus 13A
#define Z80_MREQ            33 // zx-bus 14A
#define Z80_IORQ            34 // zx-bus 15A
#define Z80_RD              35 // zx-bus 16A
#define Z80_WR              36 // zx-bus 17A
#define Z80_RST             37 // zx-bus 21A
#define Z80_M1              38 // zx-bus 22A
#define Z80_RFSH            39 // zx-bus 23A
#define Z80_CLK             40 // zx-bus 6B, 3.25MHz, through a 74LVC3G34 (GPIO40 is not 5 V tolerant)
#define LED_GREEN           41 // LED green, active high
#define I2C_SDA             42 // I2C1
#define I2C_SCL             43 // I2C1
#define SD_MISO             44 // SPI1 RX
#define SD_CS               45 // SPI1 CS
#define SD_CLK              46 // SPI1 SCK
#define SD_MOSI             47 // SPI1 TX

#endif // _PINS_H_
