"""OpenSpand Card: single source of truth for parts and connectivity.

Every part lists its symbol, footprint, LCSC number and a {pin: net} map.
gen_sch.py turns this into the schematic, gen_pcb.py into the board.
The card is the SMD2 circuit on a 155 x 57 mm card that stands in a ZX81-style
edge socket on an expansion bus. Its data and control GPIO groups are swapped from
SMD2's (see firmware/ in this folder), and it swaps SMD2's DS1307 real-time clock for a crystal-free DS3231MZ.
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
part('SW1', 'Switch:SW_Push', 'Reset', 'OpenSpandSMD:SW_TS-1102US-C-I', {'1': 'Z80_RST', '2': 'GND'},
     'C2885134', B, mpn='XKB TS-1102US-C-I', note='right-angle button on the top edge')

# ==================================================================== RP2350B
B = 'MCU'
# GPIO map chosen for routing. U2 is turned so GPIO0..31 sweep round its
# lower-left corner, along the bottom and up the right side, facing the edge
# fingers below it in their left-to-right order: data bus (whose fingers are
# on the left), address bus, then the control lines (fingers on the right).
# GPIO32..47 face the top edge and carry only 3.3 V signals, so no 5 V bus line
# sits on an ADC pin. Same peripheral pins as SMD2; the bus groups are reversed.
gpio = {
    24: 'Z80_HALT', 25: 'Z80_MREQ', 26: 'Z80_IORQ', 27: 'Z80_RD',
    28: 'Z80_WR', 29: 'Z80_RST', 30: 'Z80_M1', 31: 'Z80_RFSH',
    32: 'Z80_CLK', 33: 'I2S_BCLK', 34: 'I2S_WS', 35: 'I2S_DOUT',
    36: 'VGA_HSYNC', 37: 'VGA_VSYNC', 38: 'LED_RED', 39: 'LED_GREEN',
    40: 'VGA_VIDEO', 41: None, 42: 'I2C_SDA', 43: 'I2C_SCL',
    44: 'SD_MISO', 45: 'SD_CS', 46: 'SD_CLK', 47: 'SD_MOSI',
}
for i in range(8):
    gpio[i] = 'Z80_D%d' % i
for i in range(16):
    gpio[8 + i] = 'Z80_A%d' % i
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
    mcu[str(p)] = '+1V1'  # DVDD
mcu.update({
    '30': 'XIN', '31': 'XOUT', '33': 'SWCLK', '34': 'SWDIO', '35': 'RUN',
    '59': '+3V3',  # ADC_AVDD
    '61': 'VREG_AVDD', '62': 'GND', '63': 'VREG_LX', '64': '+3V3', '65': '+1V1',
    '66': 'USB_DM', '67': 'USB_DP', '68': '+3V3', '69': '+3V3',
    '70': 'QSPI_SD3', '71': 'QSPI_SCLK', '72': 'QSPI_SD0', '73': 'QSPI_SD2',
    '74': 'QSPI_SD1', '75': 'QSPI_SS', '81': 'GND',
})
part('U2', 'MCU_RaspberryPi:RP2350B', 'RP2350B', 'Package_DFN_QFN:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm',
     mcu, 'C42415655', B)
for i in range(8):
    C('C%d' % (10 + i), '100n', '+3V3', block=B)  # one per IOVDD pin
for i in range(3):
    C('C%d' % (18 + i), '100n', '+1V1', block=B)  # DVDD
C('C21', '4.7u', '+1V1', block=B)  # core regulator output
C('C22', '4.7u', '+3V3', block=B)  # VREG_VIN
C('C23', '4.7u', 'VREG_AVDD', block=B)  # RC filter with R1, per the RP2350 design guide
R('R1', '33', '+3V3', 'VREG_AVDD', B)
part('L1', 'Device:L', '3.3uH', 'OpenSpandSMD:L_AOTA-B201610', {'1': '+1V1', '2': 'VREG_LX'},  # pad 1: dot
     'C42411119', B, mpn='AOTA-B201610S3R3-101-T',
     note='Use the RP2350-recommended Abracon part; mind the orientation dot')
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
part('SW2', 'Switch:SW_Push', 'RUN', 'OpenSpandSMD:SW_TS-1102US-C-I', {'1': 'RUN', '2': 'GND'},
     'C2885134', B, mpn='XKB TS-1102US-C-I', note='right-angle button on the top edge')
part('SW3', 'Switch:SW_Push', 'BOOTSEL', 'OpenSpandSMD:SW_TS-1102US-C-I', {'1': 'BOOT', '2': 'GND'},
     'C2885134', B, mpn='XKB TS-1102US-C-I', note='right-angle button on the top edge')
R('R4', '1k', 'QSPI_SS', 'BOOT', B)
part('J2', 'Connector_Generic:Conn_01x03', 'SWD', HDR.format('1x03'),
     {'1': 'SWCLK', '2': 'GND', '3': 'SWDIO'}, '', B, dnp=True)

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
      '7': None, '8': 'CONFIG', '9': 'SPI_CS', '10': None, '11': None, '12': None,
      '13': 'JOY_F', '14': 'JOY_R', '15': 'JOY_L', '16': 'JOY_D', '17': 'JOY_U',
      '18': None, '19': None, '20': 'GND'}, 'C629436', B,
     note='ADDR tied to VDD -> 0x27 like upstream; open-drain GPIO are 5V tolerant')
C('C31', '100n', '+3V3', block=B)
part('SW4', 'Switch:SW_Push', 'Config', 'OpenSpandSMD:SW_TS-1102US-C-I', {'1': 'CONFIG', '2': 'GND'},
     'C2885134', B, mpn='XKB TS-1102US-C-I', note='right-angle button on the top edge')
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

# ===================================================================== audio
B = 'Audio'
part('U7', 'Audio:PCM5102A', 'PCM5102A', 'Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm',
     {'1': '+3V3', '2': 'DAC_CAPP', '3': 'GND', '4': 'DAC_CAPM', '5': 'DAC_VNEG',
      '6': 'DAC_OUTL', '7': 'DAC_OUTR', '8': '+3V3', '9': 'GND', '10': 'GND',
      '11': 'GND', '12': 'GND', '13': 'I2S_BCLK', '14': 'I2S_DOUT', '15': 'I2S_WS',
      '16': 'GND', '17': 'DAC_XSMT', '18': 'DAC_LDOO', '19': 'GND', '20': '+3V3'},
     'C107671', B, note='SCK grounded: PLL runs from BCK (32fs, 16-bit)')
C('C36', '2.2u', 'DAC_CAPP', 'DAC_CAPM', B)
C('C37', '2.2u', 'DAC_VNEG', block=B)
C('C38', '1u', 'DAC_LDOO', block=B)
C('C39', '100n', '+3V3', block=B)  # CPVDD
C('C40', '100n', '+3V3', block=B)  # AVDD
C('C41', '100n', '+3V3', block=B)  # DVDD
C('C42', '10u', '+3V3', block=B)
R('R16', '10k', '+3V3', 'DAC_XSMT', B)
R('R17', '470', 'DAC_OUTL', 'AUDIO_L', B)
R('R18', '470', 'DAC_OUTR', 'AUDIO_R', B)
C('C43', '2.2n', 'AUDIO_L', block=B)
C('C44', '2.2n', 'AUDIO_R', block=B)
part('J7', 'Connector_Audio:AudioJack4', 'Line out', 'Connector_Audio:Jack_3.5mm_PJ320D_Horizontal',
     {'T': 'AUDIO_L', 'R1': 'AUDIO_R', 'R2': 'GND', 'S': 'GND'}, 'C431535', B)

# ========================================================= video, LEDs, I/O
B = 'Video & I/O'
# VGA, 640x480-style timing at 60 Hz (31.5 kHz lines): the firmware scan-doubles the
# ZX81's NTSC picture. One GPIO carries the mono video; a triple buffer drives R, G
# and B through 270R each (0.7 V into the monitor's 75R), about 9 mA per output.
part('U8', 'OpenSpandSMD:74LVC3G34', 'SN74LVC3G34DCUR', 'Package_SO:VSSOP-8_2.3x2mm_P0.5mm',
     {'1': 'VGA_VIDEO', '2': 'VGA_B_D', '3': 'VGA_VIDEO', '4': 'GND', '5': 'VGA_G_D',
      '6': 'VGA_VIDEO', '7': 'VGA_R_D', '8': '+3V3'}, 'C130024', B,
     note='mono video to all three colour lines')
C('C45', '100n', '+3V3', block=B)
R('R19', '270', 'VGA_R_D', 'VGA_R', B)
R('R20', '270', 'VGA_G_D', 'VGA_G', B)
R('R21', '270', 'VGA_B_D', 'VGA_B', B)
R('R24', '33', 'VGA_HSYNC', 'VGA_HS', B)
R('R25', '33', 'VGA_VSYNC', 'VGA_VS', B)
part('J8', 'Connector:DE15_Socket_HighDensity_MountingHoles', 'VGA',
     'Connector_Dsub:DSUB-15-HD_Socket_Horizontal_P2.29x1.90mm_EdgePinOffset3.03mm_Housed_MountingHolesOffset4.94mm',
     {'1': 'VGA_R', '2': 'VGA_G', '3': 'VGA_B', '4': None, '5': 'GND', '6': 'GND', '7': 'GND',
      '8': 'GND', '9': None, '10': 'GND', '11': None, '12': None, '13': 'VGA_HS', '14': 'VGA_VS',
      '15': None, 'SH': 'GND'}, '', B, mpn='BOOMELE VGA-002',
     note='VGA socket, hand-soldered THT (LCSC C138387)')
part('D3', 'Device:LED', 'Red', LED0603, {'1': 'LED_R_K', '2': 'LED_RED'}, 'C2286', B)
part('D4', 'Device:LED', 'Green', LED0603, {'1': 'LED_G_K', '2': 'LED_GREEN'}, 'C2289', B)
R('R22', '1k', 'LED_R_K', 'GND', B)
R('R23', '1k', 'LED_G_K', 'GND', B)
part('J9', 'Connector_Generic:Conn_01x04', 'Digitized audio', HDR.format('1x04'),
     {'1': '+5V', '2': 'GND', '3': 'LED_RED', '4': 'LED_GREEN'}, '', B, dnp=True)

B = 'Mechanical'
for i in range(5):
    part('H%d' % (i + 1), 'Mechanical:MountingHole', 'M3', 'MountingHole:MountingHole_3.2mm_M3',
         {}, '', B, in_bom=False)

# Nets without a power-output pin get a PWR_FLAG so ERC is satisfied.
PWR_FLAGS = ['GND', '+5V', '5VZX', 'VBUS', '+1V1', 'VREG_AVDD', 'VBAT']


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
             'C21': ('U2', '65'), 'C22': ('U2', '64'), 'C23': ('U2', '61'), 'R1': ('U2', '61'),
             'C24': ('U2', '68'), 'C25': ('U2', '69'), 'C26': ('U2', '59'),
             'R2': ('U2', '31'), 'C27': ('Y1', '1'), 'C28': ('Y1', '3'),
             'R7': ('U2', '67'), 'R8': ('U2', '66'), 'R4': ('U2', '75'),
             'C30': ('U3', '8'), 'C45': ('U8', '8'),
             'R19': ('J8', '1'), 'R20': ('J8', '2'), 'R21': ('J8', '3'), 'R24': ('J8', '13'), 'R25': ('J8', '14'), 'C31': ('U4', '1'), 'C32': ('U5', '2'), 'C33': ('U6', '8'),
             'C39': ('U7', '1'), 'C40': ('U7', '8'), 'C41': ('U7', '20'), 'C42': ('U7', '20'), 'C38': ('U7', '18'),
             'C36': ('U7', '2'), 'C37': ('U7', '5'), 'C34': ('J5', '4'), 'C35': ('J5', '4'),
             'C3': ('U1', '5'), 'C4': ('U1', '5'), 'C1': ('U1', '1'), 'C2': ('U1', '1'),
             'C5': ('SW1', '1')})
