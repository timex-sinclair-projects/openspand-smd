# OpenSpand Card

The [SMD2](../smd2/README.md) circuit on a card that stands upright in an edge socket on a
ZX81 expansion bus. The card is 155 mm wide, close to the ZX81's 167 mm, so it can go in a
3D-printed case. It is 57 mm tall: a 49 mm body, plus the fingers.

**Status: unverified prototype (rev 0.2).** No board has been built, and the firmware patch
hasn't been compiled or tested. Rev 0.2 swaps rev 0.1's VGA socket for DVI on an HDMI socket
([issue 7](https://github.com/timex-sinclair-projects/openspand-smd/issues/7)), and the DVI
output has no firmware yet: see [Firmware](#firmware). See [Result](#result) for the routing and
check state.

![The card, component side](docs/card-top.png)

## Form factor

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │ SPI        ▲R   ▲G     ▲RESET ▲CONFIG ▲BOOT ▲RUN  USB-C       ┌──────┤
 ├─────┐ U4                                                      │ SD  ►│
 │◄DE-9│                                                         ├──────┤
 ├─────┘                                         RP2350B         │HDMI ►│
 │                                                               └──────┤
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
- **Connectors**: on the left edge, the SPI header (J6) at the top and the DE-9 joystick port
  below it, with the joystick's I/O expander (U4) just inboard. On the right edge, the microSD
  (the card goes in from the side) above the HDMI socket. Along the top edge: the two status
  LEDs, four buttons and USB-C. There's no SWD header; flash over USB with BOOTSEL.
  The buttons are named on the silkscreen: RESET and CONFIG, as on OpenSpand, plus BOOTSEL
  and RUN for the RP2350B (upstream has BOOTSEL on its Pico module and RUN only as a pin).
  The DE-9 stands about 12.5 mm off the board (the HDMI socket about 6.5 mm), so sockets on
  the backplane need roughly 15 mm or more between them.
- **Buttons through the top of the case**: SW1–SW4 are C&K PTS645VL83-2 LFS right-angle
  through-hole tactile switches, hand-fitted (DNP for JLC). Each has a 3.5 mm plunger pointing
  up out of the top edge. For the case: the body's front is flush with the board edge, the
  plunger tip is about 5.8 mm past it, and the plunger's axis is 3.5 mm above the component
  side. The four sit at 49.5, 62.7, 75.9 and 89.1 mm from the card's left edge (RESET, CONFIG,
  BOOTSEL, RUN). The body is 7.5 mm wide.
- **Status LEDs through the top of the case**: D3 (red) and D4 (green) are 3 mm diffused
  through-hole LEDs (Kingbright WP710A10ID and WP710A10GD), hand-fitted (DNP for JLC). Bend
  the legs 90° about 1.3 mm from the flange so the body lies on the component side and looks
  up out of the top edge, like the buttons: the flange sits 0.7 mm inside the edge, the dome
  about 4.6 mm past it, and the LED's axis is 2 mm above the board. Their centres are 26 and
  36 mm from the card's left edge, 10 mm apart, with about 4 mm clear to H1 and 6 mm to
  RESET. The flat (cathode) side goes to the square pad. Each runs from 3.3 V through 2.2 kΩ
  (R22, R23), about 0.6 mA red and 0.5 mA green: a soft glow from a diffused LED, not a glare.
  For brighter, drop the resistors (not below 330 Ω); for dimmer, raise them.
- **1.2 V core LDO instead of the RP2350's switcher**: an ME6211C12 (U9) feeds DVDD, so there's
  no inductor and none of the switcher's layout rules. The RP2350 datasheet allows this
  (section 6.3.7): VREG_LX is left open, VREG_FB is grounded, and VREG_VIN and VREG_AVDD stay
  powered for the reset and brownout circuits. It's 1.2 V rather than 1.1 V because the
  firmware runs the core at 1.20 V for its 208 MHz overclock. The on-chip regulator still
  starts at power-up but can't drive anything without its inductor; firmware can turn it off
  (VREG.HIZ) to save about 400 µA. The LDO wastes about 0.1 W.
- **DVI on an HDMI socket instead of composite video**: the RP2350's HSTX block, which can
  only drive GPIO12..19, sends DVI (TMDS) to an HDMI type A socket (J8, Molex 208658-1001) on
  the right edge. Each of the eight lines goes through 220 Ω (R24–R31), as on Adafruit's DVI
  Sock and HSTX adapter, and then through a flow-through ESD array (U10, U11, TPD4E05U06) at
  the socket. Pin 18 gets +5V through a Schottky (D5), which some displays need before they'll
  take a picture. DDC, CEC and hot-plug detect are left open: DDC pulls up to 5 V and the free
  GPIOs aren't 5 V tolerant. HSTX can put any lane or the clock, of either polarity, on any of
  its pins, so the pairs are wired in the order the socket's pins come.
- **Sound over HDMI, no line-out or serial port**: HSTX needs eight GPIOs, and the Z80 bus
  needs every other 5 V-tolerant one, so the I2S DAC (and its line-out jack) and the UART
  header are gone; the firmware is to send sound as HDMI audio. The DE-9's I/O expander,
  the real-time clock and the settings EEPROM stay on I2C exactly as in rev 0.1.
- **Bus pins round HSTX**: only GPIO0..39 are 5 V tolerant, and with HSTX on GPIO12..19 the 32
  bus lines take every one of the rest. D0..D7 stay on GPIO0..7 and A0..A3 on GPIO8..11.
  A15..A4 are on GPIO20..31, in reverse, so their tracks fan out to the fingers without
  crossing, and the control lines are on GPIO32..39. Z80_CLK goes to GPIO40 (an ADC pin)
  through one gate of a 74LVC3G34 (U8), whose inputs take 5 V. The red LED (D3) is on the
  I/O expander's GP2 as in rev 0.1, and the green LED (D4) is on GPIO41.
- **Real-time clock**: a DS3231MZ (U5) at 0x68 in place of SMD2's DS1307. It has a
  built-in MEMS resonator, so there's no 32.768 kHz crystal, and it keeps time to about
  ±5 ppm (a few minutes a year). It uses the DS1307's address and time registers, so the
  firmware's `GET TIM` / `GET DAT` and time and date screens work unchanged. Backup is a
  plain CR2032 (BT1) that slides in from the bottom edge; there's no charger.
- **Five M3 holes** (3.2 mm, unplated) for screw posts in a case: top left, between the SPI
  header and the LEDs (H1); lower left corner (H3); top right corner, above the microSD (H4); bottom right, in
  the corner below the HDMI socket (H5); and one near the bottom middle (H2).

## What changed from SMD2

| | SMD2 | Card |
| --- | --- | --- |
| Board | 100 x 70 mm, socket on the bottom edge | 155 x 57 mm card with gold fingers |
| ZX81 connection | edge socket (plugs onto the ZX81) | fingers (stand in a socket on a bus) |
| Video | composite, 2-pin header J8 | DVI on an HDMI socket J8 (HSTX) |
| Audio | I2S DAC, line-out jack | over HDMI (firmware); no DAC or jack |
| DE-9 | bottom side | top side, left edge |
| Serial port (UART) | GPIO40-41, header J10 | none |
| Red LED | GPIO38 (PWM, also sampled audio) | I/O expander GP2 (on/off only) |
| Green LED | GPIO39 | GPIO41 |
| Headers | SWD, UART, SPI, digitized audio | SPI only |
| Real-time clock | DS1307 + 32.768 kHz crystal + CR2032 | DS3231MZ (no crystal) + CR2032 |
| RP2350 core supply | on-chip switcher + 3.3 µH inductor | ME6211C12 LDO at 1.2 V |
| Buttons | top-push SMD, inboard | right-angle THT on the top edge, hand-fitted |
| GPIO0..7 | control lines | D0..D7 |
| GPIO8..11 | A0..A3 | same |
| GPIO12..19 | A4..A11 | HSTX (DVI) |
| GPIO20..31 | A12..A15, D0..D7 | A15..A4 |
| GPIO32..39 | Z80 clock, I2S, video, LEDs | control lines |
| GPIO40..47 | UART, I2C, microSD | Z80 clock (buffered), green LED, I2C, microSD |

**Why the bus moves.** On SMD2 the edge socket is on the bottom of the board. Here the
fingers are on the same side as the RP2350B, which mirrors the left-to-right order. With
U2 turned 90° its GPIO0..31 sweep round its lower-left corner, along its bottom edge toward
the fingers and up its right side. HSTX sits in the middle of that bottom edge (GPIO12..19),
so the bus goes round it: data and A0..A3 to its left, the rest of the address bus up U2's
right side, and the control lines along its top edge. The DVI pairs leave U2's bottom edge
and run right to the HDMI socket, under the address lines, which reach the fingers on
B.Cu.

## Result

Fully routed on four layers (signal, GND, power, signal). DRC with schematic parity and a
zone refill reports no copper, clearance, edge or unconnected errors; what remains is
silkscreen only (reference text over copper, overlapping or near the edge), which the fab
clips. ERC is clean.

| | Card rev 0.2 | Card rev 0.1 | SMD2 |
| --- | --- | --- | --- |
| Vias | 250 | 301 | 268 |
| Signal vias | 118 | 150 | 126 |
| Track length | 3367 mm | 3545 mm | 3520 mm |
| Z80 bus track | 1174 mm | 1095 mm | 1319 mm |

The Z80 bus is shorter than on SMD2 because the fingers run right under U2. Rev 0.2 has less
track and fewer vias than rev 0.1 because the audio DAC, line out and UART header at the
left end are gone. The eight TMDS lines are 23 to 26 mm long with no vias; the two halves of
each pair are within 0.5 mm of each other. Freerouting closed every connection (the first
run left RUN open, and a second run with 200 passes closed it), and no signal runs on the
inner planes. The only inner-layer copper is the +1V2 core rail, a short spur on In2 as on
SMD2. The silkscreen warnings went up from rev 0.1 (mostly references overlapping in the
column of 0402 resistors). The fab clips silkscreen off exposed copper.

![Copper layers](docs/copper-card.png)

## Firmware

`firmware/card-pins.patch` applies to upstream OpenSpand_SW 0.51.0, like SMD2's patch:

```bash
cd OpenSpand/OpenSpand_SW
patch -p1 < /path/to/card/firmware/card-pins.patch
```

It moves every pin to the rev 0.2 map in `firmware/pins.h`. Data reads and writes still use
the low byte of the GPIO registers, exactly as upstream. The address read becomes
`((lo >> 8) & 0x000F) | ((__rbit(lo) << 4) & 0xFFF0)` on one read of the low GPIO
register: A0..A3 sit on GPIO8..11 and A4..A15 on GPIO31..20, reversed, which RBIT (one
instruction on the Cortex-M33) undoes. The video PIO gets GPIO base 16, and Z80_CLK, now
on GPIO40, is index 24 in that window, the same encoding as upstream's GPIO24. SMD2's
[checklist](../smd2/README.md#firmware) applies: timing, and SDK pin handling with a GPIO base.

**The patch doesn't build yet, on purpose.** Rev 0.2 has no composite video, I2S DAC or
serial port, so `pins.h` leaves `VIDEO_SYNC`, `VIDEO_DATA`, `I2S_PIN_*`, `ZX_SER_TX`,
`ZX_SER_RX` and `LED_RED` undefined. Code that still uses them fails to compile instead of
driving a bus pin. What's needed:

- **DVI out over HSTX**, in place of the composite video PIO: core 1 already hands each ZX81
  pixel byte to the video PIO, so it stores it in a line buffer instead, and HSTX, fed by
  DMA with its TMDS encoder on, sends 640 x 480 at 60 Hz, each ZX81 line twice. HSTX bit n
  is GPIO12+n; `HSTX_PIN_n` in `pins.h` says which TMDS line each one is. The lanes go
  D0 on bits 3/2, D1 on 5/4, D2 on 7/6 and the clock on 1/0, positive on the odd bit.
  [Adafruit DVI HSTX](https://github.com/adafruit/Adafruit-DVI-HSTX) and the Pico SDK's
  `dvi_out_hstx_encoder` example both set this up. The DMA interrupt has to go on core 0,
  since core 1 is servicing the Z80 bus. HSTX needs about 126 MHz (25.2 MHz pixels, ten
  bits each, two per HSTX clock), and the firmware's 208 MHz system clock doesn't divide
  down to that. The usual fix is a 252 MHz system clock with HSTX at half of it, and that
  has to be checked against the bus timing, which was tuned at 208 MHz.
- **Sound as HDMI audio**: the AY and beeper output that went to I2S goes into HDMI data
  islands instead, as in [pico_hdmi](https://github.com/fliperama86/pico_hdmi) and
  [frank-hdmi-audio](https://github.com/rh1tech/frank-hdmi-audio). Strictly this sends HDMI
  rather than DVI, which every HDMI display takes. A DVI-only monitor shows the picture and
  stays silent.
- **No serial port**: the serial commands (ports 0xE3 / 0xEB, `OPEN SERIAL`, `OPEN MIDI`,
  `PUT SER`) and the ZXpand serial server have nowhere to go.
- **Red LED**: bit 2 of the I/O expander at 0x27, active low, as in rev 0.1; the green LED
  is on GPIO41.

## Regenerating

From `tools/`:

```bash
python3 gen_lib.py      # project library: edge fingers, Z80_CLK buffer, ESD arrays (and the SMD2 parts)
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
  RP2350B. So are the eight TMDS lines, from U2's HSTX pins through R24..R31 and the ESD
  arrays to the HDMI socket, innermost first, so they run side by side on F.Cu with no
  vias and each pair matched to within about 0.5 mm. Left to Freerouting, they wandered
  round U2 with up to 27 mm between the two halves of a pair.
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
- Hand-fit: DE-9 (J4), the four buttons (SW1–SW4, C&K PTS645VL83-2 LFS), the two 3 mm
  LEDs (D3, D4) and the optional pin header. The HDMI socket (J8, Molex 208658-1001, LCSC C916313) is SMD with through-hole
  shell tabs, so JLC fits it; it uses KiCad's own footprint for that part.

## License

Hardware: CC BY-SA 4.0, as a derivative of OpenSpand HW 1.3.1 by Adam Klotblixt & ZX-Team.
The firmware patch modifies GPL-3.0 code from OpenSpand_SW and is GPL-3.0.
