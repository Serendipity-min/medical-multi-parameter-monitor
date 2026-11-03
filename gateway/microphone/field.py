"""C-only语音台架现场入口：不签PI、不使用nonce；纯观察MQTT、真实串口命令与源PCM对账。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import wave
import zlib

import paho.mqtt.client as mqtt
import serial
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'cloud/microphone'))
from protocol import AudioAssembler
sys.path.insert(0,str(Path(__file__).parent))
from capture import analyze


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True)
    p.add_argument('--unified',action='store_true',help='当前唯一C运行入口；保留B5新鲜SNTP，不设置UTC');p.add_argument('--port',required=True);p.add_argument('--action',choices=('connect','capture','retry','stop','load','fault','finish'),required=True);a=p.parse_args()
    if not a.unified and a.action in ('load','fault','finish'):p.error('该动作需要--unified')
    if a.unified and a.action=='retry':p.error('统一入口不支持旧U重传命令')
    stamp=time.strftime('%Y%m%dT%H%M%S',time.gmtime());out=a.job/('field-'+a.action+'-'+stamp);out.mkdir()
    if not out.stat().st_file_attributes&0x4000:raise ValueError('FIELD_OUTPUT_NOT_EFS')
    (out/'executed-field-tool.py').write_bytes(Path(__file__).read_bytes())
    result={'exit_code':1,'action':a.action,'scope':'C_UNIFIED_RUNTIME' if a.unified else 'C_ONLY_VOICE_NETWORK','MCU_RESET_commands':0,
            'B5START':0,'host_MQTT_application_publications':0,'formal_PI_signature_or_nonce_used':False}
    stream=(out/'serial-rx-private.bin').open('xb');events=[];tunnel=None;client=None;log=None;wire=None
    session={};source_audio={};reply={};observer_ready=threading.Event();assembler=AudioAssembler()
    s=serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=2);s.dtr=False;s.rts=False;s.port=a.port

    def line(deadline):
        data=bytearray()
        while time.monotonic()<deadline:
            c=s.read(1);data.extend(c);stream.write(c)
            if c==b'\n':stream.flush();return bytes(data)
            if len(data)>32000:raise ValueError('FIELD_SERIAL_LINE_BOUND')
        raise TimeoutError('FIELD_SERIAL_TIMEOUT')
    def until(prefix,seconds):
        deadline=time.monotonic()+seconds
        while True:
            b=line(deadline);text=b.decode('ascii',errors='replace').strip()
            if a.unified and text.startswith('UNI AUDIO '):
                event={k:int(v) for k,v in (x.split('=') for x in text.split()[2:])}
                event['event']='UNI_PHASE_'+str(event['phase']);events.append(event)
                with (out/'C-events-live.jsonl').open('a',encoding='utf-8') as live:live.write(json.dumps(event)+'\n')
                if event.get('session'):session['id']=event['session']
                print(json.dumps({'C_phase':event['phase'],'session':event['session'],'chunk':event['chunk']}),flush=True)
                if event['phase']==8 or event['stop_failed'] or event['tts_uart'] or event['tts_overflow']:
                    raise ValueError('FIELD_UNIFIED_AUDIO_FAILED')
            if text.startswith('MIC_NET '):
                pieces=text.split();event={'event':pieces[1],**{k:int(v) for k,v in (x.split('=') for x in pieces[2:])}}
                events.append(event)
                with (out/'C-events-live.jsonl').open('a',encoding='utf-8') as live:live.write(json.dumps(event)+'\n')
                print(json.dumps({'C_event':event['event'],'session':event['session'],'chunk':event['chunk']}),flush=True)
                if event['event'] in ('RECORDING','REUPLOAD_EXISTING_RECORD'):session['id']=event['session']
                if event['event'] in ('CONNECT_FAILED','TTS_FAILED','CAPTURE_FAILED','UPLOAD_FAILED','NETWORK_FAILED','TURN_TIMEOUT'):
                    raise ValueError('FIELD_'+event['event'])
            if b.startswith(prefix):return b
    def observe():
        nonlocal tunnel,client,log,wire
        with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
        log=(out/'own-ssh-tunnel-private.log').open('xb');wire=(out/'MQTT-observer-private.jsonl').open('x',encoding='utf-8')
        tunnel=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ExitOnForwardFailure=yes',
                    '-o','ConnectTimeout=10','-N','-L',f'127.0.0.1:{port}:127.0.0.1:18885','tencent-codex'],
                    stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        time.sleep(2)
        if tunnel.poll() is not None:raise RuntimeError('FIELD_OBSERVER_TUNNEL_FAILED')
        settings=json.loads((a.job/'voice-runtime-credentials-private.json').read_text())
        kwargs={'client_id':'mic-field-observer-'+stamp,'protocol':mqtt.MQTTv311,'reconnect_on_failure':False}
        if hasattr(mqtt,'CallbackAPIVersion'):kwargs['callback_api_version']=mqtt.CallbackAPIVersion.VERSION2
        client=mqtt.Client(**kwargs);client.username_pw_set('mic-observer',settings['roles']['mic-observer'])
        def on_connect(c,u,f,reason,props=None):
            if reason==0:c.subscribe([('mpm/mic/v1/in',1),('mpm/mic/v1/out',1)])
        def on_subscribe(c,u,mid,codes,props=None):
            if len(codes)==2 and all(code==1 for code in codes):observer_ready.set()
        def on_message(c,u,m):
            b=bytes(m.payload);wire.write(json.dumps({'topic':m.topic,'qos':m.qos,'retain':m.retain,
                'arrival_unix_ns':time.time_ns(),'payload_hex':b.hex()})+'\n');wire.flush()
            if m.qos!=1 or m.retain:return
            if m.topic=='mpm/mic/v1/in':
                try:completed=assembler.feed('C',b)
                except ValueError as error:source_audio['error']=str(error);return
                if completed:source_audio.update(completed)
            elif m.topic=='mpm/mic/v1/out' and len(b)>=17:
                magic,seen,crc,length,flags=struct.unpack_from('<4sIIHH',b)
                if magic==b'MR01' and seen==session.get('id') and length+16==len(b) and flags==0:
                    reply.update(session=seen,crc32=crc,text=b[16:].decode('utf-8'))
        client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_message=on_message
        client.connect('127.0.0.1',port,15);client.loop_start()
        if not observer_ready.wait(7):raise RuntimeError('FIELD_OBSERVER_NOT_READY')

    try:
        s.open();s.write(b'I');identity=until(b'UNI ID ' if a.unified else b'MIC_NETWORK_ID ',3)
        if identity.strip()!=(b'UNI ID V1 DUAL_CAN_MIC_MQTT_TTS CONFIG_RAM' if a.unified else b'MIC_NETWORK_ID PA4_PC10_PC12 TLS_PCM16_TTS_LOW_VOLUME WIFI_RAM_V4_STATE_SAFE'):
            raise ValueError('FIELD_WRONG_RUNTIME_CONFIG_VERSION')
        if a.unified and a.action=='connect':
            settings=json.loads((a.job/'voice-runtime-credentials-private.json').read_text())
            wifi=json.loads((a.job/'host-hotspot-runtime-private.json').read_text())
            fields=[b'b5-gateway',settings['roles']['b5-gateway'].encode('ascii'),b'b5-c-isolated',
                    wifi['ssid'].encode('utf-8'),wifi['wifi_password'].encode('utf-8')]
            sizes=[33,65,41,33,65]
            if any(not x or len(x)>=n for x,n in zip(fields,sizes)):raise ValueError('FIELD_UNIFIED_CONFIG_LENGTH')
            body=b'MCF3'+b''.join(x.ljust(n,b'\0') for x,n in zip(fields,sizes))+struct.pack('<I',int(time.time()))
            s.write(b'F'+body+struct.pack('<I',zlib.crc32(body)));until(b'UNI CONFIG_OK',3)
            s.write(b'UNISTART C\n');deadline=time.monotonic()+160;ready=False
            while time.monotonic()<deadline:
                s.write(b'Q')
                try:until(b'UNI AUDIO ',3)
                except TimeoutError:continue
                e=events[-1]
                if e['phase']==1 and e['online'] and e['subscribed'] and e['tts_ack']>=1:ready=True;break
            if not ready:raise TimeoutError('FIELD_UNIFIED_CONNECT_NOT_READY')
            result.update(exit_code=0,status='C_UNIFIED_TLS_SUBACK_TTS_READY_NOT_AUDIO_PASS',
                          UTC_setting_commands=0,time_policy='B5_FRESH_SNTP_UNCHANGED',last_state=events[-1])
        elif a.action=='connect':
            s.write(b'S');until(b'MIC_NET OWNER_STOP_STOP_ACK_NOT_ASSUMED',12);until(b'MIC_CONTROL_READY',3)
            settings=json.loads((a.job/'voice-runtime-credentials-private.json').read_text())
            user=b'mic-device';password=settings['roles']['mic-device'].encode('ascii');cid=('mic-c-'+stamp).encode('ascii')
            wifi=json.loads((a.job/'host-hotspot-runtime-private.json').read_text())
            ssid=wifi['ssid'].encode('utf-8');wifi_password=wifi['wifi_password'].encode('utf-8')
            if not 1<=len(ssid)<=32 or not 8<=len(wifi_password)<=64:raise ValueError('FIELD_WIFI_LENGTH')
            code="import json,time,subprocess\ns=subprocess.run(['timedatectl','show','-p','NTPSynchronized','--value'],capture_output=True,text=True,timeout=3)\nprint(json.dumps({'unix_ms':time.time_ns()//1000000,'NTP_synced':s.returncode==0 and s.stdout.strip()=='yes'}))\n"
            utc_at=time.monotonic_ns()
            utc_run=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','tencent-codex','python3','-'],
                                   input=code.encode(),capture_output=True,timeout=15)
            utc_elapsed=(time.monotonic_ns()-utc_at)//1000000
            (out/'UTC-native-stdout-private.json').write_bytes(utc_run.stdout)
            (out/'UTC-native-stderr-private.txt').write_bytes(utc_run.stderr)
            if utc_run.returncode:raise RuntimeError('FIELD_UTC_SSH_FAILED')
            utc=json.loads(utc_run.stdout)
            if not utc['NTP_synced'] or utc_elapsed>5000:raise ValueError('FIELD_UTC_SOURCE_OR_LATENCY')
            result.update(UTC_source='SSH_AUTHENTICATED_NTP_SYNCED_SERVER',UTC_query_native_exit=utc_run.returncode,
                          UTC_query_roundtrip_ms=utc_elapsed,UTC_source_unix_ms=utc['unix_ms'],UTC_quantization_ms=1000)
            body=b'MCF3'+user.ljust(33,b'\0')+password.ljust(65,b'\0')+cid.ljust(41,b'\0')+ssid.ljust(33,b'\0')+wifi_password.ljust(65,b'\0')+struct.pack('<I',utc['unix_ms']//1000)
            if len(body)!=245:raise ValueError('FIELD_RUNTIME_CONFIG_LENGTH')
            s.write(b'C'+body+struct.pack('<I',zlib.crc32(body)));until(b'MIC_CONFIG_OK',3)
            s.write(b'N');until(b'MIC_VOICE_READY',140)
            result.update(exit_code=0,status='C_TLS_MQTT_SUBACK_TTS_VOLUME_ACK_READY_NOT_AUDIO_UPLINK',
                          connect_cleanup_STOP_ACK_and_IDLE_proven=any(e['event']=='STOP_ACK_IDLE_CONFIRMED' for e in events))
        elif a.action in ('capture','retry'):
            observe()
            if a.unified:
                s.write(b'Q');until(b'UNI AUDIO ',3)
                baseline_failures=events[-1]['failures'];baseline_done=events[-1]['tts_done']
            s.write(b'R' if a.action=='capture' else b'U')
            until(b'UNI RECORDING' if a.unified else b'MIC_NET RECORDING ' if a.action=='capture' else b'MIC_NET REUPLOAD_EXISTING_RECORD ',3)
            if a.unified:
                deadline=time.monotonic()+125
                while True:
                    until(b'UNI AUDIO ',max(.1,deadline-time.monotonic()));last=events[-1]
                    if last['failures']>baseline_failures:raise ValueError('FIELD_UNIFIED_CAPTURE_FAILED')
                    if last['phase']==1 and last['tts_done']>baseline_done:break
                    if time.monotonic()>=deadline:raise TimeoutError('FIELD_UNIFIED_TURN_TIMEOUT')
                last=dict(last,ack=last['tts_ack'],done=last['tts_done'],uart_errors=last['tts_uart'],uart_overflow=last['tts_overflow'])
            else:until(b'MIC_NET PLAYBACK_DONE_REQUIRES_OWNER_HEARING',125);last=events[-1]
            counts_bad=(last['ack']<1 or last['done']<1) if a.unified else (last['ack']!=1 or last['done']!=1)
            if counts_bad or last['uart_errors'] or last['uart_overflow']:
                raise ValueError('FIELD_TTS_ACK_DONE_OR_UART')
            if 'pcm' not in source_audio or 'error' in source_audio or reply.get('session')!=session.get('id'):
                raise ValueError('FIELD_BROKER_SOURCE_OR_REPLY_MISSING')
            if a.unified:
                s.write(b'X');until(b'B5 STOPPED NO_AUTOREARM',5)
                deadline=time.monotonic()+4
                while True:
                    until(b'UNI AUDIO ',max(.1,deadline-time.monotonic()))
                    if events[-1]['stop_ack'] and events[-1]['stop_query'] and events[-1]['stop_idle']:break
                result['STOP_ACK_query_IDLE']=True
            s.write(b'D')
            while True:
                b=line(time.monotonic()+4)
                if b.startswith(b'{'):break
            meta=json.loads(b);data=bytearray();deadline=time.monotonic()+15
            if meta['bytes']!=64000:raise ValueError('FIELD_SOURCE_LENGTH')
            while len(data)<64000 and time.monotonic()<deadline:
                b=s.read(min(4096,64000-len(data)));data.extend(b);stream.write(b)
            trailer=bytearray()
            while len(trailer)<11 and time.monotonic()<deadline:
                b=s.read(11-len(trailer));trailer.extend(b);stream.write(b)
            if trailer!=b'\r\nMIC_END\r\n':raise ValueError('FIELD_SOURCE_TRAILER')
            proof=analyze(meta,data)
            if bytes(data)!=source_audio['pcm'] or reply['crc32']!=zlib.crc32(data):raise ValueError('FIELD_SOURCE_CLOUD_BYTES_MISMATCH')
            (out/'source-PCM-private.bin').write_bytes(data)
            (out/'source-metadata-private.json').write_text(json.dumps(meta,indent=2)+'\n')
            with wave.open(str(out/'source-audio.wav'),'wb') as wav:wav.setparams((1,2,16000,0,'NONE','not compressed'));wav.writeframes(data)
            result.update(exit_code=0,status='C_AUDIO_BROKER_BYTE_MATCH_AND_TTS_ACK_DONE_PENDING_ASR_REVIEW_OWNER_HEARING',
                          session=session['id'],source_proof=proof,broker_chunks=source_audio['chunks'],
                          source_cloud_PCM_SHA256=source_audio['PCM_SHA256'],actual_reply=reply,last_TTS=last)
        elif a.unified and a.action=='finish':
            s.write(b'X');until(b'B5 STOPPED NO_AUTOREARM',6);deadline=time.monotonic()+5
            while True:
                until(b'UNI AUDIO ',max(.1,deadline-time.monotonic()))
                e=events[-1]
                if e['stop_ack'] and e['stop_query'] and e['stop_idle']:break
            result.update(exit_code=0,status='C_GLOBAL_STOP_ACK_QUERY_IDLE_VERIFIED_NO_REARM',last_state=e)
        elif a.unified and a.action=='load':
            s.write(b'L');until(b'UNI C_ONLY_SOFTWARE_REPLAY_ON',3)
            result.update(exit_code=0,status='C_ONLY_SOFTWARE_CAN_REPLAY_ENABLED_NOT_PHYSICAL_CAN_PASS',
                          synthetic_input='INVALID_PDO_ANCHOR_QUALITY_ONLY_NO_MEASUREMENTS')
        elif a.unified and a.action=='fault':
            # 只暂停本任务透传进程；finally必定恢复，不触及正式服务或热点。
            unit='mpm-unified-c-ingress-20261103';suspended=False;native=[]
            def signal(sig):
                run=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','tencent-codex',
                    'sudo','-n','systemctl','kill','--kill-whom=main','--signal='+sig,unit],capture_output=True,timeout=15)
                native.append({'signal':sig,'native_exit':run.returncode})
                (out/('own-ingress-'+sig+'-private.log')).write_bytes(run.stdout+run.stderr)
                if run.returncode:raise RuntimeError('FIELD_OWN_INGRESS_SIGNAL_FAILED')
            observe();s.write(b'R');until(b'UNI RECORDING',3)
            deadline=time.monotonic()+25
            while True:
                until(b'UNI AUDIO ',max(.1,deadline-time.monotonic()))
                if events[-1]['phase']==4 and 5<=events[-1]['chunk']<125:break
            try:
                suspended=True;signal('STOP');s.write(b'S');deadline=time.monotonic()+8
                result['STOP_ACK_query_IDLE_observed_during_stall']=False
                while time.monotonic()<deadline:
                    s.write(b'Q')
                    try:until(b'UNI AUDIO ',min(1,max(.1,deadline-time.monotonic())))
                    except TimeoutError:continue
                    e=events[-1]
                    if e['phase']==1 and e['session']==session['id'] and e['stop_ack'] and e['stop_query'] and e['stop_idle']:
                        result['STOP_ACK_query_IDLE_observed_during_stall']=True
            finally:
                if suspended:signal('CONT')
                result['own_ingress_signals']=native
            deadline=time.monotonic()+160
            while time.monotonic()<deadline:
                s.write(b'Q')
                try:until(b'UNI AUDIO ',3)
                except TimeoutError:continue
                e=events[-1]
                if e['phase']==1 and e['online'] and e['subscribed']:break
            else:raise TimeoutError('FIELD_UNIFIED_RECOVERY_NOT_READY')
            if not(e['stop_ack'] and e['stop_query'] and e['stop_idle']):raise ValueError('FIELD_FAULT_STOP_NOT_LATCHED')
            if 'pcm' in source_audio or reply:raise ValueError('FIELD_FAULT_UNEXPECTED_COMPLETED_OR_REPLIED_AUDIO')
            result.update(exit_code=0,status='C_UNIFIED_INGRESS_STALL_STOP_AND_FRESH_RECONNECT_OBSERVED',
                          fault='OWN_INGRESS_PROCESS_SUSPEND_REAL_TCP_ACK_STALL_NOT_WIFI_POWER_OFF',last_state=e,
                          previous_active_session=session['id'],incomplete_audio_expected=True)
        else:
            s.write(b'S');stop_proven=False
            if a.unified:
                deadline=time.monotonic()+4
                while time.monotonic()<deadline:
                    until(b'UNI AUDIO ',max(.1,deadline-time.monotonic()))
                    if events[-1]['stop_ack'] and events[-1]['stop_query'] and events[-1]['stop_idle']:stop_proven=True;break
            else:
                until(b'MIC_NET OWNER_STOP_STOP_ACK_NOT_ASSUMED',12)
                try:until(b'MIC_NET STOP_ACK_IDLE_CONFIRMED',3);stop_proven=True
                except TimeoutError:stop_proven=False
            result.update(exit_code=0,status='STOP_ATTEMPT_COMPLETED',STOP_ACK_and_IDLE_proven=stop_proven)
    except (OSError,RuntimeError,TimeoutError,ValueError,serial.SerialException) as error:
        result.update(error_type=type(error).__name__,reason=str(error) if isinstance(error,(ValueError,TimeoutError,RuntimeError)) else 'NATIVE_IO_ERROR')
    finally:
        if s.is_open:s.close()
        stream.close()
        if client:client.disconnect();client.loop_stop()
        if wire:wire.close()
        if tunnel:tunnel.terminate();result['own_tunnel_native_exit']=tunnel.wait(timeout=5)
        if log:log.close()
        (out/'C-events.json').write_text(json.dumps(events,indent=2)+'\n')
        (out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (a.job/'latest-field-pointer.json').write_text(json.dumps({'out':str(out)})+'\n')
    print(json.dumps({'out':str(out),**result},ensure_ascii=False,indent=2));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
