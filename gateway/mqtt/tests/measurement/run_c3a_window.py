"""执行明确批准的两轮C3A窗口；固定产物、次数、私有原片及finally恢复。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import threading
import time

from c3a_jlink import CaptureLink
from r2_snapshot_bytes import InvalidSnapshot, load_layout, verify_pair


ROOT = Path(__file__).resolve().parents[4]
JLINK = 'E:/stm32/j_link/JLink_V512/JLink.exe'
FLASH_SHA = '852d7618f8fc46c80cbe035ebd41f4e21e4d5a76a26cf10a39e0600f7a89ffb8'
BRIDGE_SHA = '523bf9c2dd4d59c0f6c564d9f16c0cc51a9160c47b8a7be31f7ddad4832df8ff'
BIN_SHA = {'P4': 'fabd82b305e2fe1bc4bbc0d06bdde91d05daabd7f91c70ca017f48e4617ab551',
           'P5': '47a444ebd3642dffef80364309d0b100cc048b456d75dde0b2806a7f9a052efc'}
LIMITS = {'app_installs': 4, 'config_writes': 2, 'reset_commands': 10,
          'measurement_D': 2, 'cleanup_D': 2, 'measurement_halts': 2, 'full_restore': 1}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-task', required=True, type=Path)
    parser.add_argument('--private-baseline', required=True, type=Path)
    parser.add_argument('--external-helper-dir', required=True, type=Path)
    parser.add_argument('--execute-authorized-window', action='store_true')
    args = parser.parse_args()
    if not args.execute_authorized_window:
        raise SystemExit('C3A_WINDOW_AUTH_REQUIRED')
    task, baseline = args.private_task, args.private_baseline
    precheck = json.loads((task / 'precheck.json').read_text(encoding='utf-8'))
    backup = task / 'before-1MiB.bin'
    if (not precheck['user_window_authorized'] or not precheck['fresh_double_backup_match'] or
            sha(backup.read_bytes()) != FLASH_SHA or
            backup.read_bytes() != (task / 'before-second-1MiB.bin').read_bytes()):
        raise SystemExit('FRESH_BACKUP_NOT_VERIFIED')
    bridge = ROOT / 'gateway/esp_at_probe/build/esp_diagnostic_bridge.bin'
    build = ROOT / 'gateway/mqtt/build/h16-diagnostic/run-20261008T105757767802Z'
    images = {v: build / v.lower() / 'gateway_mqtt.bin' for v in BIN_SHA}
    if sha(bridge.read_bytes()) != BRIDGE_SHA or any(sha(p.read_bytes()) != BIN_SHA[v] for v, p in images.items()):
        raise SystemExit('MEASUREMENT_IMAGE_IDENTITY')
    cfg, uid = baseline / 'gateway-config.bin', baseline / 'uid-guard.bin'
    if cfg.stat().st_size != 312 or uid.stat().st_size != 12:
        raise SystemExit('PRIVATE_INPUT_SIZE')
    layout = load_layout(ROOT / 'doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/evidence/c25-r2/probe-layout-v2.json')
    # 同一授权窗口只启动一次；异常恢复后不能靠重跑脚本绕过累计操作上限。
    with (task / 'execution-started.json').open('x', encoding='utf-8') as marker:
        json.dump({'authorized': True, 'planned_runs': 2}, marker)
    (task / 'executed-run_c3a_window.py').write_bytes(Path(__file__).read_bytes())
    (task / 'executed-c3a_jlink.py').write_bytes(Path(__file__).with_name('c3a_jlink.py').read_bytes())
    # 连接信息仅由外部旧索引选择并在内存注入，不复制配置值或读取SSH私钥。
    index = json.loads((baseline / 'external-source-index.json').read_text(encoding='utf-8'))
    selection = json.loads((baseline / 'credential-selection.json').read_text(encoding='utf-8'))
    reader = json.loads(Path(index[selection['reader']]['path']).read_text(encoding='utf-8-sig'))
    sys.path.insert(0, str(ROOT / 'cloud/backend'))
    sys.path.insert(0, str(args.external_helper_dir))
    from app.mqtt_adapter import configured_client
    from app.adapters import decode_mqtt
    from web_observer_runtime import BackendObserver
    import serial

    origin = time.perf_counter_ns()
    legacy_observer_origin = time.monotonic()
    now = lambda: (time.perf_counter_ns() - origin) // 1000
    report = {'kind': 'C3A_TWO_RUN_PILOT', 'user_authorized': True, 'limits': LIMITS,
              'counts': {name: 0 for name in LIMITS}, 'temporary_write_attempted': False,
              'original_flash_restored': False, 'physical_nodes': False, 'real_patient_data': False,
              'security_gate': 'NOT_AUTHORIZED', 'broker_fault_operations': False,
              'clock_domain': 'HOST_QPC_US', 'runs': [], 'stage': 'PREPARED',
              'runner_sha256': sha(Path(__file__).read_bytes()),
              'capture_helper_sha256': sha(Path(__file__).with_name('c3a_jlink.py').read_bytes())}
    samples, lines, events = [], [], []
    mutex, subscribed = threading.Lock(), threading.Event()
    uart = client = capture = None
    esp_before = None
    current_diag = False
    pending = bytearray()
    backend = BackendObserver()

    def save(path, value, exclusive=False):
        with path.open('x' if exclusive else 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())

    def journal(stage):
        report['stage'] = stage
        save(task / 'window-journal.json', report)
        print('C3A_STAGE ' + stage, flush=True)

    def count(name, amount=1):
        if report['counts'][name] + amount > LIMITS[name]:
            raise RuntimeError('WINDOW_OPERATION_LIMIT')
        report['counts'][name] += amount

    def jlink(name, body):
        count('reset_commands', body.splitlines().count('r'))
        script = task / (name + '.jlink')
        script.write_text('exitonerror 1\nconnect\n' + body + '\nq\n', encoding='ascii')
        result = subprocess.run([JLINK, '-device', 'STM32F407ZG', '-if', 'SWD', '-speed', '4000',
                                 '-CommanderScript', str(script)], capture_output=True, timeout=100,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        text = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        (task / (name + '-private.log')).write_text(text, encoding='utf-8')
        if result.returncode or re.search(r'^\s*ERROR|Cannot connect|Unknown command|Verification failed|Failed to', text, re.I | re.M):
            raise RuntimeError('FIXED_JLINK_STEP_FAILED')

    def install(binary, name, config=None):
        count('app_installs')
        if config:
            count('config_writes')
        report['temporary_write_attempted'] = True
        journal('INSTALL_' + name)
        output = task / (name + '-app-readback.bin')
        body = f'r\nh\nverifybin {uid.as_posix()}, 0x1FFF7A10\nloadbin {binary.as_posix()}, 0x08000000\n'
        body += f'verifybin {binary.as_posix()}, 0x08000000\nsavebin {output.as_posix()}, 0x08000000, 0x{binary.stat().st_size:X}\n'
        if config:
            cfg_out = task / (name + '-config-readback.bin')
            body += f'loadbin {config.as_posix()}, 0x080E0000\nverifybin {config.as_posix()}, 0x080E0000\n'
            body += f'savebin {cfg_out.as_posix()}, 0x080E0000, 0x138\n'
        jlink('install-' + name, body)
        if output.read_bytes() != binary.read_bytes() or (config and cfg_out.read_bytes() != config.read_bytes()):
            raise RuntimeError('APPLICATION_OR_CONFIG_READBACK')

    def start(binary, name):
        sp, pc = struct.unpack('<II', binary.read_bytes()[:8])
        if not 0x20000000 < sp <= 0x20020000 or not 0x08000000 <= pc & ~1 < 0x080E0000:
            raise RuntimeError('IMAGE_VECTOR_BOUNDARY')
        body = f'r\nh\nverifybin {uid.as_posix()}, 0x1FFF7A10\nw4 0xE000ED08, 0x08000000\n'
        body += f'wreg MSP, 0x{sp:08X}\nwreg CONTROL, 0\nwreg PRIMASK, 0\nwreg BASEPRI, 0\nwreg FAULTMASK, 0\nSetPC 0x{pc:08X}\ng'
        jlink('start-' + name, body)

    def at(command, timeout=5):
        uart.reset_input_buffer()
        uart.write((command + '\r\n').encode('ascii'))
        uart.flush()
        deadline = time.perf_counter() + timeout
        reply = bytearray()
        while time.perf_counter() < deadline:
            reply.extend(uart.read(512))
            if b'\r\nOK\r\n' in reply:
                return bytes(reply)
            if b'\r\nERROR\r\n' in reply or len(reply) > 4096:
                break
        raise RuntimeError('FIXED_AT_OPERATION')

    def establish_at():
        try:
            return at('AT')
        except RuntimeError:
            uart.write(b'\r\n\r\n')
            uart.flush()
            time.sleep(.25)
            return at('AT')

    def on_connect(c, u, flags, reason, properties):
        if not reason.is_failure:
            c.subscribe('mpm/v1/GW-C-001/#', 1)

    def on_message(c, u, message):
        if message.retain:
            return
        try:
            value = decode_mqtt(message.topic, message.payload)
            if not value.synthetic or not value.session_id.startswith('can-'):
                return
            row = {'at_us': now(), 'node': value.node_id, 'stream': value.stream,
                   'session_id': value.session_id, 'timestamp': value.timestamp, 'seq': value.seq,
                   'validity': value.validity, 'source': value.source, 'synthetic': True}
            if value.stream in ('GATEWAY_STATUS', 'SPO2', 'TEMP', 'RR'):
                row['value'] = value.value
            with mutex:
                samples.append(row)
        except Exception:
            report['decode_failure_count'] = report.get('decode_failure_count', 0) + 1

    def pump():
        nonlocal pending
        pending.extend(uart.read(max(1, min(1024, uart.in_waiting))))
        chunks = pending.split(b'\n')
        pending = bytearray(chunks.pop())
        if len(pending) > 4096:
            pending.clear()
            report['serial_overlong_lines'] = report.get('serial_overlong_lines', 0) + 1
        for chunk in chunks:
            text = chunk.decode('ascii', errors='ignore').strip()
            if re.fullmatch(r'GW (?:BOOT [A-Z0-9_ ]+|OK [A-Z0-9_]+|FAIL [A-Z0-9_]+|MQTT_CONNECTED|'
                            r'WIFI_TEST_DISCONNECTED|CONFIG_REQUIRED|ASSERT_FATAL|CONNECT_PACKET_SENT|'
                            r'CONNACK_CODE [0-9]+|RECONNECT|CAN_INIT_FAIL code=-?[0-9]+ hardware=[0-9]+|'
                            r'METRICS [a-z0-9= ]+|WRITE_[A-Z_]+|READ_[A-Z_]+)', text):
                lines.append({'at_us': now(), 'message': text})
                if text in ('GW ASSERT_FATAL', 'GW CONFIG_REQUIRED') or text.startswith('GW CAN_INIT_FAIL'):
                    raise RuntimeError('FIRMWARE_RUNTIME_STOP')

    def wait_for(predicate, seconds):
        end = time.perf_counter() + seconds
        while time.perf_counter() < end:
            pump()
            if predicate():
                return
        raise TimeoutError('WINDOW_OBSERVATION_DEADLINE')

    def frame_ready(since):
        with mutex:
            return all(any(r['at_us'] > since and r['node'] == node and r['stream'] == stream and r['validity'] == 'VALID'
                           for r in samples) for node, stream in (('NODE-A', 'SPO2'), ('NODE-B', 'ECG')))

    def observe_until(end_us):
        while now() < end_us:
            pump()

    def cleanup_D():
        count('cleanup_D')
        old = len(lines)
        uart.write(b'D')
        uart.flush()
        try:
            wait_for(lambda: any(r['message'] == 'GW WIFI_TEST_DISCONNECTED' for r in lines[old:]), 20)
            return True
        except TimeoutError:
            return False

    def raw_numbers(data, variant):
        types = layout['variants'][variant]['types']
        fields = types['ProbeState']['fields']
        get = lambda field, width=4: int.from_bytes(data[fields[field]:fields[field] + width], 'little')
        if len(data) != 1264 or get('magic') != 0xC25D1A60 or get('variant') != int(variant[-1]):
            raise RuntimeError('RAW_IDENTITY_MISMATCH')
        values = {key: get(key) for key in ('profile', 'core_hz', 'clock_seq', 'irq_flags', 'foreground_flags',
                  'depth', 'window_generation', 'recovery_generation', 'dropped_observations', 'unmatched_ticks',
                  'tick_dropped', 'tick_drop_base', 'tick_head', 'tick_tail', 'network_valid_mask', 'cache_snapshot_mask',
                  'heap_peak_bytes', 'heap_enomem_count', 'heap_error_base', 'cache_drained_observed')}
        values['network_us'] = [int.from_bytes(data[fields['network_us'] + i * 8:fields['network_us'] + i * 8 + 8], 'little') for i in range(9)]
        values['aggregate'] = []
        for scope in range(10):
            base = fields['aggregate'] + scope * types['ProbeAggregate']['size']
            sub = types['ProbeAggregate']['fields']
            values['aggregate'].append({k: int.from_bytes(data[base + sub[k]:base + sub[k] + (8 if k.endswith('cycles') and k in ('inclusive_cycles', 'direct_child_cycles') else 4)], 'little')
                                       for k in ('success', 'failure', 'invalid', 'min_cycles', 'max_cycles', 'inclusive_cycles', 'direct_child_cycles')})
        for name in ('cache_before', 'cache_after'):
            base = fields[name]
            values[name] = {k: int.from_bytes(data[base + offset:base + offset + 4], 'little') for k, offset in types['ProbeCache']['fields'].items()}
        values['first_live_us'] = get('first_live_us', 8)
        values['first_replay_us'] = get('first_replay_us', 8)
        values['quality'] = 'RAW_NUMERIC_INSPECTION_NOT_ACCEPTANCE'
        return values

    try:
        journal('READ_ONLY_OBSERVERS')
        backend.start(reader['host'])
        if not backend.ready.wait(20):
            raise RuntimeError('BACKEND_OBSERVER_UNAVAILABLE')
        client = configured_client(reader, 'p5-c3a-two-run-observer')
        client.on_connect, client.on_message = on_connect, on_message
        client.on_subscribe = lambda *a: subscribed.set()
        client.connect_async(reader['host'], 8883, 15)
        client.loop_start()
        if not subscribed.wait(20):
            raise RuntimeError('TLS_OBSERVER_UNAVAILABLE')
        uart = serial.Serial(port=None, baudrate=115200, timeout=.02)
        uart.dtr = uart.rts = False
        uart.port = 'COM15'
        uart.open()
        install(bridge, 'bridge-before')
        uart.reset_input_buffer()
        start(bridge, 'bridge-before')
        time.sleep(.3)
        first = establish_at()
        mode, store = at('AT+CWMODE?'), at('AT+SYSSTORE?')
        esp_before = {'mode': int(re.search(rb'\+CWMODE:(\d)', mode)[1]),
                      'sysstore': int(re.search(rb'\+SYSSTORE:(\d)', store)[1]),
                      'echo': first.lstrip().startswith(b'AT'), 'gmr_sha256': sha(at('AT+GMR'))}
        report['esp_before'] = esp_before
        for variant in ('P4', 'P5'):
            current_diag = False
            install(images[variant], variant.lower(), cfg)
            uart.reset_input_buffer()
            pending.clear()
            startup = now()
            start(images[variant], variant.lower())
            current_diag = True
            journal(variant + '_WARMUP')
            wait_for(lambda: frame_ready(startup), 120)
            capture = CaptureLink(uid.read_bytes(), window_authorized=True)
            sample = {'variant': variant, 'bin_sha256': BIN_SHA[variant], 'events': {}, 'clock_domain': 'HOST_QPC_US'}
            sample['dwt_control_before'] = capture.read32(0xE0001000)
            a_time = now()
            a_cycle = capture.read32(0xE0001004)
            observe_until(a_time + 500000)
            b_time = now()
            b_cycle = capture.read32(0xE0001004)
            sample['cycle_calibration_hz'] = ((b_cycle - a_cycle) & 0xffffffff) * 1_000_000 / (b_time - a_time)
            sample['calibration_reference'] = {'at_us': b_time, 'cycle': b_cycle}
            count('measurement_D')
            d = now()
            sample['events']['D_SENT'] = d
            uart.write(b'D')
            uart.flush()
            journal(variant + '_D_90S_OBSERVATION')
            observe_until(d + 90_000_000)
            count('measurement_halts')
            halt_sent = now()
            halted = False
            one, two = task / (variant + '-snapshot-read1.bin'), task / (variant + '-snapshot-read2.bin')
            try:
                capture.halt()
                halted = True
                sample['events']['HALT'] = now()
                sample['registers_at_halt'] = capture.registers_at_halt()
                sample['dwt_cycle_at_halt'] = capture.read32(0xE0001004)
                address = layout['variants'][variant]['probe_state_address']
                first = capture.snapshot(address)
                with one.open('xb') as stream:
                    stream.write(first); stream.flush(); os.fsync(stream.fileno())
                sample['events']['READ1_DONE'] = now()
                second = capture.snapshot(address)
                with two.open('xb') as stream:
                    stream.write(second); stream.flush(); os.fsync(stream.fileno())
                sample['events']['READ2_DONE'] = now()
                sample['snapshot_sha256'] = sha(first)
                sample['snapshot_double_read_match'] = first == second
                save(task / (variant + '-capture-during-halt.json'), sample, exclusive=True)
                sample['events']['SNAPSHOT_PERSISTED'] = now()
            finally:
                # 冻结后任何解码/保存错误也优先resume；不尝试第二次halt救回样本。
                if halted or capture.link.halted():
                    capture.resume()
                sample['events']['RESUME'] = now()
                sample['halt_total_us'] = sample['events']['RESUME'] - halt_sent
            capture.close()
            capture = None
            if not sample['snapshot_double_read_match']:
                raise RuntimeError('RAW_SNAPSHOT_DOUBLE_READ_MISMATCH')
            sample['raw_numeric'] = raw_numbers(one.read_bytes(), variant)
            try:
                sample['strict_decode'] = verify_pair(one, two, layout, variant)
                sample['strict_decode_status'] = 'PASS_OFFLINE_BYTES_ONLY'
            except InvalidSnapshot as error:
                sample['strict_decode_status'] = str(error)
            sample['halt_context_valid'] = sample['registers_at_halt']['IPSR'] == 0 and sample['raw_numeric']['depth'] == 0
            sample['pause_budget_valid'] = sample['halt_total_us'] <= 2_000_000
            sample['window_duration_us'] = sample['events']['HALT'] - d
            span = sample['events']['HALT'] - b_time
            delta = (sample['dwt_cycle_at_halt'] - b_cycle) & 0xffffffff
            sample['full_window_cycle_hz'] = delta * 1_000_000 / span
            sample['cycle_clock_consistent'] = all(15_680_000 <= sample[k] <= 16_320_000 for k in ('cycle_calibration_hz', 'full_window_cycle_hz'))
            journal(variant + '_POST_RESUME_30S_OBSERVATION')
            observe_until(sample['events']['RESUME'] + 30_000_000)
            with mutex:
                related = [dict(row) for row in samples if row['at_us'] >= d]
            sample['broker_fixed_metadata'] = related
            sample['post_halt_offline_observed'] = any(r['at_us'] >= sample['events']['HALT'] and r['stream'] == 'GATEWAY_STATUS' and r.get('value') == 'OFFLINE' for r in related)
            sample['last_metrics'] = next((row for row in reversed(lines) if row['message'].startswith('GW METRICS')), None)
            report['runs'].append(sample)
            save(task / (variant + '-measurement.json'), sample, exclusive=True)
            journal(variant + '_RAW_CAPTURE_SAVED')
            if sample['post_halt_offline_observed']:
                raise RuntimeError('OBSERVATION_INDUCED_DISCONNECT')
            if variant == 'P4':
                report['p4_quiesced_for_swap'] = cleanup_D()
                if not report['p4_quiesced_for_swap']:
                    raise RuntimeError('P4_SWAP_QUIESCE_FAILED')
        report['pilot_capture_complete'] = True
    except BaseException as error:
        report['failure_category'] = type(error).__name__
        report['failure_stage'] = report['stage']
        print('C3A_STOP ' + report['failure_category'], flush=True)
    finally:
        if capture:
            try:
                if capture.link.halted():
                    capture.resume()
                capture.close()
            except BaseException:
                report['capture_close_issue'] = True
        try:
            report['backend_observer'] = backend.stop(task / 'backend-fixed-metadata.json', legacy_observer_origin)
        except BaseException:
            report['backend_stop_issue'] = True
        if client:
            try:
                client.disconnect(); client.loop_stop()
            except BaseException:
                report['reader_stop_issue'] = True
        if report['temporary_write_attempted']:
            try:
                if current_diag and uart:
                    report['final_quiesced'] = cleanup_D()
                if esp_before and uart:
                    install(bridge, 'bridge-restore')
                    uart.reset_input_buffer(); start(bridge, 'bridge-restore'); time.sleep(.3)
                    establish_at(); at('AT+SYSSTORE=0')
                    for close in ('AT+CIPCLOSE', 'AT+CWQAP'):
                        try: at(close)
                        except RuntimeError: pass
                    at('AT+CWMODE=' + str(esp_before['mode']))
                    at('ATE' + str(int(esp_before['echo'])))
                    at('AT+SYSSTORE=' + str(esp_before['sysstore']))
                    mode, store = at('AT+CWMODE?'), at('AT+SYSSTORE?')
                    report['esp_mode_store_restored'] = (int(re.search(rb'\+CWMODE:(\d)', mode)[1]) == esp_before['mode'] and int(re.search(rb'\+SYSSTORE:(\d)', store)[1]) == esp_before['sysstore'])
            except BaseException as error:
                report['esp_restore_failure_category'] = type(error).__name__
            try:
                journal('RESTORE_ORIGINAL_FULL_1MIB')
                count('full_restore')
                restored = task / 'restored-1MiB-readback.bin'
                body = f'r\nh\nverifybin {uid.as_posix()}, 0x1FFF7A10\nloadbin {backup.as_posix()}, 0x08000000\n'
                body += f'verifybin {backup.as_posix()}, 0x08000000\nsavebin {restored.as_posix()}, 0x08000000, 0x100000\nr\ng'
                jlink('restore-original', body)
                if restored.read_bytes() != backup.read_bytes():
                    raise RuntimeError('FULL_FLASH_RESTORE_READBACK')
                report['original_flash_restored'] = True
                report['restored_flash_sha256'] = sha(restored.read_bytes())
                if uart:
                    uart.reset_input_buffer()
                    passive, end = bytearray(), time.perf_counter() + 5
                    while time.perf_counter() < end and b'DMA_ADC' not in passive:
                        passive.extend(uart.read(512))
                        del passive[:-4096]
                    report['original_dma_adc_observed'] = b'DMA_ADC' in passive
            except BaseException as error:
                report['flash_restore_failure_category'] = type(error).__name__
                print('C3A_RESTORE_NOT_CONFIRMED', flush=True)
        if uart:
            uart.close()
        save(task / 'serial-fixed-diagnostics.json', lines, exclusive=True)
        save(task / 'broker-fixed-metadata.json', samples, exclusive=True)
        report['finished_at_us'] = now()
        journal('FINISHED' if report['original_flash_restored'] else 'NO_VERIFIED_RESTORE')
        print(json.dumps({'runs_captured': len(report['runs']), 'counts': report['counts'],
                          'full_flash_restored': report['original_flash_restored'],
                          'dma_adc_observed': report.get('original_dma_adc_observed', False),
                          'failure_category': report.get('failure_category'), 'H16_acceptance': 'NOT_GRANTED'}), flush=True)
    return 0 if report.get('pilot_capture_complete') and report['original_flash_restored'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
