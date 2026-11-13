"""脱机生成固定DAC码表：工程QRS不冒充临床ECG，电压列只是假定参考下的计算值。"""
from pathlib import Path
import csv,hashlib,json,math
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT.parent/'artifacts/ecg-source'

def ecg(count,bpm):
    period=60.0/bpm
    values=[]
    for i in range(count):
        # 宽度用秒固定；90bpm采用2秒3拍而非将667点近似成每一拍。
        p=((i/1000.0-.3+period/2)%period)-period/2
        y=(.12*math.exp(-.5*((p+.18)/.035)**2)
           -.15*math.exp(-.5*((p+.025)/.008)**2)
           +math.exp(-.5*(p/.012)**2)
           -.25*math.exp(-.5*((p-.025)/.01)**2)
           +.30*math.exp(-.5*((p-.25)/.055)**2))
        values.append(y)
    gain=1240/(max(values)-min(values))
    # 保留等电位基线为2048码；正/负工程峰的比例来自上面的冻结形状。
    return [2048+round(v*gain) for v in values]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    tables={'sine':[2048+round(620*math.sin(2*math.pi*i/1000)) for i in range(1000)],
            'ecg60':ecg(1000,60),'ecg90':ecg(2000,90)}
    metadata={'scope':'SOFTWARE_DAC_CODES_NOT_MEASURED_VOLTAGE','sample_hz_nominal':1000,
              'bias_code':2048,'reference_voltage_measured':None,
              'voltage_model':'code * assumed_VREF / 4096; local older RM0090 displays /4095; neither is calibration',
              'shape':'fixed engineering P/Q/R/S/T Gaussian fixture, positive R','tables':{}}
    lines=['/* 固定脱机生成表；仅源板工程使用，物理电压/节律须G2独立实测。 */',
           '#include <stdint.h>']
    for name,codes in tables.items():
        assert all(1024<=x<=3328 for x in codes)
        symbol={'sine':'src_sine','ecg60':'src_ecg60','ecg90':'src_ecg90'}[name]
        lines.append('const uint16_t '+symbol+'['+str(len(codes))+']={')
        lines += ['    '+','.join(map(str,codes[i:i+16]))+',' for i in range(0,len(codes),16)]
        lines.append('};')
        raw=b''.join(x.to_bytes(2,'little') for x in codes)
        metadata['tables'][name]={'count':len(codes),'duration_s':len(codes)/1000,
            'beats':{'sine':0,'ecg60':1,'ecg90':3}[name],
            'bpm':{'sine':None,'ecg60':60,'ecg90':90}[name],
            'minimum':min(codes),'maximum':max(codes),'peak_to_peak_codes':max(codes)-min(codes),
            'codes_u16le_sha256':hashlib.sha256(raw).hexdigest()}
    with (OUT/'software-waveform.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['mode','sample_index','assigned_time_ms','DAC1_code','DAC2_code',
                                  'outputs_enabled','nominal_volts_if_VREF_3V3','reference_status'])
        w.writerow(['OFF',0,0,None,None,0,None,'NOT_MEASURED'])
        w.writerow(['BIAS',0,0,2048,2048,1,2048*3.3/4096,'NOT_MEASURED'])
        for name,codes in tables.items():
            for i,c in enumerate(codes):w.writerow([name,i,i,c,2048,1,c*3.3/4096,'NOT_MEASURED'])
    (ROOT/'src/waveform_tables.c').write_text('\n'.join(lines)+'\n','utf-8')
    (OUT/'waveform-spec.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:(v['count'],v['codes_u16le_sha256']) for k,v in metadata['tables'].items()}))

if __name__=='__main__':main()
