// SPDX-License-Identifier: GPL-3.0-or-later
// Pico SDK board header for the OpenSpand Card v0.2. Preprocessor directives only.
// There are deliberately no default UART, I2C, SPI or LED pins: the SDK's usual
// ones are all Z80 bus or HSTX lines on this card.

// pico_cmake_set PICO_PLATFORM=rp2350

#ifndef _BOARDS_OPENSPAND_CARD_H
#define _BOARDS_OPENSPAND_CARD_H

#define OPENSPAND_CARD

#define PICO_RP2350A 0

#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1
#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 4
#endif

// pico_cmake_set_default PICO_FLASH_SIZE_BYTES = (16 * 1024 * 1024)
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

#ifndef PICO_XOSC_STARTUP_DELAY_MULTIPLIER
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
#endif

// pico_cmake_set_default PICO_RP2350_A2_SUPPORTED = 1
#ifndef PICO_RP2350_A2_SUPPORTED
#define PICO_RP2350_A2_SUPPORTED 1
#endif

#endif
