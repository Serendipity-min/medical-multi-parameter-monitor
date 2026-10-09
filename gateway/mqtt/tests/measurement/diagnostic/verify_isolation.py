"""只读核对诊断生成树、冻结依赖、原链接布局和实际RAM；不执行硬件或扫描。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from build_diagnostic import ALLOWED_PATCH, BASE_OUTPUT, HERE, PINS, PROBE_FILES, PRODUCTION, ROOT, sha

ADDED = {'gateway/mqtt/src/' + name for name in (*PROBE_FILES, 'probe_variant.h')}
BASE_RAM = {'P4': 120160, 'P5': 120208}
BASE_STATIC = {'P4': 87388, 'P5': 87436}

def sections(text):
    result = {}
    for line in text.splitlines():
        found = re.fullmatch(r'(\S+)\s+(\d+)\s+(\d+)', line.strip())
        if found:
            result[found[1]] = {'size': int(found[2]), 'address': int(found[3])}
    for required in ('.text', '.data', '.bss', '._user_heap_stack'):
        if required not in result:
            raise ValueError('section output incomplete')
    return result

def symbol_address(text, name):
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[-1] == name:
            return int(fields[0], 16)
    raise ValueError('required diagnostic symbol absent')

def verify(run):
    run = run.resolve()
    if not run.is_relative_to(BASE_OUTPUT.resolve()):
        raise ValueError('run outside ignored diagnostic directory')
    summary = json.loads((run / 'reports/build-summary.json').read_text(encoding='utf-8'))
    results = {}
    for variant in ('P4', 'P5'):
        record = summary['variants'][variant]
        if record['source_commit'] != PINS[variant] or record['production_bin_sha256'] != PRODUCTION[variant]:
            raise ValueError('frozen variant identity mismatch')
        frozen = json.loads((run / 'reports' / f'{variant}-frozen-inputs.json').read_text())
        source = run / (variant.lower() + '-source')
        current = {file.relative_to(source).as_posix() for file in source.rglob('*') if file.is_file() and '__pycache__' not in file.parts}
        # 生成树未在该目录内编译，所以唯一新增应只有4份probe源/变体头。
        if current != set(frozen) | ADDED:
            raise ValueError('unreviewed generated source file')
        for path, identity in frozen.items():
            actual = sha((source / path).read_bytes())
            expected = record['changes'][path]['after_sha256'] if path in ALLOWED_PATCH else identity['sha256']
            if actual != expected:
                raise ValueError('generated source outside exact overlay changed')
        for name in PROBE_FILES:
            if sha((source / 'gateway/mqtt/src' / name).read_bytes()) != record['probe_sources_sha256'][name]:
                raise ValueError('probe copy identity mismatch')
        if sha((run / 'reports' / f'{variant}-applied.patch').read_bytes()) != record['overlay_sha256']:
            raise ValueError('applied patch receipt mismatch')
        artifacts = run / variant.lower()
        for suffix, key in (('.elf', 'elf_sha256'), ('.bin', 'bin_sha256'), ('.map', 'map_sha256')):
            if sha((artifacts / ('gateway_mqtt' + suffix)).read_bytes()) != record['arm'][key]:
                raise ValueError('diagnostic artifact changed')
        binary = (artifacts / 'gateway_mqtt.bin').read_bytes()
        marker = (variant + '_DIAGNOSTIC_C25_PROFILE_1').encode('ascii')
        if marker not in binary or sha(binary) == PRODUCTION[variant]:
            raise ValueError('diagnostic marker or distinct BIN absent')
        if struct.unpack('<I', binary[:4])[0] != 0x20020000:
            raise ValueError('stack vector layout changed')
        table = sections((run / 'reports' / f'{variant}-sections.txt').read_text())
        static = table['.data']['size'] + table['.bss']['size']
        total = static + table['._user_heap_stack']['size']
        symbols = (run / 'reports' / f'{variant}-symbols.txt').read_text()
        heap_start, heap_end = [symbol_address(symbols, name) for name in ('_heap_start', '_heap_end')]
        if heap_end - heap_start != 24576 or symbol_address(symbols, '_estack') != 0x20020000:
            raise ValueError('reserved heap or stack top changed')
        if not (32768 <= table['._user_heap_stack']['size'] <= 32775):
            raise ValueError('heap/stack reservation changed')
        if len(binary) >= 896 * 1024 or total > 128 * 1024 or static - BASE_STATIC[variant] > 1536 or total - BASE_RAM[variant] > 1536:
            raise ValueError('diagnostic RAM or Flash budget exceeded')
        probe = [line for line in symbols.splitlines() if line.split() and line.split()[-1] == 'probe_state']
        if len(probe) != 1 or int(probe[0].split()[1], 16) > 1536:
            raise ValueError('probe state size not bounded')
        results[variant] = {'source_commit': PINS[variant], 'elf_sha256': record['arm']['elf_sha256'],
                            'bin_sha256': record['arm']['bin_sha256'], 'map_sha256': record['arm']['map_sha256'],
                            'bin_bytes': len(binary), 'sections': table, 'static_ram': static, 'ram_with_reservation': total,
                            'static_ram_delta': static - BASE_STATIC[variant], 'ram_delta': total - BASE_RAM[variant],
                            'ram_remaining': 131072 - total, 'probe_state_bytes': int(probe[0].split()[1], 16),
                            'heap_start': hex(heap_start), 'heap_end': hex(heap_end), 'vendor_files_untouched': True}
    output = {'kind': 'OFFLINE_ISOLATION_VERIFICATION', 'hardware_values': 'NOT_MEASURED',
              'M04': 'BLOCKED_UNSAFE_SENTINEL', 'variants': results}
    return output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    result = verify(args.run)
    file = args.run / 'reports/isolation-resources.json'
    with file.open('x', encoding='utf-8') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({variant: {'ram_delta': record['ram_delta'], 'probe_state_bytes': record['probe_state_bytes'],
                               'bin_sha256': record['bin_sha256']} for variant, record in result['variants'].items()}))

if __name__ == '__main__':
    main()
