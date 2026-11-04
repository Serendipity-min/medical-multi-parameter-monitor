"""M1 逐板离线构建；复用现有 Keil/ARM GCC，不连接设备或启动网络。"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_sources(tree, project, sources):
    group = ET.SubElement(tree.find('.//Groups'), 'Group')
    ET.SubElement(group, 'GroupName').text = 'FIVE_NODE_ROLE'
    files = ET.SubElement(group, 'Files')
    for source in sources:
        entry = ET.SubElement(files, 'File')
        ET.SubElement(entry, 'FileName').text = source.name
        ET.SubElement(entry, 'FileType').text = '1'
        ET.SubElement(entry, 'FilePath').text = '..\\' + str(source.relative_to(project))


def keil(role):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT / 'node-b/build' / f'five-node-{role}-{stamp}'
    project = out / 'firmware'
    source = ROOT / ('node-a/STM32F407_HOSPITAL' if role in ('A', 'E') else 'node-b/firmware/biov2/实验固件')
    shutil.copytree(source, project)
    xml = project / ('USER/STM32F407_Template.uvprojx' if role in ('A', 'E') else 'USER/BIO_V2.uvprojx')
    tree = ET.parse(xml)
    controls = tree.find('.//Cads/VariousControls')
    define = controls.find('Define')
    define.text = (define.text + ',' if define.text else '') + f'MP_FIVE_NODE_{role}'
    tree.find('.//Cads/uC99').text = '1'
    if role == 'E':
        shutil.copyfile(ROOT / 'node-e/main.c', project / 'USER/main.c')
        shutil.copyfile(ROOT / 'node-e/e_canopen.c', project / 'HARDWARE/CANopen/canopen_app.c')
        excluded = {'usart.c', 'dc_hmi.c', 'app_bloodoxygen.c', 'uno.c', 'node_status.c'}
    elif role == 'D':
        shutil.copyfile(ROOT / 'node-d/main.c', project / 'USER/main.c')
        shutil.copytree(ROOT / 'node-b/canopen', project / 'B4')
        shutil.copytree(ROOT / 'gateway/third_party/CANopenNode', project / 'CANopenNode')
        shutil.copytree(ROOT / 'node-b/temperature', project / 'B5_TEMP')
        shutil.copyfile(ROOT / 'node-d/d_canopen.c', project / 'B4/b_canopen_app.c')
        excluded = {'stm32f4xx_it.c', 'spi.c', 'ads1292.c', 'systick.c', 'beep.c', 'hr_page.c',
                    'can.c', 'canopen.c', 'arm_cortexM4lf_math.lib', 'bio_v2.c', 'cmd_queue.c',
                    'cmd_process.c', 'hmi_user_uart.c', 'hw_config.c', 'ulitity.c', 'ecg_frame_queue.c'}
        controls.find('IncludePath').text = '..\\B4;..\\CANopenNode;..\\B5_TEMP;' + controls.findtext('IncludePath')
        vendor = project / 'CANopenNode'
        add_sources(tree, project, [*sorted((project / 'B4').glob('*.c')), vendor / 'CANopen.c',
                                   *sorted((vendor / '301').glob('*.c')), vendor / '303/CO_LEDs.c',
                                   *[project / 'B5_TEMP' / f for f in ('gy641.c', 'b_temperature.c', 'b_temp_screen.c')]])
    else:
        excluded = set()
    for files in tree.findall('.//Files'):
        for entry in list(files):
            if entry.findtext('FileName') in excluded:
                files.remove(entry)
    # 不复用原工程对象，输出路径局限于本次构建副本。
    tree.find('.//TargetCommonOption/OutputDirectory').text = '.\\Objects\\'
    tree.find('.//TargetCommonOption/ListingPath').text = '.\\Listings\\'
    tree.write(xml, encoding='utf-8', xml_declaration=True)
    for folder in ('USER/Objects', 'USER/Listings', 'OBJ'):
        (project / folder).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'node-b/acquisition/工具'))
    from acq_swd import ascii_mapping
    log = project / 'build.log'
    with ascii_mapping(project) as prefix:
        result = subprocess.run(['D:/keil/UV4/UV4.exe', '-r', prefix + 'USER/' + xml.name,
                                 '-o', prefix + 'build.log'], capture_output=True, timeout=180)
    text = log.read_text(encoding='utf-8', errors='replace')
    (out / 'launcher.log').write_bytes(result.stdout + result.stderr)
    resources = re.search(r'Program Size: Code=(\d+) RO-data=(\d+) RW-data=(\d+) ZI-data=(\d+)', text)
    success = result.returncode == 0 and resources is not None and '0 Error(s)' in text
    report = dict(role=role, node_id={'A': 1, 'D': 4, 'E': 5}[role], status='FAIL',
                  scope='OFFLINE_BUILD_NOT_INSTALLED', native_exit=result.returncode,
                  resources=list(map(int, resources.groups())) if resources else None,
                  builder_sha256=digest(Path(__file__)), log_sha256=digest(log))
    if success:
        axfs = list((project / 'USER/Objects').glob('*.axf'))
        if len(axfs) != 1:
            raise RuntimeError('EXPECTED_ONE_AXF')
        axf = out / f'FIVE_NODE_{role}.axf'
        shutil.copyfile(axfs[0], axf)
        binary = out / f'FIVE_NODE_{role}.bin'
        symbols = out / f'FIVE_NODE_{role}.symbols.txt'
        for mode, target in (('--bin', binary), ('-s', symbols)):
            subprocess.run(['D:/keil/ARM/ARMCC/bin/fromelf.exe', mode, '--output', str(target), str(axf)], check=True, capture_output=True)
        maps = list((project / 'USER/Listings').glob('*.map'))
        if len(maps) != 1:
            raise RuntimeError('EXPECTED_ONE_MAP')
        mapping = out / f'FIVE_NODE_{role}.map'
        shutil.copyfile(maps[0], mapping)
        report.update(status='PASS', artifacts={f.name: dict(bytes=f.stat().st_size, sha256=digest(f)) for f in (binary, axf, symbols, mapping)})
    report['source_sha256'] = {str(f.relative_to(project)): digest(f) for f in project.rglob('*') if f.is_file() and f.suffix.lower() in ('.c', '.h', '.s', '.uvprojx')}
    (out / 'receipt.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(out.relative_to(ROOT), report['status'])
    if not success:
        print(text[-6000:])
    return int(not success)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['A', 'B', 'C', 'D', 'E'])
    args = parser.parse_args()
    if args.role == 'B':
        return subprocess.call([sys.executable, str(ROOT / 'node-b/tools/build_b4_arm.py'), '--candidate-r6'])
    if args.role == 'C':
        return subprocess.call([sys.executable, str(ROOT / 'gateway/dual_can/build_arm.py'), '--b5', '--egress-final',
                                '--tri', '--unified', '--split-flash', '--five-node'])
    return keil(args.role)


if __name__ == '__main__':
    raise SystemExit(main())
