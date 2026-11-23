# Card bring-up firmware

A test console for a freshly built OpenSpand Card **v0.2**. It isn't OpenSpand: it checks
the hardware so that faults found while porting OpenSpand are software faults. It needs
only the Pico SDK.

**Status: not yet run on a board.**

Don't flash it to upstream's OpenSpand board or the retired SMD board: their address
lines are on this card's I2C and microSD pins.

## Safety

- Every bus and HSTX pin starts as an input. The only test that drives the bus is
  `shorts`, which first pulls every line up and drives nothing if any of them reads low.
- GPIO12-19 carry DVI on v0.2 but Z80 A4-A11 on v0.1 and SMD2. `dvi`, and the other
  tests specific to v0.2, need `arm v0.2`, which also checks that U8 is driving GPIO40
  (on the older boards that pin floats).
- The EEPROM, clock and microSD are only read.

## Bench procedure

1. **Unpowered, bare card.** Read the revision on the back. With a meter, check that +5V,
   +3V3 (U1 pin 5) and +1V2 (U9 pin 5) aren't shorted to ground.
2. **USB only**, nothing in the fingers or HDMI socket. Measure 3.3 V at U1 pin 5 and
   1.2 V at U9 pin 5. A blank flash comes up as a USB drive by itself; otherwise hold
   BOOTSEL and tap RUN. Copy `openspand_bringup.uf2` to it.
3. **Open the console**: `screen /dev/cu.usbmodem* 115200`
4. Run these, in order:

| Command | Needs | Pass |
| --- | --- | --- |
| `i2c` | | 0x27, 0x50 and 0x68 answer |
| `rtc` | | seconds advance |
| `eeprom` | | 16 bytes read |
| `sd` | a microSD | sector 0 reads the same at all three speeds |
| `arm v0.2` | v0.2 on the silkscreen | `Armed.` |
| `shorts` | bare card, HDMI unplugged | 0 faults |
| `leds` | LEDs fitted | green and red alternate |
| `inputs` | buttons, DE-9, a joystick | all seven inputs seen |
| `dvi 30` | HDMI display | test card; on reconnecting, 126000 kHz and 60.00 frames/s |

5. **On the ZX81.** Power everything off, seat the card with the components facing the
   ZX81, then power up and connect USB. Run `arm v0.2`, `clock` (3.25 MHz) and `bus`
   (which lines move). The ZX81 **will not boot** with this firmware: the card holds
   ROMCS and RAMCS high, and nothing here stands in for the ROM or RAM. Its clock and bus
   still run, which is all these two tests need. Then run `opens`.

   The Z80 runs wild on garbage, so a TS1000's clock may read a little under 3.25 MHz. The
   two machines tested so far gave 3.2226 and 3.2390 MHz. With no ROM, the Z80 never
   halts and does no I/O, so `bus` always shows HALT and IORQ as "always high". That's
   expected. `opens` checks those two instead: each line gets a weak pull-down, and a
   line the Z80 drives reads high at least some of the time. A line that never does is an
   open joint.

The DVI test card has a white border around colour bars, four grey steps and a one-pixel
checker, which is the hardest pattern on the link. Sparkles there point to signal
integrity. No picture with a passing frame rate points to the lane map, socket or cable.

## Clock plan under test

A 252 MHz system clock, the first plan for DVI, doesn't fit the video code. Upstream's video PIO takes
208 x 2 / 13 = 32 system clocks per ZX81 pixel, and at 252 MHz that would be 38.77.

`dvi` tries another plan: the system clock stays at 208 MHz and PLL_USB is retuned to
126 MHz for HSTX, giving standard 640x480 at 60 Hz. DMA feeds HSTX with no interrupts and
no CPU work. The cost is USB while DVI runs, so the test reboots to get the console back.
OpenSpand 0.51.4's source uses USB at run time only to print diagnostics (the code that
would mirror its config screen there is commented out), and updates go through the boot
ROM's own loader. Running OpenSpand with PLL_USB retuned is untested.

## Build and test

```bash
export PICO_SDK_PATH=~/pico/pico-sdk
export PICO_TOOLCHAIN_PATH=~/pico/arm-gnu-toolchain-13.3.rel1-darwin-arm64-arm-none-eabi
cmake -G Ninja -S . -B build && cmake --build build
cc -std=c11 -Wall -o build/test_dvi test/test_dvi.c && build/test_dvi
```

The host test replays two frames of the DMA list through a model of the HSTX command
expander, and checks the lane map and the firmware patch's address decode. It can't
check the HSTX registers, electrical behaviour or timing on silicon.

## License

GPL-3.0-or-later, like the other firmware here.
