"""从仓库外配置生成 STM32 sector 7 配置，不输出敏感字段。"""

import argparse
import json
from pathlib import Path
import struct
import time


def field(value, size):
    data = value.encode('utf-8')
    # 当前 AT 字符串不做转义，遇到特殊字符明确拒绝，避免改变命令含义。
    if len(data) >= size or any(char in value for char in ['"', '\\', '\r', '\n', '\0']):
        raise ValueError('Field exceeds capacity or requires AT escaping')
    return data.ljust(size, b'\0')


# 生成配置不等于烧录；布局必须与 gateway_config.h 一致，输入和输出均限定在仓库外。
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wifi', type=Path, required=True)
    parser.add_argument('--mqtt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    for path in [args.wifi, args.mqtt, args.output]:
        if path.resolve().is_relative_to(repository):
            raise ValueError('Credentials and binary must remain outside the repository')
    wifi = json.loads(args.wifi.read_text(encoding='utf-8'))
    mqtt = json.loads(args.mqtt.read_text(encoding='utf-8'))
    if mqtt.get('port', 8883) != 8883 or mqtt.get('gateway_id', 'GW-C-001') != 'GW-C-001':
        raise ValueError('This phase uses the fixed Gateway identity and TLS port')
    data = struct.pack('<II', 0x31435747, int(time.time()) - 86400)
    for value, size in [
        (wifi['ssid'], 33),
        (wifi['password'], 65),
        (mqtt['host'], 65),
        (mqtt['username'], 33),
        (mqtt['password'], 65),
        (mqtt['client_id'], 41),
    ]:
        data += field(value, size)
    # C 结构末尾按四字节对齐；独占创建避免覆盖现有凭据或备份。
    with args.output.open('xb') as output:
        output.write(data.ljust(312, b'\0'))
    print('External Gateway configuration created (312 bytes)')


if __name__ == '__main__':
    main()
