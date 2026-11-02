"""Write JLCPCB fabrication files to hardware/fab/:
gerbers + drill (zipped), BOM (LCSC numbers) and CPL (pick and place).

Uses kicad-cli; run with any Python 3.
"""
import csv
import os
import shutil
import subprocess
import zipfile

import design

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, 'hardware')
FAB = os.path.join(HW, 'fab')
PCB = os.path.join(HW, design.PROJECT + '.kicad_pcb')
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'


def cli(*args):
    subprocess.run(['kicad-cli'] + list(args), check=True, stdout=subprocess.DEVNULL)


def main():
    gdir = os.path.join(FAB, 'gerbers')
    shutil.rmtree(FAB, ignore_errors=True)
    os.makedirs(gdir)
    cli('pcb', 'export', 'gerbers', '--layers', LAYERS, '--subtract-soldermask',
        '--no-protel-ext', '-o', gdir + '/', PCB)
    cli('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
        '--generate-map', '--map-format', 'gerberx2', '-o', gdir + '/', PCB)
    with zipfile.ZipFile(os.path.join(FAB, design.PROJECT + '-gerbers.zip'), 'w') as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)

    # BOM: one line per LCSC part, assembled parts only
    groups = {}
    for p in design.parts:
        if p['lcsc'] and not p.get('dnp') and p.get('in_bom', True):
            k = (p['value'], p['fp'].split(':')[1], p['lcsc'])
            groups.setdefault(k, []).append(p['ref'])
    with open(os.path.join(FAB, 'BOM-JLCPCB.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (val, fp, lcsc), refs in sorted(groups.items(), key=lambda g: g[1][0]):
            w.writerow([val, ','.join(refs), fp, lcsc])

    # Parts the buyer sources and solders: no LCSC number, or marked DNP
    with open(os.path.join(FAB, 'hand-solder.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Value', 'Footprint', 'Note'])
        for p in design.parts:
            if p['ref'].startswith(('H', 'JP')) or not p.get('in_bom', True):
                continue
            if not p['lcsc'] or p.get('dnp'):
                w.writerow([p['ref'], p['value'], p['fp'].split(':')[1], p.get('note', '')])

    # CPL from KiCad's position file
    pos = os.path.join(FAB, 'pos.csv')
    cli('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
        '--exclude-dnp', '-o', pos, PCB)
    lcsc_refs = {p['ref'] for p in design.parts if p['lcsc'] and not p.get('dnp')}
    with open(pos) as fi, open(os.path.join(FAB, 'CPL-JLCPCB.csv'), 'w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in csv.DictReader(fi):
            if r['Ref'] in lcsc_refs:
                w.writerow([r['Ref'], r['PosX'] + 'mm', r['PosY'] + 'mm',
                            'Top' if r['Side'] == 'top' else 'Bottom', r['Rot']])
    os.remove(pos)
    print('fab files in', FAB)


if __name__ == '__main__':
    main()
