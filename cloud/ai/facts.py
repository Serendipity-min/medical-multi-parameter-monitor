"""仅从服务端只读快照生成可核验事实，绝不接受浏览器上报读数。"""
import hashlib
import json
import math
import os

CHANNELS = {
    'HR': ('NODE-B', 'bpm', '心率', 0, 350),
    'SPO2': ('NODE-A', '%', '血氧', 0, 100),
    'PR': ('NODE-A', 'bpm', '脉率', 0, 350),
    'RR': ('NODE-B', 'breaths/min', '呼吸率', 0, 100),
    'TEMP': ('NODE-B', 'degC', '体温', 0, 60),
    'NIBP': ('NODE-A', 'mmHg', '血压', 0, 400),
}
if os.environ.get('MPM_NODE_PROFILE', 'three') == 'five':
    CHANNELS['TEMP'] = ('NODE-D', 'degC', '物体温度', 0, 60)
    CHANNELS['NIBP'] = ('NODE-E', 'mmHg', '血压', 0, 400)
KEYWORDS = {'心率': 'HR', '血氧': 'SPO2', '脉率': 'PR', '呼吸率': 'RR', '体温': 'TEMP',
            '温度': 'TEMP', '血压': 'NIBP', '高压': 'NIBP', '低压': 'NIBP'}
ADVICE_TEXT = '请核对设备和数据来源。有疑问可咨询医护人员。'
CLARIFY_TEXT = '请一次询问一项读数。'


def question_rule(question: str) -> tuple[str, set[str]]:
    streams = {stream for word, stream in KEYWORDS.items() if word in question}
    if any(word in question for word in ('建议', '怎么办', '怎么做', '解释', '为什么', '正常', '异常',
                                          '偏高', '偏低', '如何', '用药', '治疗', '参考范围')):
        return 'GENERAL_ADVICE', set()
    if len(streams) > 1:
        return 'MULTI_VALUE', streams
    return ('SINGLE_VALUE' if streams else 'CLARIFY'), streams


def extract(snapshot: dict, gateway: str, now_ms: int) -> list[dict]:
    if snapshot.get('gateway_id') != gateway or snapshot.get('schema_version') != 1:
        raise ValueError('SNAPSHOT_IDENTITY')
    server_time = snapshot.get('server_time', 0)
    if not isinstance(server_time, int) or not -1000 <= now_ms - server_time <= 5000:
        raise ValueError('SNAPSHOT_EXPIRED')
    facts = []
    # 同一节点/流多份输入不择优猜测，整个快照拒绝，避免来源串位。
    seen = set()
    for item in snapshot.get('streams', []):
        stream = item.get('stream')
        if stream not in CHANNELS:
            continue
        node, unit, label, low, high = CHANNELS[stream]
        if stream in seen or item.get('gateway_id') != gateway or item.get('node_id') != node or item.get('unit') != unit:
            raise ValueError('FACT_IDENTITY')
        seen.add(stream)
        source, synthetic = item.get('source'), item.get('synthetic')
        if source not in ('LIVE', 'MOCK', 'REPLAY') or type(synthetic) is not bool:
            raise ValueError('FACT_SOURCE')
        if (source == 'MOCK' and not synthetic) or (source == 'LIVE' and synthetic):
            raise ValueError('FACT_SOURCE')
        validity = item.get('validity')
        if validity not in ('VALID', 'INVALID', 'STALE', 'OFFLINE'):
            raise ValueError('FACT_VALIDITY')
        stamp = item.get('timestamp', 0)
        ttl = 90000 if stream == 'NIBP' else 5000
        state = snapshot.get('nodes', {}).get(node)
        if snapshot.get('gateway_state') != 'ONLINE' or not snapshot.get('broker_connected') or state != 'ONLINE':
            validity = 'OFFLINE' if state == 'OFFLINE' or snapshot.get('gateway_state') == 'OFFLINE' else 'STALE'
        elif not isinstance(stamp, int) or not -1000 <= now_ms - stamp < ttl:
            validity = 'STALE'
        value = item.get('value') if validity == 'VALID' and source != 'REPLAY' else None
        values = value if isinstance(value, list) else [value]
        if value is not None and (len(values) != (2 if stream == 'NIBP' else 1) or any(type(v) not in (float, int) or not math.isfinite(v) or not low <= v <= high for v in values)):
            raise ValueError('FACT_VALUE')
        if validity == 'VALID' and source != 'REPLAY' and value is None:
            raise ValueError('FACT_VALUE')
        session, seq = item.get('session_id'), item.get('seq')
        if not isinstance(session, str) or not session or type(seq) is not int or seq < 0:
            raise ValueError('FACT_PROVENANCE')
        facts.append(dict(stream=stream, node_id=node, gateway_id=gateway, unit=unit,
                          label=label, value=value, validity=validity, source=source,
                          synthetic=synthetic, timestamp=stamp, session_id=session, seq=seq))
    return facts


def digest(facts: list[dict]) -> str:
    return hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()[:32]


def answer_facts(facts: list[dict], question: str) -> str:
    selected = {v for k, v in KEYWORDS.items() if k in question}
    if not selected:
        return '请明确指定心率、呼吸率、血氧、血压或物体温度。'
    lines = []
    for fact in facts:
        if selected and fact['stream'] not in selected:
            continue
        origin = '模拟数据，非真人测量' if fact['synthetic'] else '实时监护数据'
        if fact['source'] == 'REPLAY':
            origin = '历史补传，不代表当前读数'
        value = fact['value']
        label = fact['label']
        if fact['stream'] == 'NIBP' and ('高压' in question) != ('低压' in question):
            label = '血压高压' if '高压' in question else '血压低压'
            if value is not None:value = value[0 if '高压' in question else 1]
        if value is None:
            lines.append(f"{label}：{fact['validity']}，没有可用当前读数；{origin}。")
        else:
            reading = '/'.join(f'{v:g}' for v in value) if isinstance(value, list) else f'{value:g}'
            lines.append(f"{label}：{reading} {fact['unit']}；{origin}。")
    return '\n'.join(lines) or '没有可用的当前监护事实，请确认数据源连接与采集状态。'
