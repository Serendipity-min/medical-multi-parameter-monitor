"""用同版 ARM 编译器从冻结诊断头文件生成 ProbeState 布局；仅访问本地文件。"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[4]
DIAG = ROOT / 'gateway/mqtt/tests/measurement/diagnostic'
BUILD = ROOT / 'gateway/mqtt/build/h16-diagnostic/r2-layout'
TOOLCHAIN = Path(r'C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin')
GCC = TOOLCHAIN / 'arm-none-eabi-gcc.exe'
NM = TOOLCHAIN / 'arm-none-eabi-nm.exe'
READELF = TOOLCHAIN / 'arm-none-eabi-readelf.exe'
FROZEN_HEADERS = {
    'probe_events.h': 'a13ca7a6399ac1dbe22cb92ba8961b1a0484ce63c8449815558a4db6cd6f6487',
    'probe_config.h': 'f805e6baeb5b730e6deac0822f13dd81ca1578dd2530d0d1df60171175405b1a',
}
ELF = {
    'P4': ('gateway/mqtt/build/h16-diagnostic/run-20261008T105757767802Z/p4/gateway_mqtt.elf',
           '1074cab9da56dd091a596d7ff3341d4ab7413c455a85149d5a05d54ede5a23e7'),
    'P5': ('gateway/mqtt/build/h16-diagnostic/run-20261008T105757767802Z/p5/gateway_mqtt.elf',
           'f70e2d043ca6b08c6d5820263a07122caeaafccc7e3b4faf2da977da0a5dbeca'),
}
TYPES = {
    'ProbeState': ('magic profile variant marker_address core_hz initialized irq_flags clock_seq clock_lo '
                   'clock_hi last_cycle last_ms tick_head tick_tail tick_dropped tick_armed ticks '
                   'foreground_flags dropped_observations unmatched_ticks serial depth window_generation '
                   'window_start_ms boundary_skipped_ticks heap_error_base tick_drop_base spans aggregate '
                   'event_count events network_us network_valid_mask recovery_generation first_business_id '
                   'cache_before cache_after cache_snapshot_mask cache_drained_observed first_live_us '
                   'first_replay_us live_observed replay_observed heap_peak_bytes heap_enomem_count').split(),
    'ProbeAggregate': 'success failure invalid min_cycles max_cycles reserved inclusive_cycles direct_child_cycles'.split(),
    'ProbeSpan': 'cycle millisecond scope serial generation reserved direct_child_cycles'.split(),
    'ProbeTick': 'tick cycle'.split(),
    'ProbeEvent': 'scope start end bound_ms'.split(),
    'ProbeCache': 'cache lost replay drop'.split(),
    'ProbeFrameId': 'node stream seq epoch boot'.split(),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_text():
    # 数组长度由编译器计算，nm 符号大小即 sizeof 或 offsetof+1；不手写 ARM 对齐偏移。
    lines = ['#include <stddef.h>', '#include "probe_events.h"']
    for typ, fields in TYPES.items():
        lines.append(f'unsigned char size__{typ}[sizeof({typ})];')
        for field in fields:
            lines.append(f'unsigned char off__{typ}__{field}[offsetof({typ}, {field}) + 1];')
    lines += ['unsigned char size__u32[sizeof(uint32_t)];',
              'unsigned char size__u64[sizeof(uint64_t)];']
    return '\n'.join(lines) + '\n'


def generate(build_dir=BUILD):
    build_dir = Path(build_dir).resolve()
    if not build_dir.is_relative_to((ROOT / 'gateway/mqtt/build/h16-diagnostic').resolve()):
        raise RuntimeError('OUTPUT_OUTSIDE_IGNORED_BUILD')
    if build_dir.exists() and any(build_dir.iterdir()):
        raise RuntimeError('REFUSE_OVERWRITE_LAYOUT_RUN')
    for tool in (GCC, NM, READELF):
        if not tool.is_file():
            raise RuntimeError('ARM_TOOLCHAIN_MISSING')
    for name, expected in FROZEN_HEADERS.items():
        if not (DIAG / name).is_file() or sha(DIAG / name) != expected:
            raise RuntimeError('FROZEN_HEADER_DRIFT')
    build_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for variant, (relative_elf, expected_elf) in ELF.items():
        elf = ROOT / relative_elf
        if not elf.is_file() or sha(elf) != expected_elf:
            raise RuntimeError('DIAGNOSTIC_ELF_IDENTITY')
        out = build_dir / variant.lower()
        out.mkdir(exist_ok=True)
        variant_header = out / 'probe_variant.h'
        source = out / 'layout.c'
        obj = out / 'layout.o'
        variant_header.write_text(f'#define PROBE_VARIANT_ID {variant[-1]}U\n', encoding='ascii')
        source.write_text(source_text(), encoding='ascii')
        command = [str(GCC), '-mcpu=cortex-m4', '-mthumb', '-mfpu=fpv4-sp-d16',
                   '-mfloat-abi=hard', '-std=c11', '-O0', '-fno-common',
                   '-I' + str(DIAG), '-I' + str(out), '-c', str(source), '-o', str(obj)]
        subprocess.run(command, check=True, capture_output=True)
        header = subprocess.check_output([str(READELF), '-h', str(obj)], text=True)
        if '2\'s complement, little endian' not in header or 'ELF32' not in header:
            raise RuntimeError('ARM_ABI_ENDIANNESS')
        symbols = subprocess.check_output([str(NM), '-S', '--defined-only', str(obj)], text=True)
        sizes = {}
        for line in symbols.splitlines():
            match = re.fullmatch(r'[0-9a-f]+\s+([0-9a-f]+)\s+[A-Za-z]\s+(\w+)', line)
            if match:
                sizes[match.group(2)] = int(match.group(1), 16)
        types = {}
        for typ, fields in TYPES.items():
            types[typ] = {'size': sizes[f'size__{typ}'],
                          'fields': {field: sizes[f'off__{typ}__{field}'] - 1 for field in fields}}
        if types['ProbeState']['size'] != 1264 or sizes['size__u32'] != 4 or sizes['size__u64'] != 8:
            raise RuntimeError('ARM_LAYOUT_SIZE_DRIFT')
        # 已冻结 ELF 的 nm 符号大小必须与新编译的类型大小一致。
        original_nm = ROOT / f'gateway/mqtt/build/h16-diagnostic/run-20261008T105757767802Z/reports/{variant}-symbols.txt'
        match = re.search(r'^([0-9a-f]+)\s+([0-9a-f]+)\s+B\s+probe_state$',
                          original_nm.read_text(encoding='utf-8'), re.M)
        if not match or int(match.group(2), 16) != types['ProbeState']['size']:
            raise RuntimeError('ELF_PROBE_SYMBOL_SIZE_DRIFT')
        marker = re.search(r'^([0-9a-f]+)\s+([0-9a-f]+)\s+[RT]\s+probe_build_marker$',
                           original_nm.read_text(encoding='utf-8'), re.M)
        if not marker:
            raise RuntimeError('ELF_MARKER_SYMBOL_MISSING')
        results[variant] = {'elf_sha256': expected_elf, 'probe_state_address': int(match.group(1), 16),
                            'marker_address': int(marker.group(1), 16),
                            'probe_state_bytes': types['ProbeState']['size'], 'layout_object_sha256': sha(obj),
                            'types': types}
    if results['P4']['types'] != results['P5']['types']:
        raise RuntimeError('P4_P5_LAYOUT_DIFFER')
    result = {'layout_version': 'C25_ARM_GCC14_2_PROBE_V2', 'endianness': 'little',
              'abi': 'cortex-m4-hard-float', 'compiler': subprocess.check_output([str(GCC), '--version'], text=True).splitlines()[0],
              'probe_events_h_sha256': sha(DIAG / 'probe_events.h'),
              'probe_config_h_sha256': sha(DIAG / 'probe_config.h'), 'variants': results}
    target = build_dir / 'probe-layout-v2.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--output-dir', type=Path, default=BUILD)
        print(generate(parser.parse_args().output_dir))
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError, RuntimeError):
        print('INVALID_OFFLINE_LAYOUT_BUILD')
        raise SystemExit(2)
