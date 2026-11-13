"""只读五板诊断原件：复用B稳定版本/逐点匹配，分别统计实时、历史与源无效。"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys

os.environ['MPM_NODE_PROFILE'] = 'five'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cloud/backend'))
from app.adapters import decode_mqtt
import b5_g3_contract as g
from b5_g3_review import reconstruct, match_batch


def review(job):
    marker = next(p for p in (job / 'T0.json', job / 'COMMON_T0.json', job / 'C-observation/ARM_ATTEMPT.json') if p.exists())
    t0 = json.loads(marker.read_text())
    low, high = t0['UTC_ms'], t0['UTC_ms'] + 300000
    source = None
    try:
        raw, can, clocks, source_stats = reconstruct(job)
        source = raw, can, g.can_utc_points(can, clocks)
    except (ValueError, OSError) as error:
        (job / 'B-review-failure-private.json').write_text(json.dumps(dict(type=type(error).__name__, detail=str(error))) + '\n')
        source_stats = dict(status='SOURCE_CAPTURE_INCOMPLETE', error_type=type(error).__name__)
    messages = {}
    counts = Counter()
    mismatched_source = []
    waveform_source_points = Counter()
    waveform_source_sequences = {'ECG': set(), 'RESP': set()}
    in_window_sequences = {'ECG': set(), 'RESP': set()}
    for line in (job / 'receiver/MQTT-private.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row['retain']:
            continue
        message = decode_mqtt(row['topic'], bytes.fromhex(row['payload_hex'])).model_dump()
        if not low <= message['timestamp'] < high:
            continue
        name = message['node_id'] + '/' + message['stream']
        counts[name + '/' + message['source'] + '/' + message['validity']] += 1
        messages[(g.telemetry_key(message), message['source'])] = message
        if message['node_id'] == 'NODE-B' and message['stream'] in ('ECG', 'RESP') and message['validity'] == 'VALID':
            if source:
                try:
                    matched = match_batch(message, source[2], source[1], source[0])
                    waveform_source_points[message['stream']] += len(matched)
                    waveform_source_sequences[message['stream']].update(x[0] for x in matched)
                    in_window_sequences[message['stream']].update(x[0] for x in matched if low <= x[1] < high)
                except ValueError:
                    mismatched_source.append(dict(stream=message['stream'], seq=message['seq']))
    seen = set()
    unequal = []
    masked = set()
    source_ages = []
    for line in (job / 'receiver/browser-snapshots-private.jsonl').read_text().splitlines():
        row = json.loads(line)
        snapshot = row['snapshot']
        received = list(snapshot['streams'])
        if snapshot.get('replay'):
            received.append(snapshot['replay'])
        for message in received:
            key = g.telemetry_key(message), message['source']
            if key not in messages:
                continue
            if message == messages[key]:
                if key not in seen:
                    source_ages.append(row['arrival_unix_ns']//1000000-message['timestamp'])
                seen.add(key)
            elif message['validity'] != 'VALID' and message['value'] is None and not message['samples']:
                masked.add(key)
            else:
                unequal.append(dict(node=message['node_id'], stream=message['stream'], seq=message['seq']))
    # Hub将状态消息聚合进gateway_state/nodes，不在生理streams中逐条回显。
    status_messages = {key for key, message in messages.items() if message['stream'] in ('GATEWAY_STATUS', 'NODE_STATUS')}
    missing = [dict(node=k[0][0], stream=k[0][1], seq=k[0][3], source=k[1]) for k in messages
               if k not in status_messages and k not in seen and k not in masked]
    traces = Counter()
    last_nodes = {}
    serial = job / 'C-observation/lines-private.jsonl'
    for line in serial.read_text().splitlines():
        text = json.loads(line)['text']
        if text.startswith('FIVE RX '):
            fields = dict((k, int(v)) for k, v in (part.split('=') for part in text[8:].split()))
            last_nodes[fields['node']] = fields
            traces['node_' + str(fields['node'])] += 1
    profile = t0.get('channel_profile', json.loads((job / 'plan-public.json').read_text())['channel_profile'])
    result = dict(scope='FIVE_40_41_OHM_DIAGNOSTIC_NOT_FORMAL_ACCEPTANCE', profile=profile,
                  evaluation_started=(job / 'T0.json').exists(), interval_basis=marker.name,
                  B_source=source_stats, B_matched_valid_source_point_occurrences=dict(waveform_source_points),
                  B_matched_unique_source_sequences={k: len(v) for k, v in waveform_source_sequences.items()},
                  B_matched_unique_source_sequences_in_evaluation_window={k: len(v) for k, v in in_window_sequences.items()},
                  B_source_mismatched_batches=mismatched_source, messages_by_source_validity=dict(counts),
                  broker_unique_messages=len(messages), browser_exact_matches=len(seen),
                  broker_status_messages_aggregated=len(status_messages),
                  browser_expected_telemetry_messages=len(messages)-len(status_messages),
                  browser_only_masked=len(masked-seen), browser_missing=missing, browser_value_mismatches=unequal,
                  first_seen_source_age_ms=dict(min=min(source_ages), max=max(source_ages)) if source_ages else None,
                  C_node_diagnostics=last_nodes, C_node_diagnostic_observations=dict(traces),
                  A_raw_input_point_integrity='NOT_PROVEN_NO_A_RAW_UART_OR_SWD_RECORD',
                  unrelated_simulator_channel='PHYSIOLOGIC_VALIDITY_RECORDED_NOT_ASSUMED_VALID',
                  formal_five_CAN_300s='NOT_CLAIMED_40OHM', formal_five_cloud_300s='NOT_CLAIMED_40OHM')
    (job / 'five-scoped-review-public.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.job), indent=2))
