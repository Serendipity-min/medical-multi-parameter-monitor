"""复用既有串口方式验证C-only TTS STOP；不加载SDK，不联网、不操作MIC/CAN。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'node-b/tools'))
from b4_recovery import protected


def stop_proof(events, state):
    tx = [(i, e['byte']) for i, e in enumerate(events) if e['kind'] == 'TX']
    if [b for _, b in tx] != [0xfd, 0, 1, 2, 0xfd, 0, 1, 0x21]:
        raise ValueError('STOP_QUERY_TX_SEQUENCE')
    acks = [i for i, e in enumerate(events) if e['kind'] == 'RX' and e['byte'] == 0x41]
    idle = [i for i, e in enumerate(events) if e['kind'] == 'RX' and e['byte'] == 0x4f]
    if not any(tx[3][0] < i < tx[4][0] for i in acks) or not any(i > tx[-1][0] for i in idle):
        raise ValueError('STOP_ACK_QUERY_IDLE_ORDER')
    if any(e['kind'] == 'RX' and e['byte'] in (0x45, 0x46) for e in events):
        raise ValueError('TTS_NATIVE_COMMAND_REJECTED')
    if any(state[k] != v for k, v in {'state':0, 'enabled':0, 'stopping':0, 'stop_sent':1,
            'stop_ack':1, 'query_sent':1, 'stop_idle':1, 'stop_failed':0,
            'uart_errors':0, 'uart_overflow':0}.items()):
        raise ValueError('STOP_FINAL_STATE_NOT_CONFIRMED')
    return {'status':'C_TTS_STOP_ACK_QUERY_IDLE_PASS_NOT_CONCURRENCY',
            'TTS_TX_bytes':8, 'STOP_packets':1, 'QUERY_packets':1,
            'final_state':state, 'events':events}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--playing',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print('TTS_STOP_FIELD_NOT_STARTED');return 0
    protected(a.out.parent,False);a.out.mkdir()
    (a.out/'executed-stop-field.py').write_bytes(Path(__file__).read_bytes())
    import serial
    s=serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=2)
    s.dtr=False;s.rts=False;s.port=a.port
    events=[];states=[];transcript=bytearray();commands=[];phrase_active=False;stop_attempted=False
    result={'exit_code':1,'scope':'C_ONLY_TTS_STOP','playing':a.playing,'SDK_opens':0,
            'Flash_writes':0,'MCU_RESET_commands':0,'network_operations':0,'hardware_concurrency':'NOT_RUN'}

    def send(command):
        n=s.write(command)
        commands.append({'monotonic_ns':time.monotonic_ns(),'command':command.decode('ascii'),'native_written':n})
        if n!=len(command):raise OSError('TTS_SERIAL_SHORT_WRITE')

    def line(deadline):
        data=bytearray()
        while time.monotonic()<deadline:
            b=s.read(1);data.extend(b);transcript.extend(b)
            if len(data)>4096:raise ValueError('TTS_SERIAL_LINE_BOUND')
            if b!=b'\n':continue
            text=data.decode('ascii').strip()
            if text.startswith('TTS_EVT '):
                parts=text.split();fields=dict(v.split('=') for v in parts[2:])
                events.append({'kind':parts[1],'ms':int(fields['ms']),'byte':int(fields['byte'],16)})
            elif text.startswith('TTS_STATE '):
                state={k:int(v) for k,v in (v.split('=') for v in text.split()[1:])};states.append(state)
                if state['stop_failed'] or state['uart_errors'] or state['uart_overflow']:
                    raise ValueError('TTS_NATIVE_STOP_OR_UART_ERROR')
            elif text.startswith('TTS_REJECT_'):raise ValueError(text)
            return text
        raise TimeoutError('TTS_SERIAL_PHASE_TIMEOUT')

    def until(predicate,seconds=5):
        deadline=time.monotonic()+seconds
        while True:
            text=line(deadline)
            if predicate(text):return

    def state_is(*values):
        return lambda text:text.startswith('TTS_STATE ') and states[-1]['state'] in values

    try:
        s.open();send(b'I')
        until(lambda t:t=='TTS_STOP_BENCH_ID V1 QUERY_AFTER_STOP_ACK NO_MIC_CAN_ESP')
        send(b'V');until(state_is(5))
        if a.playing:
            send(b'P');phrase_active=True;until(state_is(3,4))
            result['pre_stop_TTS_state']=states[-1]['state']
            result['playback_scope']='ACK_ACCEPTED_REQUIRES_OWNER_HEARING_NOT_4E_PROOF'
            time.sleep(.5)
        boundary=len(events);send(b'S');stop_attempted=True
        until(lambda t:t.startswith('TTS_STATE ') and states[-1]['state']==0 and states[-1]['stop_idle']==1 and states[-1]['stopping']==0)
        result.update(stop_proof(events[boundary:],states[-1]),exit_code=0)
    except (ValueError,TimeoutError,OSError,serial.SerialException) as error:
        result.update(error_type=type(error).__name__,reason=str(error))
    finally:
        # 仅在文本已启动但尚未尝试STOP时保全；失败的STOP不会被自动重发成PASS。
        if phrase_active and not stop_attempted and s.is_open:
            try:send(b'S');result['cleanup_STOP_attempted']=True
            except serial.SerialException:result['cleanup_STOP_failed']=True
        if s.is_open:s.close()
        (a.out/'serial-rx-private.bin').write_bytes(transcript)
        (a.out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        result.setdefault('events',events)
        result['observed_states']=states
        result['transcript_SHA256']=hashlib.sha256(transcript).hexdigest()
        (a.out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
