# OpenSpand Card

The [SMD2](../smd2/README.md) circuit on a card that stands upright in an edge socket on a
ZX81 expansion bus. The card is 155 mm wide, close to the ZX81's 167 mm, so it can go in a
3D-printed case. It is 57 mm tall: a 49 mm body, plus the fingers.

**Status: unverified prototype (rev 0.1).** No board has been built, and the firmware patch
hasn't been compiled or tested. The VGA output has no firmware yet: see [Firmware](#firmware). See [Result](#result) for the routing and check state.

![The card, component side](docs/card-top.png)

## Form factor

```
 ┌──────────────────────────────────────────────────────────────────────┐
 ├─────┐ SPI UART  ▲RESET ▲CONFIG ▲BOOT ▲RUN  USB-C   microSD     ┌─────┤
 │◄DE-9│ U4  DAC                                         RP2350B  │VGA ►│
 ├─────┘                                                          └─────┤
 │◄line out                                                             │
 └──────────────────────────────┐▌▌ ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌┌─────┘
                                └─────────────────────────┘
   seen from the front (the component side, which faces the ZX81)
```

- **Fingers**: the ZX81's own edge, 23 positions at 0.1 in, key slot at position 3
  (2 fingers left of the slot, 20 right of it). Fingers are 1.65 x 7 mm on an 8 mm tongue.
- **Which side is which**: the components face the ZX81. Seen from that side the card
  matches the ZX81's edge seen from above: the front fingers carry the ZX81's top-side
  signals (D7, ~RAMCS, key, D0 ... ~RFSH), and the back fingers carry its underside
  signals (+5V, +9V, key, 0V ... ~ROMCS). Position 1 is on the left. A backplane that
  wires each socket straight through to the ZX81 connector, ZX81 top row to the socket's
  front row, works as-is.
- **Alignment**: the fingers sit 6.38 mm in from the card's right edge. That figure
  assumes the ZX81 board sits centred in its 167 mm case: the board is 142.24 mm wide
  (from the [ZX81+38](https://github.com/mahjongg2/ZX81plus38) drop-in replacement), and
  its edge connector runs to the board's right end. **Measure a real ZX81 before ordering**:
  take the distance from the case's right side (seen from the front) to the end of the
  edge connector, and subtract 6 mm. Set `RIGHT_OVERHANG` in `tools/gen_pcb.py` to the
  result and rerun the pipeline.
- **Connectors**: on the left edge, the DE-9 joystick port with the line-out jack below it;
  the joystick's I/O expander (U4) and the audio DAC sit just inboard. On the right edge,
  the VGA socket. Along the top edge: the SPI and UART headers, four buttons, USB-C and the
  microSD. There's no SWD header; flash over USB with BOOTSEL.
  The buttons are named on the silkscreen: RESET and CONFIG, as on OpenSpand, plus BOOTSEL
  and RUN for the RP2350B (upstream has BOOTSEL on its Pico module and RUN only as a pin).
  The DE-9 and VGA socket stand about 12.5 mm off the board, so sockets on the backplane
  need roughly 15 mm or more between them.
- **Buttons through the top of the case**: SW1–SW4 are C&K PTS645VL83-2 LFS right-angle
  through-hole tactile switches, hand-fitted (DNP for JLC). Each has a 3.5 mm plunger pointing
  up out of the top edge. For the case: the body's front is flush with the board edge, the
  plunger tip is about 5.8 mm past it, and the plunger's axis is 3.5 mm above the component
  side. The four sit at 49.5, 62.7, 75.9 and 89.1 mm from the card's left edge (RESET, CONFIG,
  BOOTSEL, RUN). The body is 7.5 mm wide.
- **1.2 V core LDO instead of the RP2350's switcher**: an ME6211C12 (U9) feeds DVDD, so there's
  no inductor and none of the switcher's layout rules. The RP2350 datasheet allows this
  (section 6.3.7): VREG_LX is left open, VREG_FB is grounded, and VREG_VIN and VREG_AVDD stay
  powered for the reset and brownout circuits. It's 1.2 V rather than 1.1 V because the
  firmware runs the core at 1.20 V for its 208 MHz overclock. The on-chip regulator still
  starts at power-up but can't drive anything without its inductor; firmware can turn it off
  (VREG.HIZ) to save about 400 µA. The LDO wastes about 0.1 W.
- **VGA instead of composite video**: a high-density 15-pin socket (J8) for 60 Hz VGA, for
  the North American (NTSC) ZX81. GPIO36 and GPIO37 carry HSYNC and VSYNC through 33 Ω, and
  GPIO38 carries the mono picture, so the three VGA pins are consecutive (36-38) for the
  PIO. A 74LVC3G34 triple buffer (U8) drives red, green and blue from it through 270 Ω
  each, about 0.7 V into the monitor's 75 Ω, so white is white.
- **Serial port kept**: UART1 stays on GPIO40 (TX) and GPIO41 (RX), as on SMD2, on a 1x4
  header J10 (TX, RX, 5 V, GND; 3.3 V logic). That's the ZX81 serial port: ports 0xE3 / 0xEB,
  `OPEN SERIAL`, `OPEN MIDI`, `PUT SER`. To make room, the red LED (D3) moved off GPIO38 to
  the I/O expander's GP2 (U4 pin 12, active low); the green LED stays on GPIO39. The
  digitized-audio header is gone, so the firmware's sampled-audio PWM (which only ever
  went to the two LED pins) has no output on this card.
- **Real-time clock**: a DS3231MZ (U5) at 0x68 in place of SMD2's DS1307. It has a
  built-in MEMS resonator, so there's no 32.768 kHz crystal, and it keeps time to about
  ±5 ppm (a few minutes a year). It uses the DS1307's address and time registers, so the
  firmware's `GET TIM` / `GET DAT` and time and date screens work unchanged. Backup is a
  plain CR2032 (BT1) that slides in from the bottom edge; there's no charger.
- **Five M3 holes** (3.2 mm, unplated) for screw posts in a case: top left, just inboard of
  the DE-9 (H1); lower left, under the line out (H3); top right, between the microSD and
  the VGA socket (H4); bottom right, in the corner below the VGA socket (H5); and one near
  the bottom middle (H2).

## What changed from SMD2

| | SMD2 | Card |
| --- | --- | --- |
| Board | 100 x 70 mm, socket on the bottom edge | 155 x 57 mm card with gold fingers |
| ZX81 connection | edge socket (plugs onto the ZX81) | fingers (stand in a socket on a bus) |
| Video | composite, 2-pin header J8 | VGA socket J8 (LCSC C138387, hand-fitted) |
| DE-9 | bottom side | top side, left edge |
| Serial port (UART) | GPIO40-41, header J10 | same |
| Red LED | GPIO38 (PWM, also sampled audio) | I/O expander GP2 (on/off only) |
| Headers | SWD, UART, SPI, digitized audio | UART and SPI only |
| Real-time clock | DS1307 + 32.768 kHz crystal + CR2032 | DS3231MZ (no crystal) + CR2032 |
| RP2350 core supply | on-chip switcher + 3.3 µH inductor | ME6211C12 LDO at 1.2 V |
| Buttons | top-push SMD, inboard | right-angle THT on the top edge, hand-fitted |
| GPIO0..7 | control lines | D0..D7 |
| GPIO24..31 | D0..D7 | control lines |

GPIO8..23 (A0..A15) and the rest of GPIO32..47 (Z80 clock, I2S, LEDs, I2C, microSD) are the
same as SMD2, except GPIO36..37 are VGA HSYNC and VSYNC (composite sync and data on SMD2) and
GPIO38 is VGA video (the red LED on SMD2).

**Why the bus groups swap.** On SMD2 the edge socket is on the bottom of the board. Here
the fingers are on the same side as the RP2350B, which mirrors the left-to-right order. With
U2 turned 90° the bus pins sweep round its lower-left corner and along its bottom edge
toward the fingers: data first (their fingers are on the left), then the address bus,
then the control lines up its right side (their fingers are on the right).

## Result

Fully routed on four layers (signal, GND, power, signal). DRC with schematic parity and a
zone refill reports no copper, clearance, edge or unconnected errors; what remains is
silkscreen only (reference text over copper, overlapping or near the edge), which the fab
clips. ERC is clean.

| | Card | SMD2 |
| --- | --- | --- |
| Vias | 301 | 268 |
| Signal vias | 150 | 126 |
| Track length | 3545 mm | 3520 mm |
| Z80 bus track | 1095 mm | 1319 mm |

The Z80 bus is shorter than on SMD2 because the fingers run right under U2. Most of the
extra track is the long runs across the card to the joystick, line out and pin headers at the
left end. The run is clean: Freerouting closed every connection, and no signal runs on the
inner planes. The only inner-layer copper is the +1V2 core rail, a short spur on In2 as on
SMD2.

![Copper layers](docs/copper-card.png)

## Firmware

`firmware/card-pins.patch` applies to upstream OpenSpand_SW 0.51.0, like SMD2's patch:

```bash
cd OpenSpand/OpenSpand_SW
patch -p1 < /path/to/card/firmware/card-pins.patch
```

It is SMD2's patch with the data bus moved back to GPIO0..7, so data reads and writes
use the low byte of the GPIO registers exactly as upstream does, with no shift. Only the
address read gains a shift (`gpio_get_all_lo() >> 8`). The video PIO changes (GPIO base
16, `wait gpio 16` for Z80_CLK on GPIO32) are the same as SMD2's. SMD2's
[checklist](../smd2/README.md#firmware) applies: timing, I2S above pin 31, and SDK pin
handling with a GPIO base.

**VGA isn't in the patch yet.** The patch still drives composite video, and on this board
those pins now carry VGA sync, so there's no picture until a VGA driver is written. The
plan: core 1, which already hands each ZX81 pixel byte to the video PIO, also stores it
in a line buffer, and a PIO program on a free PIO block sends every line out twice at
twice the rate. That turns the ZX81's NTSC picture (262 lines at about 15.7 kHz, 60 Hz)
into about 524 lines at 31.4 kHz and 60 Hz, which is close to 640 x 480 VGA timing. The
serial port code stays as it is (UART1 on GPIO40/41). Two more changes are needed: the VGA
pins (36-38), and the red LED, which is now bit 2 of the I/O expander rather than GPIO38.
Until the LED change is made the red LED stays on, because the firmware sets that expander
bit as an output and leaves it low.

## Regenerating

From `tools/`:

```bash
python3 gen_lib.py      # project library: edge fingers, VGA buffer (and the SMD2 parts)
python3 gen_sch.py
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$KPY gen_pcb.py
FREEROUTING_JAR=~/freerouting.jar JAVA=/opt/homebrew/opt/openjdk/bin/java $KPY route.py 150
$KPY finish.py
python3 export_fab.py
```

The schematic and PCB are generated: to change the circuit, edit `design.py` and
regenerate. `route.py` starts from the unrouted board, so run `gen_pcb.py` before it every
time. Routing takes 5 to 10 minutes. The result varies a little from run to run, so a fresh
run can still end with an open connection; `finish.py` reports any it couldn't close.
`route.py reuse` re-imports the last run's `.ses` file without routing again, which is
useful after a rule-only change in `gen_pcb.py`.

### How the board is routed

- **Planes.** In1 is solid GND and In2 is +3V3, over the body only. Every SMD GND and +3V3
  pad gets a short track and a via to its plane. The RP2350B's supply pins put their vias
  inward, in the ring between the pins and the exposed pad, so the outside is free for
  signals.
- **1.2 V core.** The RP2350B's core supply (+1V2) is fanned out the same way and joined by
  a 0.3 mm track tree on In2, cut into the +3V3 plane.
- **Fingers.** A rule area over the tongue bans vias and pours. The GND fingers (on the
  back) are tied to the plane by a short stub and a via just above the tongue.
- **Pre-routes.** VREG_AVDD, the QSPI flash bus and the USB
  pair are maze-routed before the autorouter runs, because they're boxed in around the
  RP2350B.
- **Autoroute.** Freerouting routes everything else on F.Cu and B.Cu.
- **Finishing.** `finish.py` reads the open connections from KiCad's DRC and maze-routes
  each one. When a connection is blocked it rips up nearby nets, routes the blocked one, and
  reroutes the ripped ones, keeping a change only if the count of open connections drops.
  It may run a short track on an inner plane (In1 first, In2 only as a last resort) and
  rejects any route that splits a plane. It then nudges tracks off the board edge, trims
  dangling ends and moves vias a few µm clear where DRC asks.
- **Ground pours.** GND is poured solid on both outer layers.
- **Rules.** Signals use 0.127 mm tracks and gaps (JLC's 4-layer minimum is 0.09 mm), and
  vias are 0.45/0.25 mm.

## Ordering

Fab files go to `hardware/fab/`: `OpenSpand-Card-gerbers.zip`, `BOM-JLCPCB.csv`,
`CPL-JLCPCB.csv` and `hand-solder.csv`. Ordering is as in the
[main README](../README.md#ordering-from-jlcpcb), plus:

- **Gold fingers**: choose "Gold fingers: Yes" and a 45° bevel. JLCPCB's gold-finger option
  plates the fingers with hard gold, which wears far better than ENIG in a socket.
- The tongue has no vias and no copper pour, and the inner planes stop at the body, so the
  bevel cuts nothing but the fingers' ends.
- Hand-fit: DE-9 (J4), VGA socket (J8, BOOMELE VGA-002, LCSC C138387), the four buttons
  (SW1–SW4, C&K PTS645VL83-2 LFS) and the optional pin headers. J8 uses KiCad's 2.29 x 1.90 mm right-angle HD-15 footprint with 25 mm mounting
  holes; compare it with the VGA-002 drawing before ordering.

## License

Hardware: CC BY-SA 4.0, as a derivative of OpenSpand HW 1.3.1 by Adam Klotblixt & ZX-Team.
The firmware patch modifies GPL-3.0 code from OpenSpand_SW and is GPL-3.0.
