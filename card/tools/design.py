"""OpenSpand Card: single source of truth for parts and connectivity.

Every part lists its symbol, footprint, LCSC number and a {pin: net} map.
gen_sch.py turns this into the schematic, gen_pcb.py into the board.
The card is the SMD2 circuit on a 155 x 57 mm card that stands in a ZX81-style
edge socket on an expansion bus. Rev 0.2 replaces the VGA output with DVI on an HDMI
socket, driven by the RP2350's HSTX block (GPIO12..19, fixed in silicon). Sound goes
out over HDMI, so the I2S DAC and line-out are gone, and the serial port with them.
It swaps SMD2's DS1307 real-time clock for a crystal-free DS3231MZ.
"""

PROJECT = 'OpenSpand-Card'

# ---------------------------------------------------------------- footprints
R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
LED0603 = 'LED_SMD:LED_0603_1608Metric'
SOD123 = 'Diode_SMD:D_SOD-123'
HDR = 'Connector_PinHeader_2.54mm:PinHeader_{}_P2.54mm_Vertical'
SJ = 'Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm'

# ------------------------------------------------- JLC basic passives (LCSC)
RES = {'27': 'C25190', '33': 'C23140', '75': 'C4275', '270': 'C22966',
       '470': 'C23179', '1k': 'C21190', '4.7k': 'C23162', '5.1k': 'C23186',
       '10k': 'C25804'}
CAP = {'15p': 'C1644', '2.2n': 'C1604', '100n': 'C14663', '1u': 'C15849',
       '2.2u': 'C23630', '4.7u': 'C19666', '10u': 'C15850', '22u': 'C45783'}

parts = []


def part(ref, sym, value, fp, pins, lcsc='', block='', **kw):
    p = dict(ref=ref, sym=sym, value=value, fp=fp, pins=pins, lcsc=lcsc,
             block=block)
    p.update(kw)
    parts.append(p)
    return p


def R(ref, value, a, b, block):
    return part(ref, 'Device:R', value, R0603, {'1': a, '2': b}, RES[value], block)


def C(ref, value, a, b='GND', block=''):
    fp = C0805 if value in ('10u', '22u') else C0603
    return part(ref, 'Device:C', value, fp, {'1': a, '2': b}, CAP[value], block)


# ===================================================================== power
B = 'Power'
part('D1', 'Device:D_Schottky', 'B5819W', SOD123, {'1': '+5V', '2': '5VZX'}, 'C8598', B,
     note='ZX81 5V -> board, blocks USB backfeed into the ZX81')
part('D2', 'Device:D_Schottky', 'B5819W', SOD123, {'1': '+5V', '2': 'VBUS'}, 'C8598', B,
     note='USB 5V -> board')
part('U1', 'Regulator_Linear:ME6211C33M5', 'ME6211C33M5G', 'Package_TO_SOT_SMD:SOT-23-5',
     {'1': '+5V', '2': 'GND', '3': '+5V', '4': None, '5': '+3V3'}, 'C82942', B)
C('C1', '22u', '+5V', block=B)
C('C2', '10u', '+5V', block=B)
C('C3', '10u', '+3V3', block=B)
C('C4', '10u', '+3V3', block=B)

# ======================================================== ZX81 edge connector
B = 'ZX81 bus'
edge = {
    'A5': '5VZX',  # ~ROMCS held high: internal ROM off
    'C26': '5VZX',  # ~RAMCS held high: internal RAM off
    'A27': '5VZX', 'A23': 'GND', 'A24': 'GND', 'A26': None,
    'A22': 'Z80_CLK',
    'C5': 'Z80_RFSH', 'C6': 'Z80_M1', 'C7': 'Z80_RST', 'C8': None, 'C9': None,
    'C10': None, 'C11': 'Z80_WR', 'C12': 'Z80_RD', 'C13': 'Z80_IORQ',
    'C14': 'Z80_MREQ', 'C15': 'Z80_HALT', 'C16': None, 'C17': None,
    'C24': 'Z80_D0', 'C23': 'Z80_D1', 'C22': 'Z80_D2', 'C19': 'Z80_D3',
    'C18': 'Z80_D4', 'C20': 'Z80_D5', 'C21': 'Z80_D6', 'C27': 'Z80_D7',
}
for i, pin in enumerate(['A21', 'A20', 'A19', 'A18', 'A6', 'A7', 'A8', 'A9',
                         'A10', 'A11', 'A12', 'A13', 'A14', 'A15', 'A16', 'A17']):
    edge[pin] = 'Z80_A%d' % i
part('J1', 'OpenSpandSMD:ZX81_Edge', 'ZX81 edge', 'OpenSpandSMD:ZX81_EdgeFingers', edge, '', B,
     in_bom=False, note='Gold fingers on the card edge (no part)')
C('C5', '1u', 'Z80_RST', block=B)
part('SW1', 'Switch:SW_Push', 'Reset', 'Button_Switch_THT:SW_Tactile_SPST_Angled_PTS645Vx83-2LFS', {'1': 'Z80_RST', '2': 'GND'},
     '', B, dnp=True, mpn='C&K PTS645VL83-2 LFS',
     note='right-angle THT button on the top edge, hand-soldered')

# ==================================================================== RP2350B
B = 'MCU'
# GPIO map chosen for routing. U2 is turned so GPIO0..31 sweep round its
# lower-left corner, along the bottom and up the right side, facing the edge
# fingers below it. HSTX, the only way to DVI, is fixed to GPIO12..19 in the middle
# of the bottom side, so the bus works round it:
#   GPIO0..7    D0..D7 (still the low byte of the GPIO register)
#   GPIO8..11   A0..A3
#   GPIO12..19  HSTX: DVI (TMDS) to the HDMI socket on the right edge
#   GPIO20..31  A15..A4, reversed, so the lines fan out to the fingers without
#               crossing; the firmware gets A4..A15 back with one RBIT
#   GPIO32..39  control lines, in edge-finger order
#   GPIO40..47  3.3 V only (ADC pins, not 5 V tolerant): Z80_CLK through a
#               buffer, green LED, I2C, microSD
# Only GPIO0..39 are 5 V tolerant, and the 32 bus lines fill exactly those not taken
# by HSTX, so the clock goes through U8.
gpio = {
    32: 'Z80_HALT', 33: 'Z80_MREQ', 34: 'Z80_IORQ', 35: 'Z80_RD',
    36: 'Z80_WR', 37: 'Z80_RST', 38: 'Z80_M1', 39: 'Z80_RFSH',
    40: 'Z80_CLK_3V3', 41: 'LED_GREEN', 42: 'I2C_SDA', 43: 'I2C_SCL',
    44: 'SD_MISO', 45: 'SD_CS', 46: 'SD_CLK', 47: 'SD_MOSI',
    # HSTX pairs, in the order the socket's pins come (pin 1 at the top): any GPIO can
    # carry any lane or the clock, of either polarity, in the firmware's HSTX setup
    19: 'HSTX_D2P', 18: 'HSTX_D2N', 17: 'HSTX_D1P', 16: 'HSTX_D1N',
    15: 'HSTX_D0P', 14: 'HSTX_D0N', 13: 'HSTX_CKP', 12: 'HSTX_CKN',
}
for i in range(8):
    gpio[i] = 'Z80_D%d' % i
for i in range(4):
    gpio[8 + i] = 'Z80_A%d' % i
for i in range(4, 16):
    gpio[35 - i] = 'Z80_A%d' % i  # A4 on GPIO31 ... A15 on GPIO20
# RP2350B (QFN-80) pin numbers, from MCU_RaspberryPi:RP2350B
gpio_pin = {4: 1, 5: 2, 6: 3, 7: 4, 8: 6, 9: 7, 10: 8, 11: 9, 12: 11, 13: 12,
            14: 13, 15: 14, 16: 16, 17: 17, 18: 18, 19: 19, 20: 20, 21: 21,
            22: 22, 23: 23, 24: 25, 25: 26, 26: 27, 27: 28, 28: 36, 29: 37,
            30: 38, 31: 39, 32: 40, 33: 42, 34: 43, 35: 44, 36: 45, 37: 46,
            38: 47, 39: 48, 40: 49, 41: 52, 42: 53, 43: 54, 44: 55, 45: 56,
            46: 57, 47: 58, 0: 77, 1: 78, 2: 79, 3: 80}
mcu = {str(gpio_pin[g]): n for g, n in gpio.items()}
for p in (5, 15, 24, 29, 41, 50, 60, 76):
    mcu[str(p)] = '+3V3'  # IOVDD
for p in (10, 32, 51):
    mcu[str(p)] = '+1V2'  # DVDD, from U9
mcu.update({
    '30': 'XIN', '31': 'XOUT', '33': None, '34': None, '35': 'RUN',  # 33, 34: SWCLK, SWDIO left open (no debug header)
    '59': '+3V3',  # ADC_AVDD
    '61': 'VREG_AVDD', '62': 'GND', '63': None, '64': '+3V3', '65': 'GND',  # on-chip regulator off: LX open, FB to GND
    '66': 'USB_DM', '67': 'USB_DP', '68': '+3V3', '69': '+3V3',
    '70': 'QSPI_SD3', '71': 'QSPI_SCLK', '72': 'QSPI_SD0', '73': 'QSPI_SD2',
    '74': 'QSPI_SD1', '75': 'QSPI_SS', '81': 'GND',
})
part('U2', 'MCU_RaspberryPi:RP2350B', 'RP2350B', 'Package_DFN_QFN:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm',
     mcu, 'C42415655', B)
for i in range(8):
    C('C%d' % (10 + i), '100n', '+3V3', block=B)  # one per IOVDD pin
for i in range(3):
    C('C%d' % (18 + i), '100n', '+1V2', block=B)  # DVDD
C('C22', '4.7u', '+3V3', block=B)  # VREG_VIN
C('C23', '4.7u', 'VREG_AVDD', block=B)  # RC filter with R1, per the RP2350 design guide
R('R1', '33', '+3V3', 'VREG_AVDD', B)
# Core supply from an LDO instead of the on-chip switcher (RP2350 datasheet 6.3.7, figure 24):
# no inductor, VREG_LX open, VREG_FB to GND; VREG_VIN and VREG_AVDD stay powered for the
# power-on reset and brownout blocks. 1.2 V, because the firmware runs the core at 1.20 V
# for its 208 MHz overclock.
part('U9', 'Regulator_Linear:ME6211C12M5', 'ME6211C12M5G-N', 'Package_TO_SOT_SMD:SOT-23-5',
     {'1': '+3V3', '2': 'GND', '3': '+3V3', '4': None, '5': '+1V2'}, 'C236672', B,
     note='1.2 V core supply (DVDD)')
C('C46', '1u', '+3V3', block=B)  # U9 input
C('C21', '4.7u', '+1V2', block=B)  # U9 output
C('C24', '100n', '+3V3', block=B)  # USB_OTP_VDD
C('C25', '100n', '+3V3', block=B)  # QSPI_IOVDD
C('C26', '100n', '+3V3', block=B)  # ADC_AVDD
part('Y1', 'Device:Crystal_GND24', '12MHz', 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
     {'1': 'XIN', '2': 'GND', '3': 'XOUT_X', '4': 'GND'}, 'C20625731', B, mpn='ABM8-272-T3',
     note='RP2350-recommended crystal (10 pF, 50 ohm ESR) for the 15 pF caps and 1k R2')
R('R2', '1k', 'XOUT', 'XOUT_X', B)
C('C27', '15p', 'XIN', block=B)
C('C28', '15p', 'XOUT_X', block=B)
R('R3', '10k', '+3V3', 'RUN', B)
C('C29', '100n', 'RUN', block=B)
part('SW2', 'Switch:SW_Push', 'RUN', 'Button_Switch_THT:SW_Tactile_SPST_Angled_PTS645Vx83-2LFS', {'1': 'RUN', '2': 'GND'},
     '', B, dnp=True, mpn='C&K PTS645VL83-2 LFS',
     note='right-angle THT button on the top edge, hand-soldered')
part('SW3', 'Switch:SW_Push', 'BOOTSEL', 'Button_Switch_THT:SW_Tactile_SPST_Angled_PTS645Vx83-2LFS', {'1': 'BOOT', '2': 'GND'},
     '', B, dnp=True, mpn='C&K PTS645VL83-2 LFS',
     note='right-angle THT button on the top edge, hand-soldered')
R('R4', '1k', 'QSPI_SS', 'BOOT', B)

part('U3', 'Memory_Flash:W25Q128JVS', 'W25Q128JVSIQ', 'Package_SO:SOIC-8_5.3x5.3mm_P1.27mm',
     {'1': 'QSPI_SS', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND', '5': 'QSPI_SD0',
      '6': 'QSPI_SCLK', '7': 'QSPI_SD3', '8': '+3V3'}, 'C97521', B)
C('C30', '100n', '+3V3', block=B)

# ======================================================================== USB
B = 'USB'
part('J3', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C',
     'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',
     {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'SH': 'GND',
      'A4': 'VBUS', 'A9': 'VBUS', 'B4': 'VBUS', 'B9': 'VBUS',
      'A5': 'USB_CC1', 'B5': 'USB_CC2', 'A6': 'USB_C_DP', 'B6': 'USB_C_DP',
      'A7': 'USB_C_DM', 'B7': 'USB_C_DM', 'A8': None, 'B8': None}, 'C165948', B)
R('R5', '5.1k', 'USB_CC1', 'GND', B)
R('R6', '5.1k', 'USB_CC2', 'GND', B)
R('R7', '27', 'USB_C_DP', 'USB_DP', B)
R('R8', '27', 'USB_C_DM', 'USB_DM', B)

# ===================================================================== I2C
B = 'I2C'
R('R9', '4.7k', '+3V3', 'I2C_SDA', B)
R('R10', '4.7k', '+3V3', 'I2C_SCL', B)
part('U4', 'OpenSpandSMD:MCP23009-E_SS', 'MCP23009-E/SS', 'Package_SO:SSOP-20_5.3x7.2mm_P0.65mm',
     {'1': '+3V3', '2': None, '3': 'I2C_SCL', '4': 'I2C_SDA', '5': '+3V3', '6': '+3V3',
      '7': None, '8': 'CONFIG', '9': 'SPI_CS', '10': None, '11': None, '12': 'LED_RED',  # GP2: red LED, active low
      '13': 'JOY_F', '14': 'JOY_R', '15': 'JOY_L', '16': 'JOY_D', '17': 'JOY_U',
      '18': None, '19': None, '20': 'GND'}, 'C629436', B,
     note='ADDR tied to VDD -> 0x27 like upstream; open-drain GPIO are 5V tolerant')
C('C31', '100n', '+3V3', block=B)
part('SW4', 'Switch:SW_Push', 'Config', 'Button_Switch_THT:SW_Tactile_SPST_Angled_PTS645Vx83-2LFS', {'1': 'CONFIG', '2': 'GND'},
     '', B, dnp=True, mpn='C&K PTS645VL83-2 LFS',
     note='right-angle THT button on the top edge, hand-soldered')
part('J4', 'OpenSpandSMD:DE9_Male', 'Joystick',
     'OpenSpandSMD:DSUB-9_Male_Horizontal_P2.77x2.84mm_EdgePinOffset4.94mm_Housed_MountingHolesOffset7.48mm',
     {'1': 'JOY_U', '2': 'JOY_D', '3': 'JOY_L', '4': 'JOY_R', '5': 'JOY_P5', '6': 'JOY_F',
      '7': 'JOY_P7', '8': 'GND', '9': None, '0': 'GND'}, '', B,
     note='Atari-style joystick, hand-soldered THT')
part('JP1', 'Jumper:SolderJumper_2_Open', '5V pin 7', SJ, {'1': '+5V', '2': 'JOY_P7'}, '', B, in_bom=False)
part('JP2', 'Jumper:SolderJumper_2_Open', '5V pin 5', SJ, {'1': '+5V', '2': 'JOY_P5'}, '', B, in_bom=False)

part('U6', 'Memory_EEPROM:24LC32', 'FT24C32A', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
     {'1': 'GND', '2': 'GND', '3': 'GND', '4': 'GND', '5': 'I2C_SDA', '6': 'I2C_SCL',
      '7': 'GND', '8': '+3V3'}, 'C232883', B,
     note='0x50, replaces the AT24C32 on the tiny-RTC module')
C('C33', '100n', '+3V3', block=B)
part('U5', 'Timer_RTC:DS3231MZ', 'DS3231MZ+TRL', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
     {'1': None, '2': '+3V3', '3': None, '4': None, '5': 'GND', '6': 'VBAT',
      '7': 'I2C_SDA', '8': 'I2C_SCL'}, 'C107410', B,
     note='0x68, DS1307-compatible time registers; MEMS resonator, no crystal')
C('C32', '100n', '+3V3', block=B)
part('BT1', 'Device:Battery_Cell', 'CR2032', 'Battery:BatteryHolder_Keystone_3034_1x20mm',
     {'1': 'VBAT', '2': 'GND'}, 'C5213768', B, mpn='Keystone 3034TR',
     note='plain replaceable coin cell; the DS3231 does not charge it')

# =================================================================== SD card
B = 'SD card'
part('J5', 'OpenSpandSMD:MicroSD_TF-01A', 'microSD', 'OpenSpandSMD:TF-01A',
     {'1': 'SD_DAT2', '2': 'SD_CS', '3': 'SD_MOSI', '4': '+3V3', '5': 'SD_CLK',
      '6': 'GND', '7': 'SD_MISO', '8': 'SD_DAT1', '9': None,
      '10': 'GND', '11': 'GND', '12': 'GND', '13': 'GND'}, 'C91145', B)
R('R11', '10k', '+3V3', 'SD_CS', B)
R('R12', '10k', '+3V3', 'SD_MOSI', B)
R('R13', '10k', '+3V3', 'SD_MISO', B)
R('R14', '10k', '+3V3', 'SD_DAT1', B)
R('R15', '10k', '+3V3', 'SD_DAT2', B)
C('C34', '100n', '+3V3', block=B)
C('C35', '10u', '+3V3', block=B)
part('J6', 'Connector_Generic:Conn_02x03_Odd_Even', 'External SPI', HDR.format('2x03'),
     {'1': 'SPI_CS', '2': 'SD_MISO', '3': 'GND', '4': 'SD_CLK', '5': '+5V', '6': 'SD_MOSI'},
     '', B, dnp=True)

# ========================================================= video, LEDs, I/O
B = 'Video & I/O'
# Z80_CLK has no 5 V-tolerant GPIO left, so one gate of a 74LVC3G34 (5 V-tolerant
# inputs, 3.3 V supply) brings it down to GPIO40. The other two gates are unused.
part('U8', 'OpenSpandSMD:74LVC3G34', 'SN74LVC3G34DCUR', 'Package_SO:VSSOP-8_2.3x2mm_P0.5mm',
     {'1': 'Z80_CLK', '2': None, '3': 'GND', '4': 'GND', '5': None,
      '6': 'GND', '7': 'Z80_CLK_3V3', '8': '+3V3'}, 'C130024', B,
     note='Z80 clock, 5 V in, 3.3 V out to GPIO40; gates 2 and 3 unused, inputs grounded')
C('C45', '100n', '+3V3', block=B)
# DVI from HSTX: each TMDS line through 220R (as on Adafruit's DVI Sock and HSTX adapter),
# then two flow-through ESD arrays at the socket. +5V on pin 18 (the sink may need it
# to see a source) through a Schottky so a powered display can't feed the card. DDC,
# CEC and hot-plug detect are left open: DDC's pull-ups go to 5 V, and the only free
# GPIOs left aren't 5 V tolerant.
# 0402 so the eight fit a 1.1 mm-pitch column between U2 and the ESD arrays.
TMDS = ['D2P', 'D2N', 'D1P', 'D1N', 'D0P', 'D0N', 'CKP', 'CKN']
for i, n in enumerate(TMDS):
    part('R%d' % (24 + i), 'Device:R', '220', 'Resistor_SMD:R_0402_1005Metric',  # R24..R31
         {'1': 'HSTX_' + n, '2': 'TMDS_' + n}, 'C25091', B)
# TPD4E05U06 flow-through: each line enters on one side and leaves on the other
# (1-10, 2-9, 4-7, 5-6), so both pads of a pair carry the line.
for ref, (a, b) in (('U10', ('D2', 'D1')), ('U11', ('D0', 'CK'))):
    part(ref, 'OpenSpandSMD:TPD4E05U06', 'TPD4E05U06DQAR', 'Package_SON:USON-10_2.5x1.0mm_P0.5mm',
         {'1': 'TMDS_%sP' % a, '10': 'TMDS_%sP' % a, '2': 'TMDS_%sN' % a, '9': 'TMDS_%sN' % a,
          '4': 'TMDS_%sP' % b, '7': 'TMDS_%sP' % b, '5': 'TMDS_%sN' % b, '6': 'TMDS_%sN' % b,
          '3': 'GND', '8': 'GND'}, 'C138714', B, note='ESD protection for two TMDS pairs')
part('D5', 'Device:D_Schottky', 'B5819W', SOD123, {'1': 'HDMI_5V', '2': '+5V'}, 'C8598', B,
     note='+5V to the HDMI socket; blocks backfeed from the display')
part('J8', 'Connector:HDMI_A', 'HDMI', 'Connector_Video:HDMI_A_Molex_208658-1001_Horizontal',
     {'1': 'TMDS_D2P', '2': 'GND', '3': 'TMDS_D2N', '4': 'TMDS_D1P', '5': 'GND', '6': 'TMDS_D1N',
      '7': 'TMDS_D0P', '8': 'GND', '9': 'TMDS_D0N', '10': 'TMDS_CKP', '11': 'GND', '12': 'TMDS_CKN',
      '13': None, '14': None, '15': None, '16': None, '17': 'GND', '18': 'HDMI_5V', '19': None,
      'SH': 'GND'}, 'C916313', B, mpn='Molex 2086581001',
     note='HDMI type A socket carrying DVI (and HDMI audio, in firmware)')
part('D3', 'Device:LED', 'Red', LED0603, {'1': 'LED_RED', '2': 'LED_R_A'}, 'C2286', B,
     note='driven by the I/O expander (GP2, open drain, active low)')
part('D4', 'Device:LED', 'Green', LED0603, {'1': 'LED_G_K', '2': 'LED_GREEN'}, 'C2289', B)
R('R22', '1k', '+3V3', 'LED_R_A', B)
R('R23', '1k', 'LED_G_K', 'GND', B)

B = 'Mechanical'
for i in range(5):
    part('H%d' % (i + 1), 'Mechanical:MountingHole', 'M3', 'MountingHole:MountingHole_3.2mm_M3',
         {}, '', B, in_bom=False)

# Nets without a power-output pin get a PWR_FLAG so ERC is satisfied.
PWR_FLAGS = ['GND', '+5V', '5VZX', 'VBUS', 'VREG_AVDD', 'VBAT', 'HDMI_5V']


def nets():
    out = {}
    for p in parts:
        for pin, n in p['pins'].items():
            if n:
                out.setdefault(n, []).append((p['ref'], pin))
    return out

# Placement hints for gen_pcb.py: put these parts next to a specific pin.
NEAR = {'C%d' % (10 + i): ('U2', str(p)) for i, p in enumerate((5, 15, 24, 29, 41, 50, 60, 76))}
NEAR.update({'C18': ('U2', '10'), 'C19': ('U2', '32'), 'C20': ('U2', '51'),
             'C21': ('U9', '5'), 'C46': ('U9', '1'), 'C22': ('U2', '64'), 'C23': ('U2', '61'), 'R1': ('U2', '61'),
             'C24': ('U2', '68'), 'C25': ('U2', '69'), 'C26': ('U2', '59'),
             'R2': ('U2', '31'), 'C27': ('Y1', '1'), 'C28': ('Y1', '3'),
             'R7': ('U2', '67'), 'R8': ('U2', '66'), 'R4': ('U2', '75'),
             'C30': ('U3', '8'), 'C45': ('U8', '8'),
             'C31': ('U4', '1'), 'C32': ('U5', '2'), 'C33': ('U6', '8'),
             'C34': ('J5', '4'), 'C35': ('J5', '4'), 'D5': ('J8', '18'),
             'C3': ('U1', '5'), 'C4': ('U1', '5'), 'C1': ('U1', '1'), 'C2': ('U1', '1'),
             'C5': ('SW1', '1')})
