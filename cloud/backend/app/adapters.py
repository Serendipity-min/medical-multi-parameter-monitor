"""只接受合同中的 MQTT Topic，不保留旧设备 WSS/MMP 入口。"""

import json
from .models import Telemetry


# MQTT Topic 是路由身份的唯一来源；载荷先校验大小和结构，再交给严格模型检查。
def decode_mqtt(topic: str, payload: bytes) -> Telemetry:
    if len(payload) > 32768:
        raise ValueError('payload too large')
    parts = topic.split('/')
    if parts[:2] != ['mpm', 'v1']:
        raise ValueError('topic prefix')
    if len(parts) == 4 and parts[3] == 'status':
        node, stream, kind = 'GATEWAY', 'GATEWAY_STATUS', 'status'
    elif len(parts) == 5 and parts[4] in {'status', 'event'}:
        node, kind = parts[3], parts[4]
        stream = 'NODE_STATUS' if kind == 'status' else 'FAULT'
    elif len(parts) == 6 and parts[4] in {'telemetry', 'replay'}:
        node, kind, stream = parts[3], parts[4], parts[5].upper()
    else:
        raise ValueError('topic shape')
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError('object required')
    # Topic 决定路由身份，载荷重复提供身份时必须完全一致。
    for key, value in {'gateway_id': parts[2], 'node_id': node, 'stream': stream}.items():
        if key in data and data[key] != value:
            raise ValueError('topic payload mismatch')
        data[key] = value
    message = Telemetry.model_validate(data)
    if (kind == 'replay') != (message.source == 'REPLAY'):
        raise ValueError('replay topic source mismatch')
    # 历史 EMCY 进入 REPLAY 区，不作为当前报警；旧状态始终禁止补传。
    if kind in {'telemetry', 'replay'} and (
        stream in {'NODE_STATUS', 'GATEWAY_STATUS'} or (stream == 'FAULT' and kind != 'replay')
    ):
        raise ValueError('reserved stream')
    return message
