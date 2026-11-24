// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "pins.h" // card/firmware/pins.h: the same map the firmware patch installs

#define BUS_AND_HSTX_PINS 40 // GPIO0..39

void board_all_inputs(void);
bool board_looks_like_v02(void);
const char *board_pin_name(unsigned pin);

void test_i2c(void);
void test_rtc(void);
void test_eeprom(void);
void test_leds(void);
void test_inputs(void);
void test_clock(void);
void test_bus(void);
void test_shorts(void);
void test_sd(void);
void test_opens(void);

void dvi_request(unsigned seconds, unsigned mode); // 0 card, 1 1 bpp, 2 HDMI tone
void dvi_run_if_requested(void);
void dvi_print_last_result(void);
