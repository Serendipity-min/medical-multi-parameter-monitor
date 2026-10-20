"""联网候选有界观测，默认只读；显式D只做既有断网试验，绝不控制采集/泵。"""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import time

ROOT=Path(__file__).resolve().parents[2]
GROUPS={'METRICS':'model','RXQ':'queue','CANPROOF':'can','DELIVERY':'delivery'}


def observe(uart,seconds,private,initial=b''):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence=ROOT/'gateway/physical_can/evidence/h3'
    public=evidence/('uart-'+stamp+'.log')
    status_path=ROOT/'gateway/physical_can/build/h3-isolated/uart-status.json'
    control_path=status_path.with_name('uart-control.txt')
    consumed=0
    state={'state':'CAPTURING','stamp':stamp,'boot_wait_marker_seen':False,'boot_markers':0,
           'latest':{},'host_log':{'complete':0,'missing_reports':0,'missing_lines':0,'duplicate_lines':0,'invalid_tags':0},'reports':[]}
    report=None;previous=None;seen=set();pending=bytearray(initial);started=time.monotonic();saved=0
    with (private/('h3-uart-'+stamp+'.raw.log')).open('xb') as raw,public.open('x',encoding='utf-8') as log:
        raw.write(initial)
        while time.monotonic()-started<seconds:
            if control_path.exists():
                commands=control_path.read_text(encoding='utf-8').splitlines()
                for command in commands[consumed:]:
                    if command=='STOP':state['state']='CAPTURE_STOPPED'
                    elif command=='D' and state.get('mqtt_connected_seen') and not state['latest'].get('queue',{}).get('fault',1):
                        uart.write(b'D');state['disconnect_command_sent']=True
                    else:state['state']='UNKNOWN_OR_UNREADY_CONTROL_STOP'
                consumed=len(commands)
                if state['state']!='CAPTURING':break
            chunk=uart.read(min(max(uart.in_waiting,1),4096));raw.write(chunk);raw.flush();pending.extend(chunk)
            if len(pending)>16384:state['state']='HOST_LINE_BUFFER_OVERFLOW_STOP';break
            while b'\n' in pending:
                line,_,pending=pending.partition(b'\n');text=line.decode('ascii',errors='replace').rstrip('\r')
                if not text.startswith('GW '):continue
                # 仅固定格式的计数行/步骤名可公开，未知输出仅保留于受限原件。
                kind=text.split()[1] if len(text.split())>1 else ''
                if kind not in {*GROUPS,'DIAG_BEGIN','DIAG_END','BOOT','WAIT_NODE_A_FIRST_HEARTBEAT','OK','FAIL',
                                'AT_VERSION','SNTP_VALID','MQTT_CONNECTED','RECONNECT','CONFIG_REQUIRED',
                                'CAN_FAULT_NETWORK_CLOSED_STOP','WAIT_NODE_A_RX_FAULT_STOP',
                                'MQTT_ERROR','MQTT_PENDING','WIFI_SIGNAL','WIFI_SIGNAL_UNAVAILABLE','WIFI_SLEEP',
                                'READ_AVAILABLE_FAIL','READ_AVAILABLE_HEADER_FAIL',
                                'READ_AT_FAIL','READ_HEADER_FAIL','READ_LENGTH_FAIL',
                                'WRITE_PROMPT_FAIL','WRITE_SEND_FAIL'}:continue
                if not re.fullmatch(r'[A-Za-z0-9_=., /:-]+',text):continue
                fields=dict(re.findall(r'(\w+)=(-?[0-9.]+)',text))
                log.write(text+'\n');log.flush()
                if kind=='WAIT_NODE_A_FIRST_HEARTBEAT':state['boot_wait_marker_seen']=True
                if kind=='BOOT':state['boot_markers']+=1
                if kind=='DIAG_BEGIN':
                    seq=int(fields['seq'])
                    if fields.get('lines')!='4':state['host_log']['invalid_tags']+=1
                    if report is not None:state['host_log']['missing_lines']+=4-len(seen)
                    if previous is not None:
                        if seq<=previous:state['host_log']['invalid_tags']+=1
                        else:state['host_log']['missing_reports']+=seq-previous-1
                    report=seq;previous=seq;seen=set()
                elif kind in GROUPS:
                    state['latest'][GROUPS[kind]]={k:int(v) for k,v in fields.items()}
                    if kind in seen:state['host_log']['duplicate_lines']+=1
                    seen.add(kind)
                elif kind=='DIAG_END':
                    if fields.get('lines')!='4':state['host_log']['invalid_tags']+=1
                    if report is None or int(fields['seq'])!=report:state['host_log']['invalid_tags']+=1
                    elif seen==set(GROUPS):
                        state['host_log']['complete']+=1
                        state['reports'].append({'seq':report,'elapsed_s':round(time.monotonic()-started,3),
                            'utc':datetime.now(timezone.utc).isoformat(),'counters':json.loads(json.dumps(state['latest']))})
                    else:state['host_log']['missing_lines']+=4-len(seen)
                    report=None;seen=set()
                if kind=='SNTP_VALID':state['sntp']=fields
                if kind=='AT_VERSION':state['at_version']=fields.get('value')
                if kind in ('WIFI_SIGNAL','WIFI_SLEEP'):state[kind.lower()]=fields
                if kind=='MQTT_CONNECTED':state['mqtt_connected_seen']=True
                if kind in ('CAN_FAULT_NETWORK_CLOSED_STOP','WAIT_NODE_A_RX_FAULT_STOP'):state['state']='DEVICE_STOP'
                q=state['latest'].get('queue',{});can=state['latest'].get('can',{})
                if any(q.get(k,0) for k in ('fovr','sw','fault','stale')) or can.get('BOFF',0):state['state']='CAN_FAULT_STOP'
            state.update(elapsed_s=round(time.monotonic()-started,3),updated_utc=datetime.now(timezone.utc).isoformat())
            if time.monotonic()-saved>=.5 or state['state']!='CAPTURING':
                temp=status_path.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2),encoding='utf-8');temp.replace(status_path);saved=time.monotonic()
            if state['state']!='CAPTURING':break
    state['host_log']['trailing_partial_report']=report is not None
    if state['state']=='CAPTURING':state['state']='CAPTURE_COMPLETE'
    state['exit_code']=0 if state['state'] in ('CAPTURE_COMPLETE','CAPTURE_STOPPED') else 1
    (evidence/('uart-'+stamp+'-result.json')).write_text(json.dumps(state,indent=2),encoding='utf-8')
    status_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    return state['exit_code']
