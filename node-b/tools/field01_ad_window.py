"""FIELD01 点对点短窗；AD60或DE血压完成/失效检查，不录音、启泵或下载。"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import zlib

import serial
from b4_recovery import protected


class ManualNIBPWindow:
    """人工启动、测量完成和到期观察分别计时，始终预留全局停止预算。"""
    def __init__(self, armed, ready):
        self.stop_deadline = armed + 395
        self.start_deadline = min(ready + 150, self.stop_deadline - 120 - 95)
        if self.start_deadline - ready < 60:
            raise TimeoutError('FIELD01_INSUFFICIENT_HARD_BUDGET_BEFORE_MANUAL_PROMPT')
        self.measurement_start = None
        self.completion_deadline = None
        self.result_seen = None
        self.end = self.stop_deadline

    def observed_start(self, now):
        if self.measurement_start is None:
            self.measurement_start = now
            self.completion_deadline = min(now + 120, self.stop_deadline - 95)

    def observed_result(self, now):
        if now + 95 > self.stop_deadline:
            raise TimeoutError('FIELD01_INSUFFICIENT_BUDGET_FOR_90S_EXPIRY_OBSERVATION')
        self.result_seen = now
        self.end = now + 95

    def check(self, now):
        if self.result_seen is not None:
            return
        if self.measurement_start is None and now >= self.start_deadline:
            raise TimeoutError('FIELD01_NO_E_MANUAL_START_WITHIN_OPERATOR_BUDGET')
        if self.measurement_start is not None and now >= self.completion_deadline:
            raise TimeoutError('FIELD01_NO_E_COMPLETION_WITHIN_120S_AFTER_START_OBSERVED')


class FiveDiagnosticWindow:
    def __init__(self, armed, common):
        self.common = common
        self.evaluation_start = common + 45
        self.end = self.evaluation_start + 300
        if self.end > armed + 395:
            raise TimeoutError('FIELD01_FIVE_420S_BUDGET_INSUFFICIENT')


def latest_snapshot(path):
    with path.open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 65536))
        raw = stream.read()
    rows = raw.splitlines()
    if not raw.endswith(b'\n'):
        rows = rows[:-1]
    return json.loads(rows[-1])['snapshot'] if rows else None


def five_nodes_online(snapshot):
    return bool(snapshot and snapshot['gateway_id'] == 'GW-B5-001' and snapshot['node_profile'] == 'five' and snapshot['gateway_state'] == 'ONLINE'
                and all(snapshot['nodes'].get(n) == 'ONLINE' for n in ('NODE-A', 'NODE-B', 'NODE-D', 'NODE-E')))


def check_five_diagnostic(text, require_operational=False):
    if text.startswith('FIVE STATE '):
        fields = dict((k, int(v)) for k, v in (p.split('=') for p in text[11:].split()))
        if fields['wrong_bus'] or fields['malformed'] or fields['resets']:
            raise ValueError('FIELD01_FIVE_WRONG_BUS_MALFORMED_OR_STACK_RESET')
        return 'STATE', fields
    if text.startswith('FIVE RX '):
        fields = dict((k, int(v)) for k, v in (p.split('=') for p in text[8:].split()))
        if fields['emcy'] or fields['code']:
            raise ValueError('FIELD01_FIVE_SOURCE_EMCY')
        if fields['node'] not in (1, 2, 4, 5) or fields['bus'] != (0 if fields['node'] in (1, 5) else 1):
            raise ValueError('FIELD01_FIVE_NODE_BUS_IDENTITY')
        if require_operational and (fields['nmt'] != 5 or fields['hb_age'] > 1500):
            raise ValueError('FIELD01_FIVE_NODE_NOT_OPERATIONAL_OR_HEARTBEAT_LOST')
        return 'RX', fields


def read_completed_nibp(wire, t0_utc_ms):
    os.environ['MPM_NODE_PROFILE'] = 'five'
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'cloud/backend'))
    from app.adapters import decode_mqtt
    while True:
        position = wire.tell()
        line = wire.readline()
        if not line.endswith('\n'):
            wire.seek(position)
            return None
        row = json.loads(line)
        if row['retain'] or row['topic'] != 'mpm/v1/GW-B5-001/NODE-E/telemetry/nibp':
            continue
        message = decode_mqtt(row['topic'], bytes.fromhex(row['payload_hex'])).model_dump()
        if message['validity'] == 'VALID' and message['source'] == 'MOCK' and message['timestamp'] >= t0_utc_ms:
            return dict(message=message, broker_arrival_utc_ms=row['arrival_unix_ns'] // 1000000)


def run(job, source_observer=None, mode='AD60', channel_profile=None):
    protected(job, False)
    out = job / 'C-observation'
    out.mkdir()
    protected(out, False)
    (out / 'executed-controller.py').write_bytes(Path(__file__).read_bytes())
    five_mode = mode == 'FIVE_DIAG'
    limit = 395 if mode in ('DE_NIBP', 'FIVE_DIAG') else 60
    result = dict(status='NOT_STARTED', exit_code=1, mode=mode, channel_profile=channel_profile,
                  electrical_condition='40_41_OHM_DIAGNOSTIC_NOT_NORMAL_TERMINATION' if five_mode else 'TWO_POINT_60_OHM', recording_commands=0,
                  pump_commands=0, Flash_writes=0, start_commands=0, observe_seconds_bound=limit)
    raw = (out / 'serial-rx-private.bin').open('xb')
    log = (out / 'lines-private.jsonl').open('x', encoding='utf-8')
    port = serial.Serial(port=None, baudrate=115200, timeout=.05, write_timeout=2)
    port.dtr = port.rts = False
    port.port = 'COM15'
    pending = bytearray()
    armed = False
    stop_seen = False
    audio_stop = False
    latest_audio = {}
    latest_E_state = {}
    diagnostics = []
    source_process = None
    source_log = None
    nibp_wire = None
    cleaning = False
    five_operational_required = False
    five_state_seen = False
    five_trace_nodes = set()

    def line(deadline):
        nonlocal stop_seen, audio_stop, latest_audio, latest_E_state, five_state_seen
        while time.monotonic() < deadline:
            data = port.read(1)
            pending.extend(data)
            raw.write(data)
            if len(pending) > 32768:
                raise ValueError('FIELD01_SERIAL_LINE_BOUND')
            if data == b'\n':
                text = pending.decode('ascii', errors='replace').strip()
                pending.clear()
                row = dict(monotonic=time.monotonic(), UTC_ms=time.time_ns() // 1000000, text=text)
                log.write(json.dumps(row) + '\n')
                log.flush()
                raw.flush()
                if text == 'B5 STOPPED NO_AUTOREARM':
                    stop_seen = True
                if 'UNI AUDIO ' in text:
                    fields = text[text.index('UNI AUDIO ') + 10:].split()
                    latest_audio = {k: int(v) for k, v in (p.split('=') for p in fields)}
                    audio_stop = all(latest_audio.get(k) for k in ('stop_ack', 'stop_query', 'stop_idle'))
                if text.startswith(('B5 DIAG ', 'ABC A_CAN ', 'UNI CAN ', 'B5 QUEUE ', 'B5 WAVE ')):
                    diagnostics.append(row)
                if text.startswith('ABC E_STATE '):
                    latest_E_state = {k: int(v) for k, v in (p.split('=') for p in text[12:].split())}
                if five_mode and not cleaning:
                    trace = check_five_diagnostic(text, five_operational_required)
                    if trace:
                        if trace[0] == 'STATE':
                            five_state_seen = True
                        else:
                            five_trace_nodes.add(trace[1]['node'])
                    if (job / 'B_FAULT.json').exists():
                        raise RuntimeError('FIELD01_B_SOURCE_OBSERVER_FAULT')
                return text
        raise TimeoutError('FIELD01_SERIAL_READ_TIMEOUT')

    def until(prefix, seconds):
        deadline = time.monotonic() + seconds
        while True:
            text = line(deadline)
            if text.startswith(prefix):
                return text

    try:
        if not (job / 'receiver/READY.json').exists() or (job / 'receiver/receipt-public.json').exists():
            raise ValueError('FIELD01_RECEIVER_NOT_ACTIVE')
        owner = json.loads((job / 'owner-power-confirmation.json').read_text())
        expected = ['A', 'B', 'C', 'D', 'E'] if five_mode else ['C', 'D', 'E'] if mode == 'DE_NIBP' else ['C', 'A', 'D']
        if owner['powered'] != expected or owner['COM'] != 'COM15':
            raise ValueError('FIELD01_OWNER_SCOPE_MISMATCH')
        if five_mode:
            if owner['JLink'] != 'B' or channel_profile not in ('ECG60', 'RR') or not (job / 'B_READY.json').exists():
                raise ValueError('FIELD01_FIVE_B_PROBE_PROFILE_OR_SOURCE_NOT_READY')
            if owner['CAN_ohms_CAN1'] < 38 or owner['CAN_ohms_CAN1'] > 43 or owner['CAN_ohms_CAN2'] < 38 or owner['CAN_ohms_CAN2'] > 43:
                raise ValueError('FIELD01_FIVE_OWNER_RESISTANCE_UNEXPECTED')
        elif mode == 'DE_NIBP':
            if owner['JLink_computer_connected'] or source_observer:
                raise ValueError('FIELD01_DE_NO_DEBUGGER_OR_A_OBSERVER')
        elif owner['JLink'] != 'A':
            raise ValueError('FIELD01_A_PROBE_POSITION_MISMATCH')
        settings = json.loads((job / 'voice-runtime-credentials-private.json').read_text())
        wifi = json.loads((job / 'host-hotspot-runtime-private.json').read_text())
        fields = [b'b5-gateway', settings['roles']['b5-gateway'].encode('ascii'), b'b5-c-isolated',
                  wifi['ssid'].encode('utf-8'), wifi['wifi_password'].encode('utf-8')]
        sizes = [33, 65, 41, 33, 65]
        if any(not value or len(value) >= size for value, size in zip(fields, sizes)):
            raise ValueError('FIELD01_CONFIG_LENGTH')
        body = b'MCF3' + b''.join(v.ljust(n, b'\0') for v, n in zip(fields, sizes)) + struct.pack('<I', int(time.time()))
        port.open()
        port.write(b'I')
        if until('UNI ID ', 3) != 'UNI ID V1 DUAL_CAN_MIC_MQTT_TTS CONFIG_RAM':
            raise ValueError('FIELD01_C_IDENTITY_MISMATCH')
        port.write(b'F' + body + struct.pack('<I', zlib.crc32(body)))
        until('UNI CONFIG_OK', 3)
        # 沿用420秒硬截止；主机最晚第395秒发X，另留15秒清理，不改90秒有效期。
        port.write(b'B5START\n')
        armed = True
        result['start_commands'] = 1
        result['armed_monotonic'] = time.monotonic()
        (out / 'ARM_ATTEMPT.json').write_text(json.dumps(dict(monotonic=result['armed_monotonic'], UTC_ms=time.time_ns() // 1000000)) + '\n')
        deadline = result['armed_monotonic'] + (50 if five_mode else 160)
        next_query = 0
        while time.monotonic() < deadline:
            if time.monotonic() >= next_query:
                port.write(b'Q')
                next_query = time.monotonic() + 1
            try:
                text = line(min(deadline, time.monotonic() + 1))
            except TimeoutError:
                continue
            if stop_seen or text == 'GW CLOSE_UNSYNCED_MANUAL_POWER_REQUIRED':
                raise ValueError('FIELD01_CONNECT_STOP_OR_UNSYNCED')
            if latest_audio.get('online') and latest_audio.get('subscribed'):
                if not five_mode or five_state_seen and five_trace_nodes == {1, 2, 4, 5} and five_nodes_online(latest_snapshot(job / 'receiver/browser-snapshots-private.jsonl')):
                    break
        else:
            raise TimeoutError('FIELD01_CONNECT_NOT_READY')
        if source_observer:
            source_log = (job / 'A-observer-native-private.log').open('xb')
            source_process = subprocess.Popen([sys.executable, '-X', 'utf8', str(source_observer)],
                                             stdout=source_log, stderr=subprocess.STDOUT,
                                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 15
            while not (job / 'A-source-observation/READY.json').exists():
                if source_process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('FIELD01_A_OBSERVER_NOT_READY')
                try:
                    line(min(deadline, time.monotonic() + .2))
                except TimeoutError:
                    pass
        t0 = time.monotonic()
        window = ManualNIBPWindow(result['armed_monotonic'], t0) if mode == 'DE_NIBP' else None
        five_window = FiveDiagnosticWindow(result['armed_monotonic'], t0) if five_mode else None
        five_operational_required = five_mode
        t0_doc = dict(monotonic=t0, UTC_ms=time.time_ns() // 1000000, duration_bound_s=limit,
                      scope=mode + '_POINT_TO_POINT_NOT_FIVE_BOARD_ACCEPTANCE')
        if window:
            t0_doc.update(operator_start_budget_s=window.start_deadline - t0,
                          completion_wait_after_start_s=120, after_completion_observe_s=95,
                          stop_deadline_monotonic=window.stop_deadline)
        if five_window:
            (job / 'COMMON_T0.json').write_text(json.dumps(dict(t0_doc, warmup_s=45, evaluation_s=300)) + '\n')
        else:
            (job / 'T0.json').write_text(json.dumps(t0_doc) + '\n')
        print(json.dumps(dict(event=mode + '_POINT_TO_POINT_T0', duration_bound_s=limit, microphone=False)), flush=True)
        end = five_window.end if five_window else window.end if window else t0 + limit
        nibp = None
        if mode == 'DE_NIBP':
            nibp_wire = (job / 'receiver/MQTT-private.jsonl').open(encoding='utf-8')
        while time.monotonic() < end:
            if five_mode and (job / 'B_FAULT.json').exists():
                raise RuntimeError('FIELD01_B_SOURCE_OBSERVER_FAULT')
            if five_window and time.monotonic() >= five_window.evaluation_start and not (job / 'T0.json').exists():
                evaluation = dict(monotonic=five_window.evaluation_start,
                                  UTC_ms=t0_doc['UTC_ms'] + 45000, duration_s=300,
                                  common_monotonic=t0, warmup_s=45, channel_profile=channel_profile,
                                  electrical='40_41_OHM_ENGINEERING_DIAGNOSTIC', formal_acceptance=False)
                (job / 'T0.json').write_text(json.dumps(evaluation) + '\n')
                print(json.dumps(dict(event='FIVE_EVALUATION_STARTED', evaluation_s=300, channel_profile=channel_profile)), flush=True)
            if window and latest_E_state.get('flags', 0) & 32 and window.measurement_start is None:
                window.observed_start(time.monotonic())
                start = dict(monotonic=window.measurement_start, E_state=latest_E_state,
                             completion_deadline_monotonic=window.completion_deadline)
                result['E_measurement_start_observed'] = start
                (job / 'E_MEASUREMENT_STARTED.json').write_text(json.dumps(start, indent=2) + '\n')
                print(json.dumps(dict(event='E_MEASUREMENT_STARTED', completion_wait_bound_s=120)), flush=True)
            if nibp_wire and nibp is None:
                nibp = read_completed_nibp(nibp_wire, t0_doc['UTC_ms'])
                if nibp:
                    nibp['host_seen_monotonic'] = time.monotonic()
                    result['new_completed_nibp'] = nibp
                    (job / 'NIBP_RECEIVED.json').write_text(json.dumps(nibp, indent=2) + '\n')
                    window.observed_result(time.monotonic())
                    end = window.end
                    print(json.dumps(dict(event='E_NIBP_RECEIVED_WAIT_EXPIRY', value=nibp['message']['value'])), flush=True)
                window.check(time.monotonic())
            if time.monotonic() >= next_query:
                port.write(b'Q')
                next_query = time.monotonic() + 1
            try:
                text = line(min(end, time.monotonic() + 1))
            except TimeoutError:
                continue
            if stop_seen or text == 'GW CLOSE_UNSYNCED_MANUAL_POWER_REQUIRED' or latest_audio.get('online') == 0:
                raise ValueError('FIELD01_WINDOW_STOP_OR_NETWORK_LOST')
            if source_process and source_process.poll() is not None:
                raise RuntimeError('FIELD01_A_OBSERVER_EXITED_EARLY')
            for prefix in ('B5 DIAG ', 'ABC A_CAN '):
                if text.startswith(prefix):
                    values = dict((k, int(v)) for k, v in (x.split('=') for x in text[len(prefix):].split()))
                    if values['txfail'] or values['overflow'] or values['esr'] & 0xffff0004:
                        raise ValueError('FIELD01_C_CAN_ERROR')
        result.update(status=mode + '_CAPTURE_COMPLETE_REQUIRES_LAYERED_REVIEW', exit_code=0,
                      T0=t0_doc, actual_observe_s=time.monotonic() - t0)
    except (Exception, KeyboardInterrupt) as error:
        (out / 'failure-private.json').write_text(json.dumps(dict(type=type(error).__name__, detail=str(error))) + '\n')
        result.update(status='STOP_REQUIRES_REVIEW', error_type=type(error).__name__)
    finally:
        cleaning = True
        if port.is_open and armed:
            try:
                port.write(b'X')
                result['global_stop_commands'] = 1
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and not (stop_seen and audio_stop):
                    port.write(b'Q')
                    try:
                        line(min(deadline, time.monotonic() + 1))
                    except TimeoutError:
                        pass
                result.update(C_STOP_banner=stop_seen, TTS_STOP_ACK_QUERY_IDLE=audio_stop)
                if not (stop_seen and audio_stop):
                    result['exit_code'] = 1
            except (OSError, TimeoutError) as error:
                result.update(exit_code=1, cleanup_error_type=type(error).__name__)
        if port.is_open:
            port.close()
        result.update(serial_closed=True, diagnostic_rows=len(diagnostics), last_audio=latest_audio,
                      tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if source_process:
            # 结束标记让尚未到T0的只读工人退出；不向目标补发复位/Go。
            (job / 'A_SOURCE_FINISH').touch()
            try:
                result['A_observer_native_exit'] = source_process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                source_process.kill()
                source_process.wait(timeout=3)
                result.update(exit_code=1, A_observer_forced_exit=True)
            if source_process.returncode:
                result['exit_code'] = 1
        if source_log:
            source_log.close()
        if nibp_wire:
            nibp_wire.close()
        if five_mode:
            (job / 'END_B').touch()
        raw.close()
        log.close()
        (out / 'diagnostics.json').write_text(json.dumps(diagnostics, indent=2) + '\n')
        (out / 'receipt-public.json').write_text(json.dumps(result, indent=2) + '\n')
        (job / 'receiver/STOP_RECEIVER').touch()
    print(json.dumps(result), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--source-observer', type=Path)
    parser.add_argument('--mode', choices=('AD60', 'DE_NIBP', 'FIVE_DIAG'), default='AD60')
    parser.add_argument('--channel-profile', choices=('ECG60', 'RR'))
    arguments = parser.parse_args()
    raise SystemExit(run(arguments.job, arguments.source_observer, arguments.mode, arguments.channel_profile))
