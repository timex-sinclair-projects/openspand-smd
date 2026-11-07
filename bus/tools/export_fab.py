"""Write fabrication files to hardware/fab/: gerbers + drill (zipped) and the
parts list for hand assembly. Nothing on this board is machine-placed, so there
is no BOM/CPL for JLC assembly.

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
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'


def cli(*args):
    subprocess.run(['kicad-cli'] + list(args), check=True, stdout=subprocess.DEVNULL)


def main():
    gdir = os.path.join(FAB, 'gerbers')
    shutil.rmtree(FAB, ignore_errors=True)
    os.makedirs(gdir)
    # gen_pcb.py leaves the pours unfilled: fill them (DRC does it) before plotting
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '-o',
                    os.path.join(FAB, 'drc.rpt'), PCB], check=True, stdout=subprocess.DEVNULL)
    os.remove(os.path.join(FAB, 'drc.rpt'))
    cli('pcb', 'export', 'gerbers', '--layers', LAYERS, '--subtract-soldermask',
        '--no-protel-ext', '-o', gdir + '/', PCB)
    cli('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
        '--generate-map', '--map-format', 'gerberx2', '-o', gdir + '/', PCB)
    with zipfile.ZipFile(os.path.join(FAB, design.PROJECT + '-gerbers.zip'), 'w') as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)

    with open(os.path.join(FAB, 'hand-solder.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Value', 'Footprint', 'Note'])
        for p in design.parts:
            if p['ref'].startswith('H') or not p.get('in_bom', True):
                continue
            w.writerow([p['ref'], p['value'], p['fp'].split(':')[1], p.get('note', '')])
    print('fab files in', FAB)


if __name__ == '__main__':
    main()
