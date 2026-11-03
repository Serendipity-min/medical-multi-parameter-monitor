"""仅补取完整300秒窗口已STOP后的Q/D；保留原退出1，不重采、不重启。"""
import argparse
import json
from pathlib import Path
import sys
import time
import zlib

import b5_g3_contract as g

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gateway/microphone'))
sys.path.insert(0,str(ROOT/'cloud/microphone'))
from capture import analyze
from protocol import AudioAssembler


def boundary(job):
    run=g.load(job/'receipt-private.json');cap=next(job.glob('field-capture-*'))
    original=g.load(cap/'receipt.json');end=g.load(job/'capture/T0.json')['evaluation_UTC_ms'][1]
    g.require(run['exit_code']==1 and run.get('capture_native_exit')==1 and original.get('reason')=='FIELD_NETWORK_UNSYNCED_REQUIRES_COLD_BOOT','M0_RECOVERY_SPECIFIC_HOST_FAILURE_ONLY')
    for p in (job/'capture/B/receipt-private.json',job/'capture/cloud-receipt-private.json',job/'browser-receipt-public.json'):
        g.require(g.load(p)['exit_code']==0,'M0_RECOVERY_OTHER_WORKER_FAILED')
    rows=[json.loads(x) for x in (cap/'C-lines-private.jsonl').read_text(encoding='utf8').splitlines()]
    stop=next((i for i,x in enumerate(rows) if x['data']=='B5 STOPPED NO_AUTOREARM'),None)
    bad=next((i for i,x in enumerate(rows) if x['data']=='GW CLOSE_UNSYNCED_MANUAL_POWER_REQUIRED'),None)
    g.require(stop is not None and bad is not None and stop<bad and rows[stop]['UTC_ms']>=end,'M0_RECOVERY_COMPLETE_WINDOW_STOP_PRECEDES_UNSYNC')
    last=next(x['data'] for x in reversed(rows[:stop]) if x['data'].startswith('UNI AUDIO '))
    state={k:int(v) for k,v in (x.split('=') for x in last.split()[2:])}
    g.require(state['phase']==1 and state['chunk']==125 and state['tts_done'] and not state['failures'],'M0_RECOVERY_PRIOR_VOICE_INCOMPLETE')
    return cap,state


def complete(job,port):
    import serial
    cap,state=boundary(job);out=job/'stop-completion-recovery';g.private.protected(job,False);out.mkdir()
    (out/'executed-tool.py').write_bytes(Path(__file__).read_bytes())
    assembler=AudioAssembler(timeout_s=180);audio=None
    for text in (cap/'MQTT-observer-private.jsonl').read_text().splitlines():
        x=json.loads(text)
        if x['topic']=='mpm/mic/v1/in' and x['qos']==1 and not x['retain']:
            completed=assembler.feed('C',bytes.fromhex(x['payload_hex']),x['arrival_unix_ns']/1e9)
            if completed:audio=completed
    g.require(audio and audio['session']==state['session'] and audio['crc32']==state['crc'],'M0_RECOVERY_BROKER_IDENTITY')
    s=serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=2);s.dtr=False;s.rts=False;s.port=port
    rows=[]
    def line(seconds=5):
        deadline=time.monotonic()+seconds;data=bytearray()
        while time.monotonic()<deadline:
            c=s.read(1);data.extend(c)
            if c==b'\n':
                text=data.decode('ascii',errors='replace').strip();rows.append({'monotonic':time.monotonic(),'UTC_ms':int(time.time()*1000),'data':text});return text
            g.require(len(data)<32000,'M0_RECOVERY_LINE_BOUND')
        raise TimeoutError('M0_RECOVERY_SERIAL_TIMEOUT')
    try:
        s.open();s.write(b'IQ')
        while True:
            text=line()
            if text.startswith('UNI AUDIO '):break
        current={k:int(v) for k,v in (x.split('=') for x in text.split()[2:])}
        g.require(current['session']==state['session'] and current['crc']==state['crc'] and current['phase']==1 and all(current[k] for k in ('stop_ack','stop_query','stop_idle')) and not current['stop_failed'],'M0_RECOVERY_STOP_NOT_VERIFIED')
        s.write(b'D')
        while True:
            text=line()
            if text.startswith('{'):break
        meta=json.loads(text);g.require(meta['bytes']==64000,'M0_RECOVERY_PCM_SIZE')
        pcm=bytearray();deadline=time.monotonic()+15
        while len(pcm)<64000 and time.monotonic()<deadline:pcm.extend(s.read(min(4096,64000-len(pcm))))
        trailer=s.read(11);g.require(trailer==b'\r\nMIC_END\r\n','M0_RECOVERY_TRAILER')
        proof=analyze(meta,pcm);g.require(bytes(pcm)==audio['pcm'] and zlib.crc32(pcm)==state['crc'],'M0_RECOVERY_PCM_BROKER_MISMATCH')
    finally:
        s.close();(out/'C-lines-private.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf8')
    (out/'source-PCM-private.bin').write_bytes(pcm);g.save(out/'source-metadata-private.json',meta)
    result={'exit_code':0,'status':'M0_POST_STOP_COMPLETION_ONLY_ORIGINAL_CAPTURE_EXIT1_RETAINED','original_capture_native_exit':1,'commands':['I','Q','D'],'new_recording':False,'reset_commands':0,'STOP_ACK_query_IDLE':True,'session':state['session'],'broker_chunks':125,'source_proof':proof,'source_cloud_PCM_SHA256':audio['PCM_SHA256'],'last_TTS':current,'original_receipt_sha256':g.sha((cap/'receipt.json').read_bytes())}
    g.save(out/'receipt.json',result)
    merged=job/'capture/C-lines-private.jsonl'
    if not merged.exists():
        with merged.open('xb') as f:
            for path in sorted(job.glob('field-*/C-lines-private.jsonl')):f.write(path.read_bytes())
    print(json.dumps({'exit_code':0,'status':result['status'],'new_recording':False,'PCM_SHA256':audio['PCM_SHA256']}));return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--port',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    boundary(a.job)
    raise SystemExit(complete(a.job,a.port) if a.execute else 0)
