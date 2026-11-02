"""已验收WAV经独立Host主题验证隔离ASR/AI；不发送到C主题，不操作设备。"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
import wave
import zlib

import paho.mqtt.client as mqtt
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'cloud/microphone'))
from protocol import HEADER


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);a=p.parse_args()
    job=a.job;settings=json.loads((job/'voice-runtime-credentials-private.json').read_text())
    with wave.open(str(job/'speech-5-phone-continuous/audio.wav'),'rb') as w:
        if w.getparams()[:3]!=(1,2,16000):raise ValueError('HOST_REFERENCE_FORMAT')
        pcm=w.readframes(w.getnframes())
    if len(pcm)!=64000:raise ValueError('HOST_REFERENCE_LENGTH')
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    connected=threading.Event();subscribed=threading.Event();replied=threading.Event();response={}
    session=int(time.time());crc=zlib.crc32(pcm);result={'scope':'HOST_BRIDGE_PROOF_ONLY_NOT_C_UPLINK','exit_code':1,
        'session':session,'PCM_SHA256':hashlib.sha256(pcm).hexdigest(),'C_topic_publications':0}
    kwargs={'client_id':'mic-host-bridge-20261102','protocol':mqtt.MQTTv311,'reconnect_on_failure':False}
    if hasattr(mqtt,'CallbackAPIVersion'):kwargs['callback_api_version']=mqtt.CallbackAPIVersion.VERSION2
    client=mqtt.Client(**kwargs);client.username_pw_set('mic-observer',settings['roles']['mic-observer'])
    def on_connect(c,u,f,reason,props=None):
        if reason==0:connected.set();c.subscribe('mpm/mic/v1/hostreply',1)
    def on_subscribe(c,u,mid,codes,props=None):
        if len(codes)==1 and codes[0]==1:subscribed.set()
    def on_message(c,u,message):
        raw=bytes(message.payload)
        if message.topic!='mpm/mic/v1/hostreply' or message.qos!=1 or message.retain or len(raw)<17:return
        magic,seen,checksum,length,flags=struct.unpack_from('<4sIIHH',raw)
        if magic==b'MR01' and seen==session and checksum==crc and 16+length==len(raw) and flags==0:
            response['actual_AI_text']=raw[16:].decode('utf-8');replied.set()
    client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_message=on_message
    with (job/'host-probe-tunnel-private.log').open('xb') as log:
        tunnel=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ExitOnForwardFailure=yes',
              '-o','ConnectTimeout=10','-N','-L',f'127.0.0.1:{port}:127.0.0.1:18885','tencent-codex'],
              stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        try:
            time.sleep(2)
            if tunnel.poll() is not None:raise RuntimeError('HOST_TUNNEL_FAILED')
            client.connect('127.0.0.1',port,15);client.loop_start()
            if not connected.wait(5) or not subscribed.wait(5):raise RuntimeError('HOST_MQTT_NOT_READY')
            for seq in range(125):
                data=pcm[seq*512:(seq+1)*512]
                packet=HEADER.pack(b'MC01',session,seq,125,16000,64000,crc,zlib.crc32(data),512,
                                   (1 if seq==0 else 0)|(2 if seq==124 else 0),1)+data
                sent=client.publish('mpm/mic/v1/hostcheck',packet,qos=1,retain=False);sent.wait_for_publish(timeout=5)
                if not sent.is_published():raise RuntimeError('HOST_PUBACK_MISSING')
            result['actual_HOST_chunks_PUBACK']=125
            if not replied.wait(120):raise TimeoutError('HOST_ASR_AI_REPLY_NOT_RECEIVED')
            result.update(response,exit_code=0)
        except (OSError,RuntimeError,TimeoutError,ValueError) as error:
            result.update(error_type=type(error).__name__)
        finally:
            client.disconnect();client.loop_stop();tunnel.terminate();result['own_tunnel_native_exit']=tunnel.wait(timeout=5)
    (job/'HOST-BRIDGE-ASR-AI-public.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
