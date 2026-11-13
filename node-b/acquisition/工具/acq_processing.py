"""标准包的纯脱机导出、表征和多轮对比；不调用 J-Link、串口或烧录程序。"""
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import statistics
import struct

from acq_protocol import (SAMPLES_HEADERS, FIRMWARE_STATE_HEADERS, OBSERVATIONS_HEADERS, REFERENCE_HEADERS,
                          decode_firmware_state_snapshot, dump_strict_json, load_strict_json,
                          loads_strict_json, sha256_file, write_strict_csv, write_events_jsonl)
from acq_storage import (check_configuration, require, unique_id, update_index,
                         verify_package, within, tool_identity, VERSION)
from stable_slot_export import StableSlots, unpack_slot_fields, validate_sequence


def add_event(events, run_id, kind, details, ref='', boot='', segment='', seq=None):
    events.append({'event_id': f'event_{len(events)+1:06d}', 'run_id': run_id,
                   'boot_id': boot or None, 'segment_id': segment or None, 'type': kind,
                   'device_seq_start': seq, 'device_seq_end': seq,
                   'host_request_ns': None, 'host_confirmation_ns': None,
                   'details': details, 'source_ref': ref})


def make_samples(session, collector, selected, events):
    """仅导出无启动歧义的记录；时间是段内相对时间，名义时基不称标定时间。"""
    run_id = session['run_id']
    rows, segments, mapping = [], [], {}
    if len(selected.boots) != 1 or selected.ambiguous_reset_chunks:
        add_event(events, run_id, 'TIME_AMBIGUOUS',
                  {'reason': '观察提示复位/跨代，但没有独立启动边界，拒绝拼接所有样本'})
        return rows, segments, mapping
    boot = selected.boots[0]
    observations = {}
    for obs in collector.observations:
        if obs.validation_status == 'VALID_FORMAT':
            observations.setdefault((obs.boot_id, obs.source_seq, obs.record_sha256), obs)
    prev = None
    segment, elapsed, start, count, wraps = 0, 0, 0, 0, 0
    profile_hz = session['timebase'].get('irq_cycles_hz_nominal')
    for seq, blob in selected.frames_by_boot[boot].items():
        fields = unpack_slot_fields(blob)
        ms, cycles = fields['device_tick_raw'], fields['irq_cycles_raw']
        reason = None
        if prev:
            delta_ms = (ms-prev['device_tick_raw']) & 0xffffffff
            delta_cycles = (cycles-prev['irq_cycles_raw']) & 0xffffffff
            if seq != prev['source_seq']+1:
                reason = 'SOURCE_GAP'
                add_event(events, run_id, reason, {'first_missing': prev['source_seq']+1,
                          'last_missing': seq-1}, boot=boot, seq=seq)
            elif delta_ms == 0 or delta_ms > 12000:
                reason = 'TIME_AMBIGUOUS'
            elif profile_hz and abs(delta_cycles/profile_hz*1000-delta_ms) > 10:
                reason = 'TIME_AMBIGUOUS'
            elif fields['flags_raw']:
                reason = 'SOURCE_FLAGS_BOUNDARY'
        if prev is None or reason:
            if prev:
                segments.append({'boot_id': boot, 'segment_id': f'seg_{segment:04d}',
                                 'first_seq': start, 'last_seq': prev['source_seq'],
                                 'distinct_seq_events': count, 'span_us': elapsed,
                                 'endpoint_sps_nominal': (count-1)*1e6/elapsed if elapsed else None,
                                 'dwt_wraps': wraps})
            if reason and reason != 'SOURCE_GAP':
                add_event(events, run_id, 'TIME_AMBIGUOUS', {'reason': reason,
                          'flags_preserved': fields['flags_raw']}, boot=boot, seq=seq)
            segment += 1
            elapsed, start, count, wraps = 0, seq, 0, 0
        else:
            elapsed += delta_ms * 1000
            wraps += int(cycles < prev['irq_cycles_raw'])
        seg = f'seg_{segment:04d}'
        mapping[(boot, seq)] = seg
        digest = hashlib.sha256(blob).hexdigest()
        obs = observations.get((boot, seq, digest))
        ref = f'{obs.source_path}@{obs.byte_offset}+24' if obs else ''
        for channel, raw in [('resp', fields['ch1_raw']), ('ecg', fields['ch2_raw'])]:
            rows.append(dict(zip(SAMPLES_HEADERS, [run_id, boot, seg, seq, ms, elapsed, cycles,
                channel, raw, fields['status_raw'], fields['flags_raw'],
                selected.integrity_by_boot_seq.get((boot, seq)),
                selected.provenance_by_boot_seq.get((boot, seq)),
                selected.observation_count_by_boot_seq.get((boot, seq)), ref])))
        count += 1
        prev = fields
    if prev:
        segments.append({'boot_id': boot, 'segment_id': f'seg_{segment:04d}', 'first_seq': start,
                         'last_seq': prev['source_seq'], 'distinct_seq_events': count,
                         'span_us': elapsed, 'endpoint_sps_nominal': (count-1)*1e6/elapsed if elapsed else None,
                         'dwt_wraps': wraps})
    return rows, segments, mapping


def export_run(run):
    run = Path(run).resolve()
    raw_check = verify_package(run, raw=True)
    session, _, profile = check_configuration(run)
    receipt = load_strict_json(run/'acquisition_receipt.json')
    analysis = run / 'derived' / unique_id('analysis')
    analysis.mkdir(exist_ok=False)
    collector = StableSlots(raise_on_paused_conflict=False)
    events = []
    io_path = run/'raw/io.jsonl'
    io = [loads_strict_json(line) for line in io_path.read_text(encoding='utf-8').splitlines()] if io_path.exists() else []
    timing = {item.get('file'): item for item in io if item.get('file')}
    for item in io:
        command = item.get('command')
        if command in {'h','g'}:
            kind = 'HALT_REQUEST' if command == 'h' else 'RUN_REQUEST'
            add_event(events, session['run_id'], kind, {'operation': command}, 'raw/io.jsonl')
            events[-1]['host_request_ns'] = item.get('request_ns')
            status = item.get('dhcsr')
            if item.get('confirmation_ns') is not None and status is not None:
                confirmed = (bool(int(status) & (1<<17)) if command == 'h' else not bool(int(status) & (1<<17)))
                if confirmed:
                    add_event(events, session['run_id'], 'HALT_CONFIRMED' if command == 'h' else 'RUN_CONFIRMED',
                              {'dhcsr': status, 'meaning': '确认边界，不是实际切换瞬间'}, 'raw/io.jsonl')
                    events[-1].update(host_request_ns=item.get('request_ns'), host_confirmation_ns=item.get('confirmation_ns'))
        elif item.get('error'):
            add_event(events, session['run_id'], 'HOST_IO_ERROR', {'reason': item['error']}, 'raw/io.jsonl')
    processing_errors = []
    def poll_number(file):
        # 旧脚本可能不补零；按实际编号排序，不能把 slot_10 排到 slot_2 之前制造假复位。
        return int(file.stem.split('_',1)[1])
    for file in sorted((run/'raw').glob('slot_*.bin'), key=poll_number):
        rel = file.relative_to(run).as_posix()
        try:
            collector.add_running_chunk(file.read_bytes(), rel)
        except ValueError as exc:
            processing_errors.append(str(exc))
            add_event(events, session['run_id'], 'HOST_IO_ERROR', {'reason': str(exc)}, rel)
    final = run/'raw/final-paused-ram.bin'
    ram = None
    if final.exists() and receipt.get('paused_snapshot_evidence') in {'DHCSR_CONFIRMED', 'IMPORTED_DECLARATION'}:
        try:
            ram = final.read_bytes()
            require(len(ram) == 131072, '最终 RAM 长度不是 128 KiB')
            require(not collector.ambiguous_reset_chunks and len(collector.versions_by_boot) == 1,
                    '启动归属不明，不能用尾段强行覆盖')
            offset = int(profile['slot_ring']['slots_addr'], 0)-0x20000000
            head_offset = int(profile['slot_ring']['head_addr'], 0)-0x20000000
            head = struct.unpack_from('<I', ram, head_offset)[0]
            collector.add_paused_snapshot(ram[offset:offset+3072], head,
                                         final.relative_to(run).as_posix(), offset)
        except ValueError as exc:
            processing_errors.append(str(exc))
            add_event(events, session['run_id'], 'PENDING', {'reason': str(exc)}, 'raw/final-paused-ram.bin')
    selected = collector.select()
    samples, segments, mapping = make_samples(session, collector, selected, events)
    dump_strict_json({'status': 'LIMITED_NOMINAL_TIMEBASE', 'segments': segments}, analysis/'segments.json')
    observations = []
    for obs in collector.observations:
        key = (obs.boot_id, obs.source_seq)
        frame = selected.frames_by_boot.get(obs.boot_id, {}).get(obs.source_seq)
        chosen = bool(frame and hashlib.sha256(frame).hexdigest() == obs.record_sha256
                      and key in mapping and obs.validation_status == 'VALID_FORMAT')
        observations.append(dict(zip(OBSERVATIONS_HEADERS, [session['run_id'], obs.boot_id or None,
            mapping.get(key), obs.source_seq or None, obs.observation_id, obs.source_path,
            obs.byte_offset, obs.byte_length, obs.record_sha256, obs.validation_status,
            'SELECTED_VERSION' if chosen else 'RETAINED_NOT_SELECTED',
            '原始观察保留；未认证版本不混入稳定样本' if not chosen else '符合适配器选择规则'])))
    for boot in selected.boots:
        for seq in selected.conflicts_by_boot.get(boot, ()):
            add_event(events, session['run_id'], 'CONFLICT',
                      selected.conflict_details_by_boot_seq.get((boot, seq), {'paused_conflict': True}),
                      boot=boot, seq=seq)
        for seq in selected.pending_by_boot.get(boot, ()):
            add_event(events, session['run_id'], 'PENDING', {'reason': '版本未认证'}, boot=boot, seq=seq)
    states = []
    state_files = list(sorted((run/'raw').glob('state_*.bin'))) + ([final] if ram is not None else [])
    for n, file in enumerate(state_files, 1):
        rel = file.relative_to(run).as_posix()
        block = file.read_bytes()
        if len(block) != (131072 if file == final else 2048):
            processing_errors.append('状态块长度错误: '+rel)
            continue
        t = timing.get(rel, {})
        # live 字段不保证同一逻辑帧：段关联留空，即使 seq 字段读到了也不推定一致性。
        states += decode_firmware_state_snapshot(block, 0x20000000, profile['symbol_table'],
            session['run_id'], selected.boots[0] if len(selected.boots) == 1 else '', '', n,
            'HALTED_MEMORY_POINT' if file == final else 'LIVE_UNCOORDINATED', rel,
            t.get('request_ns'), t.get('confirmation_ns'))
    pending = sum(len(x) for x in selected.pending_by_boot.values())
    multi = sum(len(x) for x in selected.multi_repeat_by_boot.values())
    paused_conflicts = sum(len(x) for x in selected.paused_conflicts_by_boot.values())
    counts = {boot: validate_sequence(frames) for boot, frames in selected.frames_by_boot.items() if frames}
    missing = sum(x['missing_in_span'] for x in counts.values())
    driver = {}
    if ram is not None:
        names = ['irq_count','captured','delivered','bad_status','spi_errors','queue_overflow',
                 'queue_peak','init_errors','long_gap_count','min_irq_gap_cycles','max_irq_gap_cycles','max_read_cycles']
        driver = dict(zip(names, struct.unpack_from('<12I', ram, 0x20c)))
    source_error = any(driver.get(name, 0) for name in ['bad_status','spi_errors','queue_overflow','init_errors','long_gap_count'])
    flag_count = sum(int(row['source_flags_raw'] != 0) for row in samples if row['channel_id'] == 'ecg')
    full = receipt.get('status') in {'CAPTURE_COMPLETED','IMPORT_COMPLETED'} and bool(samples) and not (pending or missing or multi or paused_conflicts or processing_errors
        or collector.invalid_nonzero_slots or len(selected.boots) != 1 or collector.ambiguous_reset_chunks)
    integrity = 'PASS' if full else 'INCOMPLETE'
    if full and (source_error or flag_count or len(segments) > 1):
        integrity = 'LIMITED'
    quality = {'protocol_version': '1.0', 'run_id': session['run_id'],
        'identity': {'status': receipt.get('identity_status', 'UNKNOWN'), 'meaning': '采集时设备核验，非仅磁盘镜像'},
        'integrity': {'status': integrity, 'scope': '导出观察跨度内、适配器一致性规则',
                      'distinct_sample_events': len(samples)//2, 'missing_in_selected_span': missing,
                      'pending': pending, 'multi_repeat_conflicts': multi, 'paused_conflicts': paused_conflicts,
                      'conflicting_sequences': sum(len(x) for x in selected.conflicts_by_boot.values()),
                      'empty_zero_slots': collector.empty_zero_slots,
                      'invalid_nonzero_slots': collector.invalid_nonzero_slots,
                      'boot_ambiguity': bool(len(selected.boots) != 1 or collector.ambiguous_reset_chunks),
                      'flags_nonzero_samples': flag_count, 'processing_errors': processing_errors,
                      'coverage_by_boot': counts},
        'timebase': {'status': 'LIMITED_NOMINAL_TIMEBASE', 'origin': '每连续段首样本，非 UTC/复位瞬间',
                     'method': 'u32 ms 模差；DWT 只做一致性与回绕检查', 'segments': segments},
        'requested_window': {'status': 'NOT_EVALUATED_IMPORTED_PLAN' if receipt.get('mode') == 'OFFLINE_IMPORT'
                             else ('COVERED_NOMINALLY' if any(s['span_us']/1e6 >= session['plan']['warmup_s']
                                      +session['plan']['analysis_window_s'] for s in segments) else 'LIMITED_ACTUAL_SPAN'),
                             'note': '主机时长不等于设备跨度；启动延迟/分段可能使计划窗口不足'},
        'source_driver': {'status': 'ERRORS_OBSERVED' if source_error else ('NO_ERRORS_IN_SAVED_COUNTERS' if driver else 'NOT_OBSERVED'),
                          'raw_counters': driver, 'physical_adc_edges': 'NOT_INDEPENDENTLY_MEASURED'},
        'target_recovery': {'status': receipt.get('target_end_state', 'UNKNOWN')},
        'accuracy': {'status': 'NOT_EVALUATED_WITHOUT_REFERENCE', 'reason': '本版不生成生理真值或临床准出'}}
    references = []
    if session['input']['declared_kind'] == 'ACTIVE_HARDWARE_SIMULATOR':
        for key, channel, metric, unit in [('ecg_hr_setpoint_bpm','ecg','heart_rate','bpm'),
                                         ('resp_setpoint_per_min','resp','resp_rate','per_min')]:
            value = session['input'].get(key)
            if value is not None:
                require(math.isfinite(float(value)) and float(value)>0, '参考设定值无效')
                references.append(dict(zip(REFERENCE_HEADERS, [session['run_id'],'declared-setpoint',None,
                    None,None,channel,metric,value,unit,'PROGRAMMED_SETPOINT','session.json#/input/'+key])))
    if references:
        write_strict_csv(analysis/'reference.csv',REFERENCE_HEADERS,references)
        quality['accuracy'] = {'status':'NOT_EVALUATED_REFERENCE_ANALYSIS_NOT_IMPLEMENTED',
                               'reason':'仅保存用户设定声明，无独立真值或同步，不能判准确度'}
    write_strict_csv(analysis/'samples.csv', SAMPLES_HEADERS, samples)
    if samples:
        # 兼容既有离线 C 回放；仅写入本次真正进入标准样本表的完整 24 B 记录。
        accepted = {int(row['source_seq']) for row in samples}
        boot = selected.boots[0]
        (analysis/'stable_frames.bin').write_bytes(b''.join(blob for seq,blob in
            selected.frames_by_boot[boot].items() if seq in accepted))
    write_strict_csv(analysis/'observations.csv', OBSERVATIONS_HEADERS, observations)
    write_strict_csv(analysis/'firmware_state.csv', FIRMWARE_STATE_HEADERS, states)
    write_events_jsonl(events, analysis/'events.jsonl')
    dump_strict_json(quality, analysis/'quality.json')
    dump_strict_json({'analysis_id': analysis.name, 'tool_version': VERSION,
                     'tool_files_sha256': tool_identity(),
                     'input_raw_manifest_sha256': raw_check['manifest_sha256'], 'exit_code': 0 if full else 2,
                     'hardware_operations': [], 'warmup_policy': '表征分析对每个连续段独立排除预热'},
                    analysis/'analysis_receipt.json')
    summarize(samples, session, analysis, quality)
    files = [{'path': p.relative_to(analysis).as_posix(), 'size_bytes': p.stat().st_size,
              'sha256': sha256_file(p)} for p in sorted(analysis.rglob('*')) if p.is_file()]
    dump_strict_json({'protocol_version': '1.0', 'self_excluded': True, 'files': files}, analysis/'manifest.json')
    update_index(run, analysis.name, quality['identity']['status'], integrity, '准确度未评估；详见逐项质量')
    return analysis, quality


def summarize(rows, session, analysis, quality):
    warmup_us = int(session['plan']['warmup_s'] or 0)*1000000
    summary = {}
    for channel in ['resp', 'ecg']:
        usable = [r for r in rows if r['channel_id'] == channel and int(r['device_time_us']) >= warmup_us]
        values = [int(r['raw_code']) for r in usable]
        summary[channel] = {'samples_after_per_segment_warmup': len(values), 'unit': 'adc_code',
                            'min': min(values) if values else None, 'max': max(values) if values else None,
                            'mean': statistics.fmean(values) if values else None,
                            'std_population': statistics.pstdev(values) if values else None,
                            'exact_rail_samples': sum(v in (-8388608, 8388607) for v in values)}
    dump_strict_json({'warmup_s_each_segment': warmup_us/1000000, 'channels': summary,
                     'heart_resp_rate_accuracy': 'NOT_EVALUATED'}, analysis/'summary.json')
    # SVG 每个时间段单独画；桶内保留极值，不插值、不把采集缺口连成实测曲线。
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="550" viewBox="0 0 1100 550">',
           '<rect width="1100" height="550" fill="white"/>']
    for n, channel in enumerate(['resp', 'ecg']):
        channel_rows = [r for r in rows if r['channel_id'] == channel]
        if not channel_rows:
            continue
        ymin = min(int(r['raw_code']) for r in channel_rows)
        ymax = max(int(r['raw_code']) for r in channel_rows)
        top = 35+n*260
        svg.append(f'<text x="20" y="{top}" font-family="sans-serif">{channel} raw ADC codes [{ymin}, {ymax}]</text>')
        groups = {}
        for row in channel_rows:
            groups.setdefault((row['boot_id'], row['segment_id']), []).append(row)
        for group in groups.values():
            span = max(int(r['device_time_us']) for r in group) or 1
            points = []
            stride = max(1, math.ceil(len(group)/500))
            for i in range(0, len(group), stride):
                bucket = group[i:i+stride]
                indices = sorted({0, len(bucket)-1, min(range(len(bucket)), key=lambda j: int(bucket[j]['raw_code'])),
                                  max(range(len(bucket)), key=lambda j: int(bucket[j]['raw_code']))})
                for j in indices:
                    r = bucket[j]
                    x = 80+int(r['device_time_us'])/span*980
                    y = top+20+190*(ymax-int(r['raw_code']))/max(1, ymax-ymin)
                    points.append(f'{x:.2f},{y:.2f}')
            svg.append('<polyline fill="none" stroke="#2463a5" stroke-width="0.8" points="'+' '.join(points)+'"/>')
        svg.append(f'<text x="80" y="{top+235}" font-family="sans-serif">Each segment uses its own relative time axis; full raw CSV retained.</text>')
    svg.append('</svg>')
    (analysis/'waveforms.svg').write_text('\n'.join(svg), encoding='utf-8')
    (analysis/'report.md').write_text(
        '# 标准采集离线报告\n\n'
        f'轮次：`{session["run_id"]}`。导出完整性：`{quality["integrity"]["status"]}`。\n\n'
        f'稳定样本事件：{len(rows)//2}；冲突、pending、错误及设备计数见 quality.json。\n\n'
        '波形为原始 ADC 码；多段图可能重叠，逐段时轴不是统一 UTC。详见 samples.csv 的段标识。\n\n'
        '![原始波形](waveforms.svg)\n\n'
        '本版输出原始表征，不计算未经参考确认的心率/呼吸准确度。实机状态不保证逻辑帧原子性。\n', encoding='utf-8')


def validate_run(run):
    run = Path(run).resolve()
    raw = verify_package(run, raw=True)
    check_configuration(run)
    analyses = []
    for folder in sorted((run/'derived').iterdir()):
        if not folder.is_dir():
            continue
        derived = verify_package(folder, 'manifest.json')
        receipt = load_strict_json(folder/'analysis_receipt.json')
        require(receipt['input_raw_manifest_sha256'] == raw['manifest_sha256'], '分析未绑定本轮原件清单')
        with (folder/'samples.csv').open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream)
            require(reader.fieldnames == SAMPLES_HEADERS, '样本表头不符')
            seen, pairs = set(), {}
            for row in reader:
                require(row['run_id'] == run.name, '样本串轮次')
                key = (row['boot_id'], row['segment_id'], row['source_seq'], row['channel_id'])
                require(key not in seen, '重复样本主键')
                seen.add(key)
                require(-8388608 <= int(row['raw_code']) <= 8388607, 'signed 24-bit 范围错误')
                require(row['integrity'] in {'CONSISTENT_RECONSTRUCTION', 'PUBLISHED_SNAPSHOT'}, '混入未认证样本')
                source = row['source_ref'].split('@')[0]
                require(source and within(run, source).is_file(), '样本原始来源缺失')
                pairs.setdefault(key[:3], set()).add(row['channel_id'])
            require(all(chs == {'resp','ecg'} for chs in pairs.values()), '双通道覆盖不完整')
        analyses.append({'analysis_id': folder.name, 'files': derived['checked_files'],
                         'sample_events': len(pairs), 'quality': load_strict_json(folder/'quality.json')['integrity']['status']})
    return {'status': 'PASS_FILE_VALIDATION', 'not_hardware_or_accuracy_acceptance': True,
            'raw_files': raw['checked_files'], 'analyses': analyses}


def compare_dataset(dataset, output, purpose='integrity'):
    dataset, output = Path(dataset).resolve(), Path(output).resolve()
    require(not output.exists(), '对比输出目录已存在，禁止覆盖')
    with (dataset/'dataset_index.csv').open(encoding='utf-8', newline='') as stream:
        entries = list(csv.DictReader(stream))
    rows, groups = [], {}
    for entry in entries:
        run = within(dataset, entry['run_path'])
        try:
            verify_package(run, raw=True)
            session, channels, profile = check_configuration(run)
            analysis = within(run, 'derived/'+entry['analysis_id'])
            require(bool(entry['analysis_id']), '没有分析产物')
            verify_package(analysis, 'manifest.json')
            receipt = load_strict_json(analysis/'analysis_receipt.json')
            require(receipt['input_raw_manifest_sha256'] == sha256_file(run/'raw_manifest.json'), '分析输入身份不符')
            require(bool(receipt.get('tool_files_sha256')), '旧分析缺少准确分析代码身份，不进入正式比较')
            q = load_strict_json(analysis/'quality.json')
            summary = load_strict_json(analysis/'summary.json')
            status = 'OBSERVATIONAL'
            if q['integrity']['status'] != 'PASS' or q['identity']['status'] != 'VERIFIED':
                status = 'EXCLUDED'
            # 精确条件分组，不因同名 condition_id 就合并不同增益、输入或速率。
            relevant = {'condition_id': session['condition_id'], 'input': session['input'],
                        'channels': channels['channels'], 'adapter': profile['adapter_id'],
                        'timebase': session['timebase'], 'warmup': session['plan']['warmup_s'],
                        'analysis_window': session['plan']['analysis_window_s'],
                        'analysis_code': receipt.get('tool_files_sha256'),
                        'analysis_version': receipt['tool_version']}
            if purpose == 'waveform' and (session['input'].get('verified_kind') == 'UNKNOWN'
                or any(c.get('gain') is None for c in channels['channels'])):
                status = 'EXCLUDED'
            # 仅对相关内容做规范化比较；原 JSON 排版和键顺序不影响分组。
            key = json.dumps(relevant, sort_keys=True, ensure_ascii=False, allow_nan=False)
            group = groups.setdefault(key, {'group_id': f'group_{len(groups)+1:03d}', 'runs': [], 'raw_std': []})
            row = {'run_id': run.name, 'group_id': group['group_id'], 'status': status,
                   'integrity': q['integrity']['status'], 'sample_events': q['integrity']['distinct_sample_events'],
                   'ecg_raw_std': summary['channels']['ecg']['std_population'],
                   'resp_raw_std': summary['channels']['resp']['std_population'],
                   'accuracy': 'NOT_EVALUATED', 'reason': '本版限定表征，未知参考不输出准确度'}
            if status != 'EXCLUDED':
                group['runs'].append(run.name)
                if row['ecg_raw_std'] is not None:
                    group['raw_std'].append(row['ecg_raw_std'])
        except (ValueError, OSError, KeyError) as exc:
            row = {'run_id': entry['run_id'], 'group_id': '', 'status': 'EXCLUDED', 'integrity': 'UNKNOWN',
                   'sample_events': None, 'ecg_raw_std': None, 'resp_raw_std': None,
                   'accuracy': 'NOT_EVALUATED', 'reason': str(exc)}
        rows.append(row)
    output.mkdir(parents=True, exist_ok=False)
    headers = ['run_id','group_id','status','integrity','sample_events','ecg_raw_std','resp_raw_std','accuracy','reason']
    write_strict_csv(output/'comparison.csv', headers, rows)
    result = []
    for group in groups.values():
        values = group.pop('raw_std')
        group.update(included_runs=len(group['runs']), ecg_raw_std_median=statistics.median(values) if values else None)
        result.append(group)
    dump_strict_json({'purpose': purpose, 'groups': result, 'failed_runs_retained': True,
                     'overall_accuracy': 'NOT_EVALUATED'}, output/'comparison.json')
    return output
