# OpenSpand SMD

A chip-down, surface-mount version of [OpenSpand](https://codeberg.org/NollKollTroll/OpenSpand),
the open-source all-in-one expansion for the Sinclair ZX81. It's designed for JLCPCB assembly.

Upstream V1.31 is built from plug-in modules (Olimex Pico2-XL, a DS1307 "tiny RTC" module,
a UDA1334 I2S DAC module) plus through-hole parts. This board puts the chips themselves on
a 4-layer, 100 × 70 mm PCB. All SMD parts are on the top side, so JLC assembles one side.

A second layout, [OpenSpand SMD2](smd2/README.md), reassigns the RP2350B's GPIOs and turns
the chip to make routing easier. It needs a patched firmware pin map; this design doesn't.

Layout: the ZX81 edge socket runs along the bottom edge. The pin headers, microSD slot and
line-out jack are on the top edge. USB-C and the Reset, Config, BOOTSEL and RUN buttons are
on the left. The DE-9 joystick connector is on the right edge, fitted on the bottom side.
This is a free layout: it does not fit the upstream 3D-printed case.

**Status: unverified prototype (rev 0.1), fully routed.** The schematic passes ERC, the PCB
matches the schematic netlist, and DRC reports no unconnected items, clearance errors or
shorts. No board has been built yet. Review it before you order.

## Firmware compatibility

The GPIO map is identical to upstream `OpenSpand_SW/pins.h`, and every I2C device sits at its
upstream address. So the **upstream firmware runs unchanged**: build it for the
"Olimex Pico2-XL" board as described in the OpenSpand manual, or flash a release `.uf2`.

| Function | Upstream V1.31 | This board |
| --- | --- | --- |
| MCU | Olimex Pico2-XL module | RP2350B + W25Q128JV 16 MB flash + 12 MHz crystal |
| 3.3 V | regulator on module | ME6211C33 LDO |
| USB | on module | USB-C, BOOTSEL and RUN buttons |
| RTC | DS1307 module | DS1307Z+ (5 V) + 32.768 kHz crystal + CR2032 (Keystone 3034) |
| Settings EEPROM (0x50) | AT24C32 on RTC module | FT24C32A |
| I/O expander (0x27) | MCP23009 DIP-18 | MCP23009 SSOP-20 (same chip: 5 V-tolerant open-drain joystick inputs) |
| Audio | UDA1334 module | PCM5102A + 3.5 mm line-out jack |
| SD card | full-size SD | microSD (TF-01A push-push) |
| 5 V jumpers, 75 Ω video termination | pin-header jumpers | solder jumpers JP1, JP2, JP3 (open by default) |

### PCM5102A note
The firmware drives I2S with 16-bit samples at about 47.8 kHz. That gives BCK = 32 × fs,
which the PCM5102A supports in its PLL mode (its SCK pin is grounded). This is the one
functional change from upstream that hasn't been tested on hardware.

## Repository layout

```
tools/design.py       parts, LCSC numbers and every connection: the single source of truth
tools/gen_lib.py      builds hardware/lib/OpenSpandSMD.{kicad_sym,pretty}
tools/gen_sch.py      design.py -> hardware/OpenSpand-SMD.kicad_sch
tools/gen_pcb.py      design.py -> hardware/OpenSpand-SMD.kicad_pcb (outline, parts, placement)
tools/route.py        fanout, pre-routes, Freerouting autoroute, ground pours
tools/finish.py       maze-routes whatever the autorouter left open, with rip-up and retry
tools/export_fab.py   Gerbers, drill, BOM and CPL for JLCPCB -> hardware/fab/
hardware/             the KiCad 10 project
```

The schematic and PCB are generated. To change the circuit, edit `design.py` and regenerate.
You can also take over in KiCad by hand: after that, treat the KiCad files as the source and
stop running the generators.

### Regenerating

```bash
cd tools
python3 gen_lib.py /path/to/OpenSpand/OpenSpand_HW/V1.31
python3 gen_sch.py
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$KPY gen_pcb.py
FREEROUTING_JAR=~/freerouting.jar JAVA=/opt/homebrew/opt/openjdk/bin/java $KPY route.py 150
$KPY finish.py
python3 export_fab.py
```

`route.py` starts from the unrouted board, so run `gen_pcb.py` before it every time. It
takes 5 to 15 minutes, and `finish.py` up to 15 more. The result varies a little from run
to run, so a fresh run can still end with an open connection or two. `route.py reuse` re-imports the last run's `.ses` file without
routing again, which is useful after a rule-only change in `gen_pcb.py`.

### How the board is routed

- **Planes.** In1 is solid GND and In2 is +3V3. Every SMD GND and +3V3 pad gets a short
  track and a via to its plane. The RP2350's supply pins put their vias inward, in the ring
  between the pins and the exposed pad, so the outside is free for signals.
- **1.1 V core.** The RP2350's core supply (+1V1) is fanned out the same way and joined by
  a 0.3 mm track tree on In2, cut into the +3V3 plane.
- **Pre-routes.** The regulator nets (VREG_LX, VREG_AVDD) and the QSPI flash bus are
  maze-routed directly on F.Cu before the autorouter runs. The USB pair is pre-routed too,
  with vias, because the RP2350's USB pins
  are boxed in by the QSPI bus and the regulator nets.
- **Autoroute.** Freerouting routes everything else on F.Cu and B.Cu.
- **Finishing.** `finish.py` reads the open connections from KiCad's DRC and maze-routes
  each one. When a connection is blocked it rips up nearby nets, routes the blocked one, and
  reroutes the ripped ones. It keeps a change only if the count of open connections drops.
  It may run a short track on an inner plane: In1 (GND) first, In2 (+3V3) only as a last
  resort. It rejects any route that splits a plane into an isolated island.
- **Ground pours.** GND is poured on both outer layers.
- **Rules.** Signals use 0.127 mm tracks and gaps (JLC's 4-layer minimum is 0.09 mm),
  and vias are 0.45/0.25 mm.

### Current board

The board in `hardware/` came from the pipeline above plus one hand-directed fix:

- `finish.py` left Z80_D5 (U2 pin 2) open, because Z80_D4 and QSPI_SS had used the only
  escape from that pin.
- Ripping both nets and rerouting D5, then D4, then QSPI_SS closed it. QSPI_SS now runs
  partly on In1 (five short segments in the GND plane).
- The D4 rip also removed the B.Cu stub joining J1 C18's through-hole pad to its edge
  finger, so that stub was put back.
- Two SD_CS segments were moved 4 µm away from U2 pad 39.

The only signal copper on the inner layers is those QSPI_SS segments on In1 and the +1V1
tree on In2. Treat `hardware/OpenSpand-SMD.kicad_pcb` as the source now. A regeneration
won't reproduce it exactly.

Current DRC: no errors. There are 4 edge-clearance warnings from J1 (below) and
silkscreen warnings, which are cosmetic.

## Ordering from JLCPCB

- PCB: upload `hardware/fab/OpenSpand-SMD-gerbers.zip`. Choose 4 layers, 1.6 mm, any colour.
- Assembly: top side. Upload `BOM-JLCPCB.csv` and `CPL-JLCPCB.csv`, then check every part's
  rotation in JLC's preview, especially U2, U3, U4, U7, J3, J5, J7 and L1.
- `hand-solder.csv` lists what you fit yourself:
  - the ZX81 edge-connector socket (same part as upstream)
  - the DE-9 joystick connector
  - the optional pin headers (SWD, external SPI, I2C/UART, digitized audio, video)

## Before ordering, check

- **L1 orientation**: the RP2350 datasheet asks for the Abracon AOTA-B201610S3R3 with its
  marking dot toward VREG_LX. The footprint is a generic 2016 pad.
- **Jack pinout**: J7 uses KiCad's PJ320D footprint (T = left, R1 = right, R2 and S = ground)
  against LCSC C431535. Compare with the LCSC drawing.
- **DE-9 on the bottom**: the joystick connector is fitted on the bottom side at the right
  edge, and its shell sticks out about 7 mm past the edge.
- **Address lines A8-A15** go to RP2350 GPIO40-47. Those are the ADC-capable pins, which are
  not 5 V tolerant. Upstream connects them the same way and works, but it's outside the
  RP2350 datasheet's rating.
- **Edge-socket footprint**: J1's GND pads sit 0.16 mm from its own board-edge slots
  (4 DRC warnings). This comes unchanged from the upstream footprint, which has been made.
- **Low-stock parts**: MCP23009T-E/SS (C629436), AOTA inductor (C42411119) and FT24C32A
  (C232883) had a few hundred in stock when this was designed.

## License

Hardware: CC BY-SA 4.0, as a derivative of OpenSpand HW 1.3.1 by Adam Klotblixt & ZX-Team.
The ZX81 edge-connector and DE-9 footprints are copied unchanged from upstream.
The OpenSpand firmware is GPL-3.0 and lives upstream.
