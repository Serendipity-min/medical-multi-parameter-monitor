"""仅生成隔离RAM配置；原GatewayConfig 312B布局不变，不提供Flash写入口。"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from gateway.mqtt.provision import field


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wifi',type=Path,required=True)
    parser.add_argument('--mqtt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if any(p.resolve().is_relative_to(ROOT) for p in (args.wifi,args.mqtt,args.output)):raise ValueError('EXTERNAL_CONFIG_ONLY')
    wifi=json.loads(args.wifi.read_text(encoding='utf-8-sig'));mqtt=json.loads(args.mqtt.read_text(encoding='utf-8-sig'))
    if mqtt.get('port')!=8884 or mqtt.get('username')!='h3-gateway' or mqtt.get('gateway_id')!='GW-C-001':raise ValueError('ISOLATED_CREDENTIALS_REQUIRED')
    floor=int(time.time())-86400;data=struct.pack('<II',0x31435747,floor)
    for value,size in [(wifi['ssid'],33),(wifi['password'],65),(mqtt['host'],65),(mqtt['username'],33),(mqtt['password'],65),(mqtt['client_id'],41)]:data+=field(value,size)
    data=data.ljust(312,b'\0')
    with args.output.open('xb') as f:f.write(data)
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'minimum_epoch':floor,
            'destination':'RAM_ONLY_0x2001FE00','configuration_flash_written':False,
            'created_utc':datetime.now(timezone.utc).isoformat()}


if __name__=='__main__':
    try:print(json.dumps(main(),indent=2))
    except Exception as exc:
        print(json.dumps({'failure_type':type(exc).__name__,'details_suppressed':True}));raise SystemExit(1)
