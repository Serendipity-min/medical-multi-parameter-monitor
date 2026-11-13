"""普通ARM脱机构建USB入口变体；不改G1工程、驱动、码表或历史摘要，不调用下载。"""
from pathlib import Path
import contextlib
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
KEIL = Path('D:/keil')


@contextlib.contextmanager
def mapped(path):
    # 老Keil使用ASCII盘符；只释放本函数成功创建的临时映射，不碰用户已有映射。
    drive = next(x + ':' for x in 'RSTUVW' if not Path(x + ':/').exists())
    subprocess.run(['subst', drive, str(path)], check=True)
    try:
        yield drive + '/'
    finally:
        subprocess.run(['subst', drive, '/d'], check=True)


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run = ROOT / 'build' / ('usb-arm-' + stamp)
    run.mkdir(parents=True)
    receipt = {'scope': 'ORDINARY_USB_VARIANT_ARM_BUILD', 'hardware_operations': [], 'status': 'PREPARING'}
    # 复制准确输入到独立构建目录；G1文件仅作构建输入读取，不改原件。
    for folder in ['src', 'platform', 'g2s-usb']:
        shutil.copytree(ROOT / folder, run / folder, ignore=shutil.ignore_patterns('__pycache__'))
    files = [p for folder in ['src', 'platform', 'g2s-usb'] for p in (run / folder).rglob('*') if p.is_file()]
    (run / 'input-manifest.json').write_text(json.dumps({'files': [
        {'path': p.relative_to(run).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]},
        ensure_ascii=False, indent=2), encoding='utf-8')
    tree = ET.parse(ROOT / 'MPM_ECG_SOURCE.uvprojx')
    tree.find('.//TargetName').text = 'MPM_ECG_SOURCE_USB'
    common = tree.find('.//TargetCommonOption')
    for tag, value in [('OutputDirectory', '.\\output\\'), ('ListingPath', '.\\output\\'), ('OutputName', 'MPM_ECG_SOURCE_USB')]:
        common.find(tag).text = value
    include = tree.find('.//Cads/VariousControls/IncludePath')
    include.text = '.\\src;.\\platform;.\\g2s-usb'
    group = tree.find('.//Group/Files')
    for node in list(group):
        if node.findtext('FileName') == 'main.c':
            node.find('FileName').text = 'main_usb.c'
            node.find('FilePath').text = '.\\g2s-usb\\main_usb.c'
    node = ET.SubElement(group, 'File')
    for tag, value in [('FileName', 'console.c'), ('FileType', '1'), ('FilePath', '.\\g2s-usb\\console.c')]:
        ET.SubElement(node, tag).text = value
    tree.write(run / 'USB.uvprojx', encoding='utf-8', xml_declaration=True)
    try:
        with mapped(run.resolve()) as prefix:
            cp = subprocess.run([str(KEIL / 'UV4/UV4.exe'), '-r', prefix + 'USB.uvprojx', '-o', prefix + 'build.log'],
                                capture_output=True, timeout=180)
        (run / 'launcher.stdout.log').write_bytes(cp.stdout)
        (run / 'launcher.stderr.log').write_bytes(cp.stderr)
        log = (run / 'build.log').read_text(errors='replace')
        receipt['exit_code'] = cp.returncode
        counts = re.search(r'(\d+) Error\(s\),\s*(\d+) Warning\(s\)', log)
        if counts:
            receipt.update(errors=int(counts[1]), warnings=int(counts[2]))
        if cp.returncode or not counts or int(counts[1]):
            raise RuntimeError('ARM构建失败，保留本次全部输入/日志')
        match = re.search(r'Code=(\d+) RO-data=(\d+) RW-data=(\d+) ZI-data=(\d+)', log)
        if not match:
            raise RuntimeError('缺少真实资源报告')
        axf = run / 'output/MPM_ECG_SOURCE_USB.axf'
        exe = KEIL / 'ARM/ARMCC/bin/fromelf.exe'
        for mode, name in [('--bin', 'MPM_ECG_SOURCE_USB.bin'), ('-s', 'symbols.txt')]:
            subprocess.run([str(exe), mode, '--output', str(run / name), str(axf)], check=True, capture_output=True, timeout=60)
        symbols = (run / 'symbols.txt').read_text(errors='replace')
        for symbol in ['Console_Feed', 'g_source_dma_buffer', 'DMA1_Stream5_IRQHandler', 'TIM6_DAC_IRQHandler']:
            if symbol not in symbols:
                raise RuntimeError('缺少必要符号：' + symbol)
        address = re.search(r'\bg_source_dma_buffer\s+0x([0-9a-fA-F]+)', symbols)
        if not address or not 0x20000000 <= int(address[1], 16) < 0x20020000:
            raise RuntimeError('DMA未落普通SRAM')
        receipt.update(status='PASS', resources=dict(zip(['code', 'ro', 'rw', 'zi'], map(int, match.groups()))),
                       dma_buffer_address='0x' + address[1],
                       outputs={p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                                for p in [axf, run / 'MPM_ECG_SOURCE_USB.bin', *list((run / 'output').glob('*.map'))]})
    except BaseException as error:
        receipt.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        raw = json.dumps(receipt, ensure_ascii=False, indent=2) + '\n'
        (run / 'receipt.json').write_text(raw, encoding='utf-8')
        (ROOT.parent / 'artifacts/ecg-source/g2s' / ('usb-arm-' + stamp + '.json')).write_text(raw, encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=True))


if __name__ == '__main__':
    main()
