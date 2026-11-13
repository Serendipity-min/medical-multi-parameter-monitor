# 公开副本：空UID只允许脱机准备，硬件模式仍强制校验完整预期UID。
"""标准采集包的身份、只增证据、独占轮次和清单管理；本模块不连接硬件。"""
from contextlib import contextmanager
import csv
import datetime as dt
import math
import os
from pathlib import Path
import re
import uuid

from acq_protocol import (DATASET_INDEX_HEADERS, dump_strict_json, load_strict_json,
                          now_utc_iso, sha256_file, write_strict_csv)

BASE = Path(__file__).resolve().parent.parent
PROFILE = Path(__file__).resolve().parent / 'profiles/ads1292r_swd_ring24_v1_9f58a890.json'
VERSION = 'acq/1.0.1'


def unique_id(prefix):
    return prefix + '-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12]


def require(ok, message):
    # 身份和完整性门禁不用 assert，避免 python -O 绕过。
    if not ok:
        raise ValueError(message)


def within(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts, '清单路径必须在采集包内')
    target = (root / path).resolve()
    require(target.is_relative_to(root), '清单或符号链接越出采集包')
    return target


def tool_identity():
    # 绑定实际导入的模块文件，而不是仅靠一个手写版本号。
    names = ['acq.py', 'acq_storage.py', 'acq_processing.py', 'acq_swd.py',
             'acq_protocol.py', 'stable_slot_export.py']
    root = Path(__file__).resolve().parent
    return {name: sha256_file(root / name) for name in names}


def create_run(dataset, sample, condition, input_kind, fixture, profile=PROFILE,
               duration=150, warmup=30, uid='', run_id=None,
               hr_setpoint=None, resp_setpoint=None):
    dataset = Path(dataset).resolve()
    run_id = run_id or unique_id('run')
    require(bool(re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id)), 'run_id 只允许字母数字下划线和连字符')
    require(1 <= duration <= 300 and 0 <= warmup < duration, '时长须 1～300 s，预热小于采集时长')
    require(input_kind in {'ACTIVE_HARDWARE_SIMULATOR', 'INTERNAL_TEST_SIGNAL', 'SOFTWARE_FIXTURE',
                          'PASSIVE_PHANTOM', 'HUMAN_DECLARED', 'UNKNOWN'}, '未知输入类别')
    require(all(v is None or (math.isfinite(v) and v > 0) for v in (hr_setpoint,resp_setpoint)),
            '设定值须为正的有限数，未知值省略')
    profile_obj = load_strict_json(Path(profile))
    run = dataset / 'runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    for folder in ('raw', 'derived'):
        (run / folder).mkdir()
    session = load_strict_json(BASE / '采集协议_v1.0_模板/session.template.json')
    session.update(record_status='PREPARED', dataset_id=dataset.name, sample_id=sample,
                   condition_id=condition, run_id=run_id, created_utc=now_utc_iso())
    session['input'].update(declared_kind=input_kind, verified_kind='UNKNOWN', model=fixture)
    session['input'].update(ecg_hr_setpoint_bpm=hr_setpoint, resp_setpoint_per_min=resp_setpoint)
    session['device'].update(model='STM32F407ZG', sensor_model='ADS1292R', expected_uid=uid.upper())
    binding = profile_obj['firmware_binding']
    session['firmware'].update(bin_sha256=binding['bin_sha256'], elf_sha256=binding['elf_sha256'])
    session['firmware']['identity_meaning'] = 'EXPECTED_PROFILE_NOT_OBSERVED_BOARD_IDENTITY'
    session['tool'].update(version=VERSION, adapter_id=profile_obj['adapter_id'],
                           adapter_version=profile_obj['adapter_version'],
                           symbol_file_sha256=binding['symbol_file_sha256'])
    session['tool']['files_sha256'] = tool_identity()
    session['timebase'].update(source_seq_semantics='DRDY_IRQ_COUNT_NOT_INDEPENDENT_ADC_COUNTER',
                              device_tick_unit='ms', device_tick_bits=32,
                              device_tick_hz_nominal=1000, irq_cycles_hz_nominal=168000000,
                              host_monotonic_clock_identity='Python time.monotonic_ns, local process epoch')
    session['plan'].update(warmup_s=warmup, analysis_window_s=duration-warmup,
                          maximum_wall_time_s=duration+60, capture_duration_s=duration,
                          nominal_sample_rate_hz=250, poll_interval_ms=100,
                          approved_hardware_action_list=['READ_IDENTITY_AND_FLASH_TWICE',
                              'ONE_RESET_AND_RUN', 'LIVE_READ_ONLY_POLL',
                              'ONE_FINAL_HALT_AND_RAM_READ', 'RESUME_AND_CONFIRM'])
    channels = load_strict_json(BASE / '采集协议_v1.0_模板/channels.template.json')
    # 示例镜像的设定值与“物理校准已验证”分开，单位仍保持 adc_code。
    for channel in channels['channels']:
        channel.update(nominal_sample_rate_hz=250, gain=4, reference_voltage_v=2.42,
                       register_config_source_ref='BOUND_IMAGE_DESIGN_SETTINGS_NOT_REGISTER_READBACK')
    dump_strict_json(profile_obj, run / 'adapter_profile.json')
    session['tool']['adapter_profile_sha256'] = sha256_file(run / 'adapter_profile.json')
    dump_strict_json(session, run / 'session.json')
    dump_strict_json(channels, run / 'channels.json')
    update_index(run)
    return run


def check_configuration(run):
    run = Path(run).resolve()
    session = load_strict_json(run / 'session.json')
    channels = load_strict_json(run / 'channels.json')
    profile = load_strict_json(run / 'adapter_profile.json')
    require(session['run_id'] == run.name, 'run_id 与目录不符')
    require(session['protocol_version'] == profile['protocol_version'] == channels['protocol_version'] == '1.0',
            '协议版本不符')
    require(sha256_file(run / 'adapter_profile.json') == session['tool']['adapter_profile_sha256'],
            '适配配置 SHA 漂移；不能改地址后沿用旧身份')
    ring = profile['slot_ring']
    require(profile['adapter_id'] == 'ads1292r_swd_ring24' and ring['slot_bytes'] == 24
            and ring['capacity'] == 128 and ring['chunk_bytes'] == 3072,
            '当前入口仅实现 128×24 B SWD 适配器')
    require(int(ring['status_mask'], 0) == 0xF01FFF and int(ring['status_expected'], 0) == 0xC00000,
            'STATUS 规则与当前适配器不符')
    require([c['channel_id'] for c in channels['channels']] == ['resp', 'ecg'], '通道布局不符')
    require(all(c['valid_bits'] == 24 and c['raw_type'] == 'signed_integer'
                and c['raw_unit'] == 'adc_code' for c in channels['channels']), '通道原始类型不符')
    ram_end = 0x20020000
    for key, length in [('slots_addr', 3072), ('head_addr', 4), ('tail_addr', 4)]:
        addr = int(ring[key], 0)
        require(0x20000000 <= addr and addr+length <= ram_end, '槽地址越出允许 SRAM 区域')
    formats = {'u8': 1, 'i8': 1, 'u16': 2, 'i16': 2, 'u32': 4, 'i32': 4, 'f32': 4}
    keys = set()
    for field in profile['symbol_table']:
        key = field['module'] + '.' + field['field']
        require(key not in keys, '重复状态字段: ' + key)
        keys.add(key)
        require(field['value_type'] in formats and field['byte_length'] == formats[field['value_type']],
                '状态字段类型/长度不符')
        require(field['endianness'] == 'little', '当前适配器状态字段须小端')
        addr = int(field['address'], 0)
        require(0x20000000 <= addr and addr+field['byte_length'] <= ram_end, '状态地址越界')
    stats_names = ['irq_count','captured','delivered','bad_status','spi_errors','queue_overflow',
                   'queue_peak','init_errors','long_gap_count','min_irq_gap_cycles','max_irq_gap_cycles','max_read_cycles']
    for number, name in enumerate(stats_names):
        members = [f for f in profile['symbol_table'] if f['c_symbol'] == 's_stats.'+name]
        require(len(members) == 1 and int(members[0]['address'],0) == 0x2000020c+4*number
                and members[0]['value_type'] == 'u32', '冻结 ADC 统计结构成员布局不符')
    require(session['timebase']['device_tick_unit'] == 'ms'
            and session['timebase']['device_tick_bits'] == 32
            and session['timebase']['device_tick_hz_nominal'] == 1000
            and session['timebase']['irq_cycles_hz_nominal'] == 168000000,
            '当前适配器仅实现冻结的 ms/DWT 时基')
    require(0 <= session['plan']['warmup_s'] < session['plan']['capture_duration_s'] <= 300,
            '计划的预热/采集时长不符')
    require(session['plan']['warmup_s'] + session['plan']['analysis_window_s'] == session['plan']['capture_duration_s'],
            '预热与分析窗口总长不符合本轮计划')
    for field in profile['symbol_table']:
        for ref in ('valid_field_ref', 'sample_tick_field_ref', 'sample_seq_field_ref'):
            require(not field.get(ref) or field[ref] in keys, '状态关联字段不存在')
    return session, channels, profile


def offline_precheck(run, binary=None, elf=None, symbols=None):
    session, _, profile = check_configuration(run)
    paths = {'bin': Path(binary) if binary else BASE / '心率+呼吸/OBJ/HR_TFT.bin',
             'elf': Path(elf) if elf else BASE / '心率+呼吸/OBJ/HR_TFT.axf',
             'symbol_file': Path(symbols) if symbols else BASE / '排查证据_20261010/R6_模拟器连续采样_20261012T185429/normal-symbols.txt'}
    for key, path in paths.items():
        require(path.is_file(), '缺少本地身份文件: ' + str(path))
        require(sha256_file(path) == profile['firmware_binding'][key+'_sha256'], key+' SHA 不符合适配器')
    require(session['tool']['files_sha256'] == tool_identity(), '工具自 init 后发生变化，请创建新轮次')
    # 同名符号必须用地址和长度共同绑定，不靠出现顺序或数值接近猜归属。
    symbol_text = paths['symbol_file'].read_text(errors='replace')
    for field in profile['symbol_table']:
        if field['c_symbol'].startswith('s_stats.'):
            # 结构成员不是独立 ELF 符号；核对所属结构基址及完整尺寸。
            require(re.search(r'\bs_stats\s+0x2000020c\s+.*?0x30\s*$', symbol_text, re.M | re.I) is not None,
                    'ADC 统计结构基址/尺寸不符')
            continue
        addr = int(field['address'], 0)
        array = re.fullmatch(r'(\w+)\[(\d+)\]', field['c_symbol'])
        if array:
            # ELF 只给出数组整体符号，元素须通过冻结的基址、长度和索引核对。
            base_addr = addr-int(array.group(2))*field['byte_length']
            pattern = rf'\b{re.escape(array.group(1))}\s+0x{base_addr:08x}\s+.*?0x([0-9a-f]+)\s*$'
            match = re.search(pattern, symbol_text, re.M | re.I)
            require(match is not None and (int(array.group(2))+1)*field['byte_length'] <= int(match.group(1),16),
                    '数组符号范围不符: '+field['c_symbol'])
            continue
        pattern = rf'\b{re.escape(field["c_symbol"])}\s+0x{addr:08x}\s+.*?0x{field["byte_length"]:x}\s*$'
        require(re.search(pattern, symbol_text, re.M | re.I) is not None,
                '符号地址/长度不符: '+field['module']+'.'+field['field'])
    return {'status': 'PASS_OFFLINE_ONLY', 'board_identity': 'NOT_CHECKED',
            'hardware_operations': session['plan']['approved_hardware_action_list'],
            'files': {key: {'path': str(p.resolve()), 'sha256': sha256_file(p)} for key, p in paths.items()}}


@contextmanager
def exclusive(path):
    # 排他创建防止两个采集进程复用目录；只释放本次成功获取的锁。
    path = Path(path)
    with path.open('x', encoding='ascii') as stream:
        stream.write(str(os.getpid()))
    try:
        yield
    finally:
        path.unlink()


def seal_run(run):
    files = [run / name for name in ('session.json', 'channels.json', 'adapter_profile.json',
                                     'acquisition_receipt.json')]
    files += sorted((run / 'raw').rglob('*'))
    entries = [{'path': p.relative_to(run).as_posix(), 'size_bytes': p.stat().st_size,
                'sha256': sha256_file(p)} for p in files if p.is_file()]
    require(not (run / 'raw_manifest.json').exists(), '原件清单已封存，禁止重新封存覆盖')
    dump_strict_json({'protocol_version': '1.0', 'self_excluded': True, 'files': entries}, run / 'raw_manifest.json')


def verify_package(root, manifest='raw_manifest.json', raw=False):
    root = Path(root).resolve()
    obj = load_strict_json(root / manifest)
    entries = obj.get('files', [])
    require(bool(entries), '清单为空')
    seen = set()
    for item in entries:
        rel = item['path']
        require(rel != manifest and rel not in seen, '清单自引用或重复路径')
        seen.add(rel)
        file = within(root, rel)
        require(file.is_file() and file.stat().st_size == int(item['size_bytes'])
                and sha256_file(file) == item['sha256'], '原件或产物身份漂移: '+rel)
    if raw:
        required = {'session.json', 'channels.json', 'adapter_profile.json', 'acquisition_receipt.json'}
        required |= {p.relative_to(root).as_posix() for p in (root / 'raw').rglob('*') if p.is_file()}
        require(seen == required, '原件清单未完整覆盖或混入派生文件')
    return {'status': 'PASS', 'checked_files': len(entries), 'manifest_sha256': sha256_file(root / manifest)}


def update_index(run, analysis_id='', identity='UNKNOWN', integrity='NOT_EVALUATED', reason='PREPARED'):
    dataset = run.parent.parent
    index = dataset / 'dataset_index.csv'
    session = load_strict_json(run / 'session.json')
    with exclusive(dataset / '.dataset-index.lock'):
        rows = []
        if index.exists():
            with index.open(encoding='utf-8', newline='') as stream:
                reader = csv.DictReader(stream)
                require(reader.fieldnames == DATASET_INDEX_HEADERS, '数据集索引表头不符')
                rows = list(reader)
        repeat = 1 + sum(r['sample_id'] == session['sample_id'] and r['condition_id'] == session['condition_id']
                         and r['run_id'] != session['run_id'] for r in rows)
        row = dict(zip(DATASET_INDEX_HEADERS, ['']*len(DATASET_INDEX_HEADERS)))
        row.update(dataset_id=session['dataset_id'], sample_id=session['sample_id'],
                   condition_id=session['condition_id'], repeat_index=repeat, run_id=session['run_id'],
                   run_path=run.relative_to(dataset).as_posix(), session_sha256=sha256_file(run/'session.json'),
                   raw_manifest_sha256=sha256_file(run/'raw_manifest.json') if (run/'raw_manifest.json').exists() else '',
                   analysis_id=analysis_id, identity_status=identity, integrity_status=integrity,
                   reference_status='NONE', comparison_disposition='OBSERVATIONAL_ONLY', reason=reason)
        if session['input']['declared_kind'] == 'ACTIVE_HARDWARE_SIMULATOR' and any(
                session['input'].get(k) is not None for k in ('ecg_hr_setpoint_bpm','resp_setpoint_per_min')):
            row['reference_status'] = 'SETPOINT'
        rows = [r for r in rows if r['run_id'] != session['run_id']] + [row]
        temporary = dataset / (unique_id('index')+'.tmp')
        write_strict_csv(temporary, DATASET_INDEX_HEADERS, rows)
        temporary.replace(index)
