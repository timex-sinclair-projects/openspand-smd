// SPDX-License-Identifier: GPL-3.0-or-later
// Bring-up console for the OpenSpand Card v0.2. Everything starts as an input.
#include "bringup.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pico/bootrom.h"
#include "pico/stdlib.h"

static bool armed;

static void help(void)
{
    printf("\nOpenSpand Card v0.2 bring-up\n"
           "Card (any revision) or SMD2, not upstream's board:\n"
           "  i2c        find the three I2C chips\n"
           "  rtc        check the clock chip is counting\n"
           "  eeprom     read the settings EEPROM\n"
           "  sd         read sector 0 of the microSD\n"
           "  boot       restart in BOOTSEL for flashing\n"
           "After 'arm v0.2' (check the silkscreen on the back first):\n"
           "  shorts     bare card on USB only: bridges and shorts\n"
           "  leds       blink both LEDs\n"
           "  inputs     buttons and joystick\n"
           "  dvi [s]    test card on HDMI for s seconds (30); USB drops out meanwhile\n"
           "  dvi1 [s]   a 1 bpp frame drawn line by line, as OpenSpand will\n"
           "  clock      in a powered ZX81: measure the Z80 clock\n"
           "  bus        in a powered ZX81: which bus lines move\n"
           "  opens      in a powered ZX81: find unconnected bus pins, no meter needed\n");
    dvi_print_last_result();
}

static void arm(const char *what)
{
    armed = false;
    if (strcmp(what, "v0.2")) {
        printf("Type 'arm v0.2', and only if the back of the card says v0.2.\n");
    } else if (!board_looks_like_v02()) {
        printf("REFUSED: GPIO40 floats, but v0.2 has U8 driving it. This is an older board,\n"
               "or U8 is missing, unpowered or badly soldered.\n");
    } else {
        armed = true;
        printf("Armed.\n");
    }
}

typedef struct {
    const char *name;
    void (*run)(void);
    bool needs_arm;
} command_t;

static const command_t commands[] = {
    {"i2c", test_i2c, false},     {"rtc", test_rtc, false},   {"eeprom", test_eeprom, false},
    {"sd", test_sd, false},       {"shorts", test_shorts, true}, {"leds", test_leds, true},
    {"inputs", test_inputs, true}, {"clock", test_clock, true}, {"bus", test_bus, true},
    {"opens", test_opens, true},
};

static void handle(char *line)
{
    char *arg = strchr(line, ' ');
    if (arg)
        *arg++ = 0;
    if (!strcmp(line, "arm")) {
        arm(arg ? arg : "");
        return;
    }
    if (!strcmp(line, "boot"))
        reset_usb_boot(0, 0);
    if (!strcmp(line, "dvi") || !strcmp(line, "dvi1")) {
        int seconds = arg ? atoi(arg) : 30;
        if (!armed) {
            printf("Needs 'arm v0.2' first.\n");
        } else if (seconds < 3 || seconds > 600) {
            printf("3 to 600 seconds.\n");
        } else {
            printf("DVI for %d s. Reconnect afterwards for the result.\n", seconds);
            sleep_ms(300);
            dvi_request((unsigned)seconds, line[3] == '1');
        }
        return;
    }
    for (unsigned i = 0; i < count_of(commands); i++) {
        if (strcmp(line, commands[i].name))
            continue;
        if (commands[i].needs_arm && !armed)
            printf("Needs 'arm v0.2' first.\n");
        else
            commands[i].run();
        return;
    }
    help();
}

int main(void)
{
    board_all_inputs();
    dvi_run_if_requested(); // before USB starts: it retunes USB's PLL
    stdio_init_all();

    char line[48];
    unsigned length = 0;
    bool connected = false;
    for (;;) {
        bool now = stdio_usb_connected();
        if (now && !connected) {
            sleep_ms(200);
            help();
            printf("> ");
        }
        connected = now;

        int c = getchar_timeout_us(50000);
        if (c == '\r' || c == '\n') {
            if (length) {
                line[length] = 0;
                printf("\n");
                handle(line);
                length = 0;
                printf("> ");
            }
        } else if (c == 8 || c == 127) {
            if (length) {
                length--;
                printf("\b \b");
            }
        } else if (c >= ' ' && c < 127 && length < sizeof line - 1) {
            line[length++] = (char)c;
            putchar_raw(c);
        }
    }
}
