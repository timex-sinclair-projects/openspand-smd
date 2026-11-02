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
    Pin map for the OpenSpand Card (RP2350B, chip-down, edge-card form factor).

    The GPIOs are arranged for the board layout:
      GPIO0..7    Z80 D0..D7   (read as the low byte of gpio_in, as upstream)
      GPIO8..23   Z80 A0..A15  (read as (gpio_in >> Z80_ADDR_SHIFT) & 0xFFFF)
      GPIO24..31  Z80 control lines, in edge-finger order
      GPIO32..47  Z80_CLK and the 3.3 V peripherals
    The video PIO uses GPIO base 16 so it can see Z80_CLK and the video pins.

    Z80_CLK, VIDEO_SYNC & VIDEO_DATA are defined here, but see
    pio_video_code.pio for actual usage.
*/

#ifndef _PINS_H_
#define _PINS_H_

#define Z80_D0               0 // zx-bus 4A
#define Z80_D1               1 // zx-bus 5A
#define Z80_D2               2 // zx-bus 6A
#define Z80_D3               3 // zx-bus 9A
#define Z80_D4               4 // zx-bus 10A
#define Z80_D5               5 // zx-bus 8A
#define Z80_D6               6 // zx-bus 7A
#define Z80_D7               7 // zx-bus 1A
#define Z80_ADDR_SHIFT       8 // Z80_A0..A15 on GPIO8..23, in order
#define Z80_A0               8 // zx-bus 7B
#define Z80_A1               9 // zx-bus 8B
#define Z80_A2              10 // zx-bus 9B
#define Z80_A3              11 // zx-bus 10B
#define Z80_A4              12 // zx-bus 22B
#define Z80_A5              13 // zx-bus 21B
#define Z80_A6              14 // zx-bus 20B
#define Z80_A7              15 // zx-bus 19B
#define Z80_A8              16 // zx-bus 18B
#define Z80_A9              17 // zx-bus 17B
#define Z80_A10             18 // zx-bus 16B
#define Z80_A11             19 // zx-bus 15B
#define Z80_A12             20 // zx-bus 14B
#define Z80_A13             21 // zx-bus 13B
#define Z80_A14             22 // zx-bus 12B
#define Z80_A15             23 // zx-bus 11B
#define Z80_HALT            24 // zx-bus 13A
#define Z80_MREQ            25 // zx-bus 14A
#define Z80_IORQ            26 // zx-bus 15A
#define Z80_RD              27 // zx-bus 16A
#define Z80_WR              28 // zx-bus 17A
#define Z80_RST             29 // zx-bus 21A
#define Z80_M1              30 // zx-bus 22A
#define Z80_RFSH            31 // zx-bus 23A
#define Z80_CLK             32 // zx-bus 6B, 3.25MHz
#define I2S_PIN_BCLK        33 // PIO-driven
#define I2S_PIN_WS          34 // PIO-driven, always BCLK + 1
#define I2S_PIN_DOUT        35 // PIO-driven
#define VIDEO_SYNC          36 // Video composite sync
#define VIDEO_DATA          37 // Video pixels, must be VIDEO_SYNC + 1
#define LED_RED             38 // PWM11A, LED red, also used for sampled audio
#define LED_GREEN           39 // PWM11B, LED green, also used for sampled audio
#define ZX_SER_TX           40 // UART1
#define ZX_SER_RX           41 // UART1
#define I2C_SDA             42 // I2C1
#define I2C_SCL             43 // I2C1
#define SD_MISO             44 // SPI1 RX
#define SD_CS               45 // SPI1 CS
#define SD_CLK              46 // SPI1 SCK
#define SD_MOSI             47 // SPI1 TX

#endif // _PINS_H_
