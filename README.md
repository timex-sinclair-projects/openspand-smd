# OpenSpand Card

A chip-down, surface-mount [OpenSpand](https://codeberg.org/NollKollTroll/OpenSpand), the
open-source all-in-one expansion for the Sinclair ZX81, on a card that stands upright in
an edge socket on a ZX81 expansion bus. It's designed for JLCPCB assembly.

![The card, component side](card/docs/card-render-front.png)

![Angled view](card/docs/card-render-3d.png)

The card is 155 × 57 mm, close to the ZX81's width, so a row of cards fits a 3D-printed
case behind the computer. The ZX81's own 23-position edge (key slot at position 3) is cut
along the bottom as gold fingers, 6.38 mm in from the right edge so they line up with the
ZX81's connector. All the SMD parts are on the component side, which faces the ZX81.

| Edge | Connectors |
| --- | --- |
| Left | DE-9 joystick |
| Right | HDMI (DVI picture, HDMI sound) |
| Top | SPI header; RESET, CONFIG, BOOTSEL and RUN buttons (right-angle, hand-fitted, pushed from above); USB-C; microSD |
| Bottom | ZX81 fingers |

**Status: unverified prototype (rev 0.2), fully routed.** Rev 0.2 replaces rev 0.1's VGA
socket with DVI on an HDMI socket, driven by the RP2350's HSTX block, and sends sound over
HDMI ([issue 7](https://github.com/timex-sinclair-projects/openspand-smd/issues/7)). ERC is
clean, the PCB matches the schematic, and DRC shows no clearance, edge or unconnected
errors (only silkscreen warnings). No board has been built, and the firmware patch
deliberately doesn't build until the DVI and HDMI-audio code is written. Review it before
you order.

The full write-up (form factor, finger convention, routing results, regenerating) is in
[card/README.md](card/README.md).

## From modules to chips

Upstream V1.31 is built from plug-in modules plus through-hole parts. The card puts the
chips themselves on a 4-layer board:

| Function | Upstream V1.31 | OpenSpand Card |
| --- | --- | --- |
| MCU | Olimex Pico2-XL module | RP2350B + W25Q128JV 16 MB flash + Abracon ABM8-272-T3 12 MHz crystal |
| 3.3 V | regulator on module | ME6211C33 LDO |
| 1.2 V core | RP2350 switcher + inductor on module | ME6211C12 LDO (no inductor) |
| USB | on module | USB-C, BOOTSEL and RUN buttons |
| RTC | DS1307 module | DS3231MZ (built-in resonator, no crystal) + CR2032 |
| Settings EEPROM (0x50) | AT24C32 on RTC module | FT24C32A |
| I/O expander (0x27) | MCP23009 DIP-18 | MCP23009 SSOP-20 (same chip: 5 V-tolerant open-drain joystick inputs) |
| Audio | UDA1334 module | HDMI audio (firmware not written yet) |
| Composite video | pin header | DVI on an HDMI socket, 60 Hz, via HSTX (firmware not written yet) |
| SD card | full-size SD | microSD (TF-01A push-push) |
| 5 V joystick jumpers | pin-header jumpers | solder jumpers JP1, JP2 (open by default) |
| Serial port | UART header | none (no GPIO left) |

The DS3231MZ answers at the DS1307's address (0x68) with the same time and date
registers, so the firmware's clock code runs unchanged. It shares the I2C bus and pull-ups
with the EEPROM and I/O expander. The CR2032 is only a backup cell; nothing charges it.

## Firmware

The card needs the upstream OpenSpand_SW 0.51.0 firmware with
[card/firmware/card-pins.patch](card/firmware/card-pins.patch) applied, plus a DVI and
HDMI-audio driver that hasn't been written yet. Until then the patch fails to build, on
purpose (see [card/README.md](card/README.md#firmware)). The fingers are on the same side
as the RP2350B, and HSTX, the RP2350's only route to DVI, is fixed to GPIO12..19, so the
card puts the Z80 bus on different GPIOs from upstream:

| GPIO | Card |
| --- | --- |
| 0–7 | D0–D7 |
| 8–11 | A0–A3 |
| 12–19 | HSTX: DVI to the HDMI socket |
| 20–31 | A15–A4 (reversed) |
| 32–39 | HALT, MREQ, IORQ, RD, WR, RESET, M1, RFSH |
| 40–47 | Z80 clock (buffered), green LED, I2C, microSD |

Data still reads as the low byte of the GPIO register, as upstream does. The address comes
from one read of the low register, with a shift for A0..A3 and an RBIT for A4..A15.
GPIO40–47 are the RP2350B's ADC pins, which aren't 5 V tolerant, and the 32 bus lines use
up every other GPIO, so the ZX81's clock reaches GPIO40 through a 74LVC3G34 buffer.

The I2S DAC, its line-out jack and the serial port are gone: HSTX's eight pins took theirs.
The joystick's I/O expander, the clock and the settings EEPROM are unchanged on I2C.

## Ordering from JLCPCB

- **PCB**: upload `card/hardware/fab/OpenSpand-Card-gerbers.zip`. Choose 4 layers, 1.6 mm,
  any colour, and **gold fingers with a 45° bevel**. The tongue has no vias or pour and the
  inner planes stop at the body, so the bevel only cuts the fingers' ends.
- **Assembly**: top side. Upload `BOM-JLCPCB.csv` and `CPL-JLCPCB.csv`, then check every
  part's rotation in JLC's preview, especially U2, U3, U4, U8, U9, U10, U11, J3, J5 and J8.
- **Hand-fit** (`hand-solder.csv`): the DE-9 (J4), the four buttons (SW1–SW4, C&K
  PTS645VL83-2 LFS) and the optional pin header. JLC fits the HDMI socket (J8, Molex
  208658-1001, LCSC C916313).

### Before ordering, check

- **Finger alignment**: the 6.38 mm offset assumes the ZX81's board is centred in its case.
  Measure from the case's right side to the end of the edge connector, subtract 6 mm, set
  `RIGHT_OVERHANG` in `card/tools/gen_pcb.py` and regenerate.
- **Backplane spacing**: the DE-9 stands about 12.5 mm off the board, so sockets on the bus
  need roughly 15 mm or more between them.
- **RP2350 support circuit**: the crystal (ABM8-272-T3, 15 pF load caps, 1 kΩ series
  resistor) follows Raspberry Pi's *Hardware design with RP2350*. The core supply doesn't: the
  on-chip switching regulator is unused (no inductor, VREG_LX open, VREG_FB grounded) and an
  ME6211C12 LDO (U9) feeds DVDD at 1.2 V, as in section 6.3.7 of the RP2350 datasheet. JLC
  may show its generic warning about following Raspberry Pi's guide.
- **HDMI socket**: J8 uses KiCad's footprint for the Molex 208658-1001 (LCSC C916313), with
  its "PCB Edge" line on the board edge. Compare it with Molex's drawing, and check that the
  mouth clears a case wall.
- **TMDS routing**: the eight DVI lines are 0.15 mm tracks over the GND plane, matched
  within a pair but not impedance-controlled. That's normal for GPIO-driven DVI at 640 x 480
  (252 Mbit/s per lane), but no board has been tested.
- **ESD arrays**: U10 and U11 are TI TPD4E05U06DQAR (C138714), flow-through: each TMDS line
  runs straight across a pad pair (1-10, 2-9, 4-7, 5-6).
- **Coin cell**: fit a CR2032 in BT1 after assembly; the board ships without one.
- **Buttons**: SW1–SW4 are C&K PTS645VL83-2 LFS right-angle through-hole switches, marked
  DNP so JLC skips them; buy them from Digi-Key or Mouser (LCSC has only the short-plunger
  PTS645VK39) and solder them yourself.
- **Low-stock parts**: MCP23009T-E/SS (C629436) and FT24C32A (C232883) had a few hundred in
  stock when this was designed.

## Earlier board

[OpenSpand SMD2](smd2/README.md) is the same circuit on a 100 × 70 mm board that plugs
straight onto the ZX81's edge connector with a socket, like upstream. The card is based on
it, and it's kept for reference. (The first board, OpenSpand SMD, kept upstream's GPIO map,
which puts A8–A15 on the RP2350B's ADC pins, which aren't 5 V tolerant. It has been
retired; it's in the git history.)

## Repository layout

```
card/                 OpenSpand Card (the main design)
  tools/              design.py is the single source of truth; the other scripts generate
                      the library, schematic, placement, routing and fab files from it
  hardware/           KiCad project, fab/ output
  firmware/           pin-map patch for OpenSpand_SW
  docs/               renders
smd2/                 OpenSpand SMD2, same structure
```

The schematics and PCBs are generated: edit `design.py` and regenerate, as described in
[card/README.md](card/README.md#regenerating).

## License

Hardware: CC BY-SA 4.0, as a derivative of OpenSpand HW 1.3.1 by Adam Klotblixt & ZX-Team.
The DE-9 footprint (and SMD2's edge-socket footprint) are copied unchanged from upstream.
The OpenSpand firmware is GPL-3.0 and lives upstream; the firmware patches here are GPL-3.0.
