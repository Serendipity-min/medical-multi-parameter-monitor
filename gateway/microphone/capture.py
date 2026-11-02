"""单次2秒MIC台架串口导出；录完后传输，默认不打开设备。"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import wave
import zlib


def analyze(meta, pcm):
    if meta['state'] != 2 or meta['frames'] != 32000 or meta['rate'] != 16000:
        raise ValueError('MIC_INCOMPLETE_CAPTURE')
    if len(pcm) != meta['bytes'] or len(pcm) != 64000 or zlib.crc32(pcm) != meta['crc32']:
        raise ValueError('MIC_LENGTH_OR_CRC')
    if meta['dma_errors'] or meta['overruns'] or meta['fault_flags'] or meta['blocks'] != 250:
        raise ValueError('MIC_CAPTURE_FAULT')
    pll, audio, divider, config = (meta[k] for k in ('PLLCFGR','PLLI2SCFGR','I2SPR','I2SCFGR'))
    if ((pll & 63) != 8 or not pll & (1 << 22) or (audio >> 6) & 511 != 256 or
        (audio >> 28) & 7 != 5 or divider != 25 or config != 0xb03 or meta['cpu_hz'] != 8000000):
        raise ValueError('MIC_CLOCK_OR_FORMAT_REGISTERS')
    ticks = meta['irq_cycles']
    if len(ticks) != 250: raise ValueError('MIC_IRQ_COUNT')
    if meta['recorded_blocks'] != list(range(51,251)):
        raise ValueError('MIC_RECORDED_BLOCK_DISCONTINUITY')
    gaps = [((b-a) & 0xffffffff)/meta['cpu_hz'] for a,b in zip(ticks,ticks[1:])]
    elapsed = ((ticks[249]-ticks[49]) & 0xffffffff)/meta['cpu_hz']
    rate = 32000/elapsed
    if not 15840 <= rate <= 16160 or min(gaps) <= 0 or max(gaps) >= .02:
        raise ValueError('MIC_IRQ_TIMING')
    values = array.array('h',pcm)
    if sys.byteorder != 'little': values.byteswap()
    rms = math.sqrt(sum(v*v for v in values)/len(values))
    mean = sum(values)/len(values); peak = max(abs(v) for v in values)
    if meta['left_abs'] == 0 or meta['right_abs'] >= meta['left_abs'] or meta['zero24'] > 31360:
        raise ValueError('MIC_LEFT_SLOT_ABSENT_OR_WRONG_CHANNEL')
    return {'status':'MIC_RECORD_INTEGRITY_PASS_NOT_FULL_LOCAL_ACCEPTANCE',
            'duration_s':len(values)/16000,'RMS_PCM16':rms,'mean_PCM16':mean,'peak_PCM16':peak,
            'RMS_dBFS':20*math.log10(rms/32768) if rms else None,
            'IRQ_rate_from_declared_HSE_Hz':rate,'IRQ_gap_min_s':min(gaps),'IRQ_gap_max_s':max(gaps),
            'clock_measurement':'REGISTER_AND_CYCLE_EVIDENCE_NOT_INDEPENDENT_FREQUENCY_METER',
            'zero24_fraction':meta['zero24']/32000,'clip24_count':meta['clip24'],
            'left_right_abs_ratio':meta['left_abs']/max(meta['right_abs'],1),
            'PCM_SHA256':hashlib.sha256(pcm).hexdigest(),
            'acceptance':'REQUIRES_QUIET_TONE_SPEECH_COMPARISON_AND_OWNER_LISTENING'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True);parser.add_argument('--condition',choices=('quiet','tone','speech'),required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--cue',action='store_true',help='确认台架身份后播放三声提示，再开始录音')
    parser.add_argument('--play-reference',type=Path,help='录音时由电脑外放已登记参考WAV；不向C注入样本')
    a = parser.parse_args()
    if not a.execute: print('MIC_CAPTURE_NOT_STARTED');return 0
    if a.out.exists() or not a.out.parent.stat().st_file_attributes & 0x4000:
        raise ValueError('MIC_NEW_EFS_OUTPUT_REQUIRED')
    a.out.mkdir(); transcript = bytearray(); result = {'exit_code':1,'condition':a.condition,'scope':'MIC_BENCH_ONLY'}
    import serial
    s = serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=2);s.dtr=False;s.rts=False;s.port=a.port
    def line(deadline):
        buf = bytearray()
        while time.monotonic() < deadline:
            b=s.read(1);buf.extend(b);transcript.extend(b)
            if b==b'\n': return bytes(buf)
            if len(buf)>32000: raise ValueError('MIC_HEADER_TOO_LONG')
        raise TimeoutError('MIC_SERIAL_LINE_TIMEOUT')
    try:
        s.open();s.write(b'I');deadline=time.monotonic()+3
        while not line(deadline).startswith(b'MIC_BENCH_ID PA4_PC10_PC12 16000 S24_32 LEFT'): pass
        if a.cue:
            import winsound
            for frequency in (650,650,1000):
                winsound.Beep(frequency,160);time.sleep(.18)
            result['operator_audio_cue_executed']=True
        s.write(b'R');deadline=time.monotonic()+7
        if a.play_reference:
            import winsound
            reference=a.play_reference.read_bytes()
            result['acoustic_reference_WAV_SHA256']=hashlib.sha256(reference).hexdigest()
            winsound.PlaySound(str(a.play_reference),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        while True:
            answer=line(deadline)
            if answer in (b'MIC_DONE\r\n',b'MIC_CAPTURE_ERROR\r\n'):break
        s.write(b'D');meta=json.loads(line(time.monotonic()+4));count=meta['bytes']
        if not 0 <= count <= 64000:raise ValueError('MIC_PAYLOAD_BOUND')
        data=bytearray();deadline=time.monotonic()+15
        while len(data)<count and time.monotonic()<deadline:
            b=s.read(min(4096,count-len(data)));data.extend(b);transcript.extend(b)
        trailer=bytearray()
        while len(trailer)<11 and time.monotonic()<deadline:
            b=s.read(11-len(trailer));trailer.extend(b);transcript.extend(b)
        (a.out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
        (a.out/'audio.pcm').write_bytes(data)
        if trailer!=b'\r\nMIC_END\r\n':raise ValueError('MIC_TRAILER_OR_TRUNCATION')
        with wave.open(str(a.out/'audio.wav'),'wb') as wav:
            wav.setparams((1,2,16000,0,'NONE','not compressed'));wav.writeframes(data)
        result.update(analyze(meta,data),exit_code=0)
    except (ValueError,TimeoutError,serial.SerialException) as error:
        result.update(error_type=type(error).__name__,reason=str(error))
    finally:
        if a.play_reference:
            import winsound
            winsound.PlaySound(None,0)
        if s.is_open:s.close()
        (a.out/'serial-raw.bin').write_bytes(transcript)
        (a.out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
