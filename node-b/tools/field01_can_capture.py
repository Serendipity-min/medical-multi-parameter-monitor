"""五板双段一次60秒真实CAN取证；无网络、录音、复位和下载。"""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import struct
import time

import b4_capture_decode as codec
import b4_recovery as recovery
from b4_serial_capture import open_port, need

NODES = {1: 0, 5: 0, 2: 1, 4: 1}
WAVES = {0x181: (1, 0, 20), 0x182: (2, 4, 4), 0x282: (2, 6, 20)}


def source_node(ident):
    for node in NODES:
        if ident in (0x700+node, 0x80+node, 0x580+node):
            return node
        if ident in (0x180+node, 0x280+node, 0x380+node, 0x480+node, 0x680+node):
            return node
    return None


def check_row(row):
    kind, ident, flags = row['kind'], row['id'], row['flags']
    data = bytes.fromhex(row['data'])
    if kind == 7:
        need(data[:4] == b'B4C4' and not flags, 'C_BOOT_IDENTITY_OR_INIT_ERROR')
    if kind == 4:
        raise ValueError('C_TX_FAILURE')
    if kind == 1:
        node = source_node(ident)
        need(node is not None and NODES[node] == row['bus'], 'UNKNOWN_OR_WRONG_BUS_NODE')
        need(not flags & 0xffff0004, 'C_RX_ERRORS_OR_BUSOFF')
        if ident == 0x700+node:
            need(row['dlc'] == 1 and data[0] in (0, 5), 'SOURCE_NOT_OPERATIONAL')
        if ident == 0x80+node:
            need(not int.from_bytes(data[:2], 'little') and not data[2], 'SOURCE_EMCY_ERROR')
    if kind == 5:
        a, b = struct.unpack('<II', data)
        if ident in (0, 1):
            need(not a & 0xffff0004 and not flags, 'C_CAN_ERRORS_OR_FIFO_OVERFLOW')
        if ident == 2:
            need(not a and not flags, 'C_CAPTURE_DROP_OR_INIT_ERROR')
        if ident == 4:
            need(codec.vector_diagnostic_ok(a, b, flags, True), 'C_VECTOR_OR_FAULT')
        if ident in (5, 8):
            need(not b and not flags, 'C_TX_FAILED_OR_BUSOFF')
        if ident == 7:
            need((a, b, flags) == (60000, 500000, 2), 'C_NOT_FIVE_FULL_60S_IMAGE')
        if ident == 10:
            need(not a and not b, 'C_MALFORMED_OR_WRONG_BUS')


def assess(rows, parser):
    start = [r for r in rows if r['kind'] == 9]
    stop = [r for r in rows if r['kind'] == 6]
    failures = []
    if len(start) != 1 or len(stop) != 1:
        failures.append('START_OR_STOP_EVIDENCE')
    elif stop[0]['flags'] or struct.unpack('<II', bytes.fromhex(stop[0]['data'])) != (60000, 0):
        failures.append('STOP_LIMIT_ERROR_OR_CAPTURE_DROP')
    if any(b['seq'] != a['seq']+1 for a, b in zip(rows, rows[1:])):
        failures.append('SERIAL_SEQUENCE_GAP')
    if rows and (parser.crc_errors != rows[0]['wire_crc_before'] or parser.discarded != rows[0]['wire_discarded_before']):
        failures.append('SERIAL_CRC_OR_RESYNC_AFTER_FIRST_PACKET')
    if parser.buffer:
        failures.append('SERIAL_TRUNCATED_TAIL')
    body = [r for r in rows if start and start[0]['seq'] <= r['seq'] <= (stop[0]['seq'] if stop else 0xffffffff)]
    counts = Counter(f"CAN{r['bus']+1}:0x{r['id']:03x}" for r in body if r['kind'] == 1)
    hbs = {node: sum(r['kind'] == 1 and r['id'] == 0x700+node and bytes.fromhex(r['data'])[0] == 5 for r in body) for node in NODES}
    if any(count < 90 for count in hbs.values()):
        failures.append('SOURCE_HEARTBEAT_COVERAGE')
    for row in rows:
        try:
            check_row(row)
        except ValueError as error:
            failures.append(str(error))
    waves = defaultdict(list)
    model_samples = Counter()
    model_valid = Counter()
    model_match = model_missing = 0
    pending = None
    for row in body:
        if row['kind'] == 1 and row['id'] in WAVES:
            node, stream, _ = WAVES[row['id']]
            value, tick = struct.unpack('<iI', bytes.fromhex(row['data']))
            waves[node, stream].append((value, tick))
        if row['kind'] == 8:
            pending = row
        if row['kind'] == 10 and pending and row['seq'] == pending['seq']+1:
            node, stream, count = pending['flags'] & 255, pending['id'], pending['flags'] >> 16
            key = f'NODE{node}:stream{stream}'
            model_samples[key] += count
            model_valid[key] += bool(pending['flags'] & 256)
            if (node, stream) in ((1, 0), (2, 4), (2, 6)):
                last, hashed = struct.unpack('<iI', bytes.fromhex(pending['data']))
                raw = waves[node, stream]
                match = False
                for end in range(len(raw), max(count-1, len(raw)-200), -1):
                    values = [x[0] for x in raw[end-count:end]]
                    if len(values) == count and values[-1] == last and codec.value_hash(values) == hashed:
                        match = True
                        break
                model_match += match
                model_missing += not match
    cadence = {}
    for ident, (node, stream, step) in WAVES.items():
        samples = waves[node, stream]
        deltas = [codec.signed_delta(b[1], a[1]) for a, b in zip(samples, samples[1:])]
        cadence[f'NODE{node}:stream{stream}'] = dict(raw_CAN_points=len(samples),
            tick_deltas=dict(Counter(deltas)),outside_step_plus_minus_1=sum(not step-1 <= x <= step+1 for x in deltas))
        if not samples:
            failures.append(f'NO_WAVE_0x{ident:x}')
    if model_missing:
        failures.append('WAVE_MODEL_NOT_FOUND_IN_RAW_CAN')
    return dict(status='SHORT_41OHM_CAN_DIAGNOSTIC_OBSERVED' if not failures else 'NOT_PASS',
        failures=sorted(set(failures)),source_OP5_heartbeat_counts=hbs,raw_CAN_counts=dict(counts),
        raw_wave_cadence=cadence,model_samples=dict(model_samples),valid_model_batches=dict(model_valid),
        waveform_model_hash_matches=model_match,waveform_model_unmatched=model_missing,
        formal_five_CAN_300s='NOT_RUN',cloud_web_voice='NOT_RUN',analog_signal_quality='NOT_MEASURED',
        time_policy='LOCAL_TEST_EPOCH_NOT_REAL_UTC',source_original_samples_before_CAN='NOT_CAPTURED')


def capture(port, out):
    parser = codec.Parser()
    rows = []
    began = time.monotonic()
    sent = False
    stop = None
    hbs = {}
    received = {}
    diag = set()
    started_at = None
    result = dict(status='STOP_TARGET', exit_code=1)
    with (out/'serial-raw-private.bin').open('xb') as raw, (out/'packets-private.jsonl').open('x') as log:
        try:
            while stop is None:
                now = time.monotonic()
                need(now-began < 80, 'HOST_CAPTURE_DEADLINE')
                if (out/'STOP').exists():
                    raise ValueError('OWNER_STOP')
                chunk = port.read(8192)
                raw.write(chunk)
                for row in parser.feed(chunk):
                    log.write(json.dumps(row)+'\n')
                    if rows:
                        need(row['seq'] == rows[-1]['seq']+1, 'SERIAL_SEQUENCE_GAP')
                    rows.append(row)
                    check_row(row)
                    if row['kind'] == 7:
                        need(len(rows) == 1, 'C_UNEXPECTED_REBOOT')
                    if row['kind'] == 1:
                        node = source_node(row['id'])
                        if node is not None and row['id'] == 0x700+node and bytes.fromhex(row['data'])[0] == 5:
                            hbs[node] = now
                        if sent and row['id'] == 0x700+node:
                            need(bytes.fromhex(row['data'])[0] == 5, 'SOURCE_RESTART_AFTER_ARM')
                    if row['kind'] == 5:
                        diag.add(row['id'])
                        if row['id'] in (0, 1):
                            received[row['id']] = struct.unpack('<II', bytes.fromhex(row['data']))[1]
                    if row['kind'] == 9:
                        need(sent and not (out/'START-OBSERVED.json').exists() and not row['flags'], 'UNEXPECTED_START')
                        (out/'START-OBSERVED.json').write_text(json.dumps(dict(host_monotonic=now)))
                        started_at = now
                    if row['kind'] == 6:
                        stop = row
                log.flush()
                if rows:
                    need(parser.crc_errors == rows[0]['wire_crc_before'] and parser.discarded == rows[0]['wire_discarded_before'], 'SERIAL_CRC_OR_RESYNC')
                if not sent:
                    need(now-began < 12, 'PREARM_NODES_OR_DIAGNOSTICS_NOT_READY')
                    if {0, 1, 2, 4, 5, 7, 8, 10, 11} <= diag and received.get(0, 0) and received.get(1, 0):
                        sent = True
                        (out/'START-INTENT.json').write_text(json.dumps(dict(host_monotonic=now, command='B4START', limit_ms=60000)))
                        need(port.write(b'B4START\n') == 8, 'START_SHORT_WRITE')
                        port.flush()
                        print('FIVE_CAN_DIAGNOSTIC_ARM_SENT_60S', flush=True)
                if started_at is not None and now-started_at > 2.5 and stop is None:
                    need(all(node in hbs and now-hbs[node] < 1.5 for node in NODES), 'SOURCE_HEARTBEAT_TIMEOUT')
            result = assess(rows, parser)
            result['exit_code'] = 0 if not result['failures'] else 3
        except (Exception, KeyboardInterrupt) as error:
            (out/'failure-private.json').write_text(json.dumps(dict(type=type(error).__name__, reason=str(error))))
            result.update(error_type=type(error).__name__, reason=str(error))
            if sent and stop is None:
                result['abort_attempted'] = True
                try:
                    result['abort_bytes'] = port.write(b'X')
                    port.flush()
                except Exception as abort_error:
                    result['abort_error_type'] = type(abort_error).__name__
        result.update(START_attempts=int(sent),target_reset_flash_commands=0,elapsed_host_s=time.monotonic()-began)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port')
    p.add_argument('--out', type=Path)
    p.add_argument('--installation', type=Path)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    if not a.execute:
        print(json.dumps(dict(status='PLAN_ONLY_NO_PORT',seconds=60,nodes=NODES,recording=False,cloud=False)))
        return 0
    need(a.port and a.out and a.installation, 'PORT_OUTPUT_INSTALL_REQUIRED')
    recovery.protected(a.out.parent, False)
    proof = json.loads(recovery.read(a.installation, False))
    need(proof['board'] == 'C' and proof['exit_code'] == 0 and proof['Close_completed'] and proof['options_unchanged'] and proof['all_other_sectors_unchanged'], 'C_INSTALL_PROOF')
    need(not a.out.exists(), 'NEW_OUTPUT_REQUIRED')
    import serial
    from serial.tools import list_ports
    need(any(x.device == a.port and x.vid == 0x1a86 and x.pid == 0x7523 for x in list_ports.comports()), 'C_CH340_PORT_NOT_PRESENT')
    a.out.mkdir()
    port = None
    try:
        port = open_port(serial.Serial, a.port)
        result = capture(port, a.out)
    finally:
        if port:
            port.close()
    result['serial_closed'] = True
    (a.out/'receipt-private.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
