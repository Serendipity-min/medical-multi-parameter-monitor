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
    p.add_argument('--port',required=True);p.add_argument('--action',choices=('connect','capture','retry','stop'),required=True);a=p.parse_args()
    stamp=time.strftime('%Y%m%dT%H%M%S',time.gmtime());out=a.job/('field-'+a.action+'-'+stamp);out.mkdir()
    if not out.stat().st_file_attributes&0x4000:raise ValueError('FIELD_OUTPUT_NOT_EFS')
    (out/'executed-field-tool.py').write_bytes(Path(__file__).read_bytes())
    result={'exit_code':1,'action':a.action,'scope':'C_ONLY_VOICE_NETWORK','MCU_RESET_commands':0,
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
        s.open();s.write(b'I');identity=until(b'MIC_NETWORK_ID ',3)
        if identity.strip()!=b'MIC_NETWORK_ID PA4_PC10_PC12 TLS_PCM16_TTS_LOW_VOLUME WIFI_RAM_V4_STATE_SAFE':
            raise ValueError('FIELD_WRONG_RUNTIME_CONFIG_VERSION')
        if a.action=='connect':
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
            observe();s.write(b'R' if a.action=='capture' else b'U')
            until(b'MIC_NET RECORDING ' if a.action=='capture' else b'MIC_NET REUPLOAD_EXISTING_RECORD ',3)
            until(b'MIC_NET PLAYBACK_DONE_REQUIRES_OWNER_HEARING',125)
            last=events[-1]
            if last['ack']!=1 or last['done']!=1 or last['uart_errors'] or last['uart_overflow']:
                raise ValueError('FIELD_TTS_ACK_DONE_OR_UART')
            if 'pcm' not in source_audio or 'error' in source_audio or reply.get('session')!=session.get('id'):
                raise ValueError('FIELD_BROKER_SOURCE_OR_REPLY_MISSING')
            s.write(b'D');meta=json.loads(line(time.monotonic()+4));data=bytearray();deadline=time.monotonic()+15
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
        else:
            s.write(b'S');until(b'MIC_NET OWNER_STOP_STOP_ACK_NOT_ASSUMED',12)
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
