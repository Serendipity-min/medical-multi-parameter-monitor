"""独立五板录音事实worker候选；仅显式ISOLATED启动，默认导入不连接网络。"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import uuid
import wave

import httpx
import paho.mqtt.client as mqtt
from .app import create_app, Settings
from .appliance_audio import AudioFactFlow
from .appliance_reply import RecordingReplyAdapter, GATEWAY
from .downlink import IsolatedPublisher


async def whisper_pcm(pcm, rate, binary, model, runtime):
    with tempfile.TemporaryDirectory(prefix='five-audio-',dir=runtime) as folder:
        wav=Path(folder)/'input.wav';prefix=Path(folder)/'asr'
        with wave.open(str(wav),'wb') as out:
            out.setparams((1,2,rate,0,'NONE','not compressed'));out.writeframes(pcm)
        process=await asyncio.create_subprocess_exec(str(binary),'-m',str(model),'-f',str(wav),
                  '-l','auto','-t','1','-nt','-np','-oj','-of',str(prefix),
                  stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        try:
            code=await process.wait()
        finally:
            if process.returncode is None:
                process.kill();await process.wait()
        if code:
            raise RuntimeError(f'ASR_EXIT_{code}')
        data=json.loads(prefix.with_suffix('.json').read_text(encoding='utf-8'))
        return ''.join(item['text'] for item in data['transcription']).strip()


def fact_flow(replies, transcribe, app):
    async def ask(question):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://isolated-asgi') as client:
            response=await client.post('/api/v1/text',headers={'Authorization':'Bearer '+app.state.worker_token},
                json=dict(session_id=uuid.uuid4().hex,gateway_id=GATEWAY,question=question,voice=True))
            if response.status_code!=200:
                raise RuntimeError(f'FACT_API_HTTP_{response.status_code}')
            return response.json()
    return AudioFactFlow(replies,transcribe,ask)


async def run(args):
    if os.environ.get('P6_MQTT_MODE')!='ISOLATED':
        raise ValueError('ISOLATED_WORKER_NOT_ENABLED')
    port=int(os.environ['P6_MQTT_PORT']);user=os.environ['P6_MQTT_USERNAME'];password=os.environ['P6_MQTT_PASSWORD']
    publisher=IsolatedPublisher(port,user,password)
    async def send(topic,payload): await asyncio.to_thread(publisher._send,topic,payload)
    replies=RecordingReplyAdapter(send);settings=Settings.from_env()
    app=create_app(settings,publisher=replies);app.state.worker_token=settings.token
    async def transcribe(pcm,rate):return await whisper_pcm(pcm,rate,args.asr_bin,args.asr_model,args.runtime)
    flow=fact_flow(replies,transcribe,app)
    incoming=queue.Queue(maxsize=256);ready=threading.Event();overflow=threading.Event()
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='five-audio-facts',protocol=mqtt.MQTTv311)
    client.connect_timeout=2;client.username_pw_set(user,password);client.max_inflight_messages_set(1)
    client.reconnect_delay_set(2,30)
    def connected(c,_u,_f,reason,_p):
        if not reason.is_failure:c.subscribe('mpm/mic/v1/in',1)
    def subscribed(_c,_u,_mid,codes,_p):
        if len(codes)==1 and codes[0].value==1:ready.set()
    def message(_c,_u,m):
        if m.topic!='mpm/mic/v1/in' or m.qos!=1 or m.retain or len(m.payload)!=544:return
        try:incoming.put_nowait(bytes(m.payload))
        except queue.Full:overflow.set()
    client.on_connect=connected;client.on_subscribe=subscribed;client.on_message=message
    await asyncio.to_thread(client.connect,'127.0.0.1',port,15);client.loop_start()
    try:
        if not await asyncio.to_thread(ready.wait,5):raise RuntimeError('AUDIO_SUBSCRIPTION_NOT_READY')
        while True:
            if overflow.is_set():
                replies.assembler.discard('C');replies.recording=None
                while not incoming.empty():incoming.get_nowait()
                overflow.clear();print('FIVE_AUDIO_QUEUE_OVERFLOW_SESSION_DISCARDED',flush=True)
            try:packet=await asyncio.to_thread(incoming.get,True,.5)
            except queue.Empty:continue
            try:
                result=await flow.feed('mpm/mic/v1/in',packet)
                if result is not None:print('FIVE_AUDIO '+result['voice_status'],flush=True)
            except (ValueError,RuntimeError,TimeoutError,KeyError,TypeError,json.JSONDecodeError):
                replies.assembler.discard('C');replies.recording=None
                # 只输出固定状态，不泄露ASR文本、凭据、WSS地址或原生异常正文。
                print('FIVE_AUDIO_TURN_REJECTED',flush=True)
    finally:
        client.disconnect();client.loop_stop()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asr-bin',type=Path,required=True);p.add_argument('--asr-model',type=Path,required=True)
    p.add_argument('--runtime',type=Path,required=True);args=p.parse_args()
    if not args.asr_bin.is_file() or not args.asr_model.is_file() or not args.runtime.is_dir():
        p.error('existing ASR binary/model and restricted runtime directory are required')
    if args.runtime.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        p.error('private audio runtime must be outside the repository')
    asyncio.run(run(args))


if __name__=='__main__':main()
