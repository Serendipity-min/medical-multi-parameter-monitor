"""隔离MQTT音频→受限CPU ASR→既有AI→独立语音回复；不修改正式服务。"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import wave

import paho.mqtt.client as mqtt
from protocol import AudioAssembler,reply_packet
from ai_reference.providers import Provider
from ai_reference import providers as ai_module

INPUT='mpm/mic/v1/in'
OUTPUT='mpm/mic/v1/out'
HOST_INPUT='mpm/mic/v1/hostcheck'
HOST_OUTPUT='mpm/mic/v1/hostreply'


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    base=a.base;runtime=base/'runs';runtime.mkdir(exist_ok=True,mode=0o700)
    settings=json.loads((base/'voice-runtime-credentials-private.json').read_text())
    os.environ['P6_REAL_BUDGET_DIR']=str(runtime/'model-usage');Path(os.environ['P6_REAL_BUDGET_DIR']).mkdir(exist_ok=True)
    os.environ.pop('CVOICE_MODEL_BUDGET_FILE',None)
    provider=Provider('DOUBAO')
    incoming=queue.Queue(maxsize=256);overflow=threading.Event();connected=threading.Event();subscribed=threading.Event()
    assembler=AudioAssembler();counts={'packets':0,'rejected':0,'completed_C':0,'completed_HOST':0,'queue_overflow':0}
    kwargs={'client_id':'mic-worker-20261102','protocol':mqtt.MQTTv311,'reconnect_on_failure':False}
    if hasattr(mqtt,'CallbackAPIVersion'):kwargs['callback_api_version']=mqtt.CallbackAPIVersion.VERSION2
    client=mqtt.Client(**kwargs);client.username_pw_set('mic-worker',settings['roles']['mic-worker'])

    def on_connect(c,u,flags,reason,properties=None):
        if reason==0:connected.set();c.subscribe([(INPUT,1),(HOST_INPUT,1)])
    def on_subscribe(c,u,mid,codes,properties=None):
        if len(codes)==2 and all(code==1 for code in codes):subscribed.set()
    def on_message(c,u,message):
        if message.topic not in (INPUT,HOST_INPUT) or message.qos!=1 or message.retain or len(message.payload)!=544:
            counts['rejected']+=1;return
        try:incoming.put_nowait((message.topic,bytes(message.payload),time.time_ns()))
        except queue.Full:overflow.set()
    client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_message=on_message
    client.connect('127.0.0.1',18885,keepalive=15);client.loop_start()
    if not connected.wait(5) or not subscribed.wait(5):raise RuntimeError('MIC_WORKER_MQTT_NOT_READY')
    save(base/'worker-ready.json',{'MQTT_connected':True,'exact_topics_subscribed':True,'ASR_model':'small-q5_1',
                                 'source_scopes_separate':True,'formal_service_config_changes':0})
    deadline=time.monotonic()+21600
    with (runtime/'mqtt-wire-private.jsonl').open('a',encoding='utf-8') as wire:
        try:
            while time.monotonic()<deadline and not (base/'STOP-WORKER').exists():
                if overflow.is_set():
                    assembler.active.clear();counts['queue_overflow']+=1
                    while not incoming.empty():incoming.get_nowait()
                    overflow.clear()
                try:topic,packet,arrival=incoming.get(timeout=.5)
                except queue.Empty:continue
                source='C' if topic==INPUT else 'HOST'
                counts['packets']+=1
                wire.write(json.dumps({'source':source,'arrival_unix_ns':arrival,'packet_SHA256':hashlib.sha256(packet).hexdigest()})+'\n');wire.flush()
                try:result=assembler.feed(source,packet)
                except ValueError as error:
                    counts['rejected']+=1;assembler.discard(source)
                    save(runtime/'last-protocol-rejection.json',{'reason':str(error),'counts':counts});continue
                if result is None:continue
                counts['completed_'+source]+=1;folder=runtime/(source+'-'+str(result['session']));folder.mkdir(mode=0o700)
                pcm=result.pop('pcm');wav=folder/'audio.wav'
                with wave.open(str(wav),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(pcm)
                result.update(scope='C_REAL_MIC_ASR' if source=='C' else 'HOST_BRIDGE_PROOF',counts=dict(counts),
                              actual_PCM_bytes=len(pcm),ASR_exit_code=None,AI_called=False,reply_published=False)
                save(folder/'receipt-private.json',result)
                prefix=folder/'asr';started=time.monotonic()
                with (folder/'asr-native-private.log').open('wb') as log:
                    run=subprocess.Popen(['/usr/bin/time','-v',str(base/'whisper-build/bin/whisper-cli'),
                                        '-m',str(base/'ggml-small-q5_1.bin'),'-f',str(wav),'-l','auto',
                                        '-t','1','-nt','-np','-oj','-of',str(prefix)],
                                       stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:native_exit=run.wait(timeout=90)
                    except subprocess.TimeoutExpired:
                        import signal
                        os.killpg(run.pid,signal.SIGKILL);native_exit=run.wait(timeout=5);result['ASR_timed_out']=True
                result.update(ASR_exit_code=native_exit,ASR_elapsed_s=time.monotonic()-started)
                text=(folder/'asr-native-private.log').read_text(errors='replace')
                rss=re.search(r'Maximum resident set size.*?:\s*(\d+)',text)
                result['ASR_peak_RSS_KiB']=int(rss[1]) if rss else None
                if native_exit:
                    result['status']='ASR_FAILED';save(folder/'receipt-private.json',result);continue
                raw=json.loads(prefix.with_suffix('.json').read_text())
                transcription=''.join(x['text'] for x in raw['transcription']).strip()
                result.update(ASR_text=transcription,ASR_language=raw.get('result',{}).get('language'))
                if not transcription or len(transcription)>200:
                    result['status']='ASR_NO_ACCEPTABLE_TEXT';save(folder/'receipt-private.json',result);continue
                try:
                    question=('非人体麦克风工程测试，识别片段：'+transcription+
                              '。请严格返回JSON对象，kind取project，explanation只用十个汉字以内简短确认收到。'
                              '不要复述识别片段，不含数字、单位、表情、换行、标签或医疗判断。')
                    result['AI_called']=True
                    original_validate=ai_module.validate_explanation
                    def audit_output(parsed):
                        save(folder/'AI-output-JSON-private.json',parsed)
                        return original_validate(parsed)
                    # 此worker串行调用AI，旁路仅留原件，仍由未改动的原校验器裁定。
                    ai_module.validate_explanation=audit_output
                    try:answer=asyncio.run(provider.explain(question,[],[]))
                    finally:ai_module.validate_explanation=original_validate
                    result.update(AI_text=str(answer),AI_evidence=dict(answer.evidence))
                    response=reply_packet(result['session'],result['crc32'],str(answer))
                except Exception as error:
                    result.update(status='AI_OR_TEXT_REJECTED',error_type=type(error).__name__)
                    if isinstance(error,ValueError) and str(error) in ('MODEL_OUTPUT_REJECTED','MODEL_RESPONSE_INCOMPLETE','MODEL_RESPONSE_SIZE'):
                        result['error_code']=str(error)
                    if provider.last_call:result['AI_evidence']=dict(provider.last_call)
                    save(folder/'receipt-private.json',result);continue
                publication=client.publish(OUTPUT if source=='C' else HOST_OUTPUT,response,qos=1,retain=False)
                publication.wait_for_publish(timeout=5)
                result.update(reply_published=publication.is_published(),actual_reply_bytes=len(response),
                              status='C_ASR_AI_REPLY_PUBACK_NOT_TTS_PROOF' if source=='C' else 'HOST_BRIDGE_PROOF')
                save(folder/'receipt-private.json',result)
                print(json.dumps({'source':source,'session':result['session'],'status':result['status'],
                                  'reply_published':result['reply_published']}),flush=True)
        finally:
            client.disconnect();client.loop_stop();save(base/'worker-exit.json',{'counts':counts,'closed':True})


if __name__=='__main__':main()
