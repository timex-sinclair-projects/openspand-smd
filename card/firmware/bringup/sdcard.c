// SPDX-License-Identifier: GPL-3.0-or-later
// Read-only microSD check over SPI1. There is no write command in this file.
#include "bringup.h"

#include <stdio.h>

#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "pico/stdlib.h"

static uint8_t xfer(uint8_t out)
{
    uint8_t in;
    spi_write_read_blocking(spi1, &out, &in, 1);
    return in;
}

static void deselect(void)
{
    gpio_put(SD_CS, 1);
    xfer(0xff);
}

static uint8_t command(uint8_t cmd, uint32_t arg, uint8_t crc)
{
    deselect();
    gpio_put(SD_CS, 0);
    xfer(0xff);
    xfer(0x40 | cmd);
    for (int shift = 24; shift >= 0; shift -= 8)
        xfer(arg >> shift);
    xfer(crc);
    for (int i = 0; i < 16; i++) {
        uint8_t reply = xfer(0xff);
        if (!(reply & 0x80))
            return reply;
    }
    return 0xff;
}

static bool read_sector0(uint8_t data[512])
{
    if (command(17, 0, 0x01) != 0)
        return false;
    absolute_time_t end = make_timeout_time_ms(300);
    while (xfer(0xff) != 0xfe)
        if (time_reached(end))
            return false;
    spi_read_blocking(spi1, 0xff, data, 512);
    xfer(0xff);
    xfer(0xff);
    deselect();
    return true;
}

static void run(void)
{
    for (int i = 0; i < 10; i++)
        xfer(0xff);
    bool idle = false;
    for (int i = 0; i < 5 && !idle; i++) // some cards miss the first CMD0
        idle = command(0, 0, 0x95) == 1;
    if (!idle) {
        printf("FAIL no answer to CMD0: no card, or a fault round J5\n");
        return;
    }
    bool v2 = command(8, 0x1aa, 0x87) == 1;
    if (v2) {
        uint8_t echo[4];
        spi_read_blocking(spi1, 0xff, echo, 4);
        if (echo[2] != 1 || echo[3] != 0xaa) {
            printf("FAIL CMD8 echo\n");
            return;
        }
    }
    absolute_time_t end = make_timeout_time_ms(1500);
    for (;;) {
        command(55, 0, 0x01);
        if (command(41, v2 ? 0x40000000u : 0, 0x01) == 0)
            break;
        if (time_reached(end)) {
            printf("FAIL card never finished initialising\n");
            return;
        }
        sleep_ms(10);
    }
    if (!v2 && command(16, 512, 0x01) != 0) {
        printf("FAIL can't set the block length\n");
        return;
    }
    static const unsigned rates[] = {400000, 4000000, 12000000};
    static uint8_t first[512], data[512];
    for (unsigned r = 0; r < count_of(rates); r++) {
        unsigned actual = spi_set_baudrate(spi1, rates[r]);
        bool ok = read_sector0(r ? data : first);
        for (unsigned i = 0; ok && r && i < 512; i++)
            ok = data[i] == first[i];
        printf("%s sector 0 at %u Hz\n", ok ? "PASS" : "FAIL", actual);
        if (!ok)
            return;
    }
    printf("  boot signature %s\n",
           first[510] == 0x55 && first[511] == 0xaa ? "present" : "absent (card not formatted?)");
}

void test_sd(void)
{
    spi_init(spi1, 400000);
    gpio_init(SD_CS);
    gpio_put(SD_CS, 1);
    gpio_set_dir(SD_CS, GPIO_OUT);
    gpio_set_function(SD_MISO, GPIO_FUNC_SPI);
    gpio_set_function(SD_CLK, GPIO_FUNC_SPI);
    gpio_set_function(SD_MOSI, GPIO_FUNC_SPI);
    run();
    deselect();
    spi_deinit(spi1);
    gpio_init(SD_CS);
    gpio_init(SD_MISO);
    gpio_init(SD_CLK);
    gpio_init(SD_MOSI);
}
