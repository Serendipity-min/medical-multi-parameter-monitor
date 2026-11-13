"""真实C输出经既有Backend解码/Hub；离线运行，不创建服务器或修改云代码。"""
from pathlib import Path
import argparse
import asyncio
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'cloud/backend'))
from app.adapters import decode_mqtt
from app.hub import Hub


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('canonical', type=Path)
    parser.add_argument('--temperature', action='store_true')
    parser.add_argument('--snapshots', type=Path)
    args = parser.parse_args()
    now = [1792713689.0]
    hub = Hub(['GW-C-001'], clock=lambda: now[0], monotonic=lambda: now[0])
    hub.broker_connected = True
    def gateway_status(session, seq):
        return decode_mqtt('mpm/v1/GW-C-001/status', json.dumps(dict(timestamp=int(now[0]*1000),
            session_id=session, seq=seq, validity='VALID', source='MOCK', synthetic=True, unit='state', value='ONLINE')).encode())
    hub.ingest(gateway_status('T0-HOST-GATEWAY', 1))
    seen = set(); count = 0; ecg = 0; temperature = 0; valid_temperature = 0
    for line in args.canonical.read_text(encoding='utf-8').splitlines():
        topic, payload = line.split('\t', 1)
        message = decode_mqtt(topic, payload.encode())
        assert message.source in ('MOCK', 'REPLAY') and message.synthetic
        if message.timestamp <= int(now[0]*1000): hub.ingest(message)
        seen.add(message.stream); count += 1
        if message.stream == 'ECG':
            assert message.sample_rate == 250 and len(message.samples) == 100
            ecg += 1
        if message.stream == 'TEMP':
            if message.validity == 'VALID':
                assert args.temperature and message.value == 33.07
                valid_temperature += 1
            else:
                assert message.value is None
            temperature += 1
    assert {'PPG', 'SPO2', 'PR', 'NIBP', 'ECG', 'HR', 'RESP', 'RR', 'TEMP', 'NODE_STATUS'} <= seen
    assert ecg > 200 and temperature > 80
    if args.temperature: assert 0 < valid_temperature < temperature
    else: assert valid_temperature == 0
    snapshots = []
    if args.snapshots:
        def export(name): snapshots.append({'scenario': name, 'snapshot': hub.snapshot('GW-C-001')})
        def stream(name): return next(x for x in hub.snapshot('GW-C-001')['streams'] if x['stream'] == name)
        initial = hub.snapshot('GW-C-001')
        assert initial['nodes'] == {'NODE-A':'ONLINE','NODE-B':'ONLINE'}
        assert stream('HR')['value'] == 60 and stream('RR')['value'] == 15 and stream('TEMP')['value'] == 33.07
        assert stream('SPO2')['value'] == 98 and stream('NIBP')['value'] == [120,80]
        export('dual-online')
        hr = hub.current[('GW-C-001','NODE-B','HR')][0]
        assert not hub.ingest(hr)
        invalid = hr.model_copy(update={'seq':hr.seq+1,'validity':'INVALID','value':None})
        assert hub.ingest(invalid) and stream('HR')['value'] is None
        export('invalid-HR')
        restored = hr.model_copy(update={'seq':hr.seq+2})
        assert hub.ingest(restored) and stream('HR')['value']==60
        export('restored-HR')
        replay = hr.model_copy(update={'source':'REPLAY','seq':hr.seq+100,'value':38.0})
        assert hub.ingest(replay) and stream('HR')['value']==60
        export('replay-no-override')
        queue = asyncio.Queue(maxsize=1);hub.subscribers[queue]='GW-C-001'
        hub.publish();first = queue.get_nowait();hub.publish();hub.publish()
        assert queue.qsize()==1 and queue.get_nowait() is not first
        del hub.subscribers[queue]
        now[0] += .1
        status = hub.current[('GW-C-001','NODE-B','NODE_STATUS')][0]
        assert hub.ingest(status.model_copy(update={'session_id':'T0-NEW-B-BOOT','seq':1,'timestamp':int(now[0]*1000)}))
        assert stream('HR')['validity']=='STALE' and stream('HR')['value'] is None and stream('SPO2')['value']==98
        export('B-new-boot')
        assert hub.ingest(hr.model_copy(update={'seq':hr.seq+1000,'timestamp':int(now[0]*1000)}))
        assert stream('HR')['value'] is None
        export('old-epoch-no-reactivation')
        now[0] += 6
        for node in ('NODE-A','NODE-B'):
            s=hub.current[('GW-C-001',node,'NODE_STATUS')][0]
            hub.ingest(s.model_copy(update={'seq':s.seq+1,'timestamp':int(now[0]*1000)}))
        hub.ingest(gateway_status('T0-HOST-GATEWAY', 2))
        assert stream('SPO2')['value'] is None and stream('NIBP')['value']==[120,80]
        export('ordinary-stale-NIBP-retained')
        hub.ingest(gateway_status('T0-NEW-GATEWAY-BOOT', 1))
        assert all(x['value'] is None and not x['samples'] for x in hub.snapshot('GW-C-001')['streams'])
        export('gateway-new-boot')
        args.snapshots.write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'c_to_backend': count, 'ecg_100_sample_batches': ecg,
                      'temperature_records': temperature, 'valid_temperature_records':valid_temperature,
                      'invalid_temperature_records':temperature-valid_temperature, 'Hub_UI_scenarios':len(snapshots), 'streams': sorted(seen),
                      'schema_version': hub.snapshot('GW-C-001')['schema_version'],
                      'network_access': False}))


if __name__ == '__main__':
    main()
