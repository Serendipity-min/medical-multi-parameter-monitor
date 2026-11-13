"""执行真实源驱动C的普通Host寄存器模型检查；不运行安全扫描或访问硬件。"""
from pathlib import Path
import ctypes as C
import datetime,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parent.parent
ART=ROOT.parent/'artifacts/ecg-source'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT=ROOT/'build'/('host-'+stamp);OUT.mkdir(parents=True)
FIELDS=['tag','version','mode','state','faults','mode_changes','core_hz','timer_hz','psc','arr',
        'table_length','completed_tables','completed_dma_samples','bias_code','first_code',
        'last_dma_flags','last_dac_flags','dma_reset_count']
class Diag(C.Structure):_fields_=[(x,C.c_uint32) for x in FIELDS]
class Table(C.Structure):_fields_=[('codes',C.POINTER(C.c_uint16)),('length',C.c_uint32),('beats',C.c_uint32),('bpm',C.c_uint32)]
class Rcc(C.Structure):_fields_=[(x,C.c_uint32) for x in ['AHB1ENR','APB1ENR','CFGR','AHB1RSTR']]
class Dac(C.Structure):_fields_=[(x,C.c_uint32) for x in ['CR','DHR12R1','DHR12R2','SR','DOR1','DOR2']]
class Tim(C.Structure):_fields_=[(x,C.c_uint32) for x in ['CR1','CR2','PSC','ARR','CNT','EGR','SR']]
class Stream(C.Structure):_fields_=[(x,C.c_uint32) for x in ['CR','PAR','M0AR','NDTR','FCR']]
class Dma(C.Structure):_fields_=[(x,C.c_uint32) for x in ['HISR','HIFCR']]
receipt={'scope':'ORDINARY_HOST_REAL_C_WITH_MMIO_MODEL','hardware_operations':[],
         'analog_calibration':False,'checks':[]}
def check(name,ok):
    receipt['checks'].append({'name':name,'pass':bool(ok)})
    if not ok:raise AssertionError(name)
try:
    dll=OUT/'source.dll'
    cmd=['C:/mingw64/bin/gcc.exe','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared',
         '-DSRC_HOST_TEST','-I'+str(ROOT/'src'),'-I'+str(ROOT/'tests')]
    cmd +=[str(ROOT/x) for x in ['src/source_driver.c','src/source_waveform.c','src/waveform_tables.c','tests/mmio_mock.c']]
    cmd +=['-o',str(dll)]
    p=subprocess.run(cmd,capture_output=True,timeout=60)
    (OUT/'compile.stdout.log').write_bytes(p.stdout);(OUT/'compile.stderr.log').write_bytes(p.stderr)
    receipt['compile_exit']=p.returncode
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    lib=C.CDLL(str(dll));lib.Src_GetTable.argtypes=[C.c_uint32];lib.Src_GetTable.restype=C.POINTER(Table)
    lib.Src_ApplyMode.argtypes=[C.c_uint32];lib.Src_ApplyMode.restype=C.c_uint8
    lib.Src_CopyRotated.argtypes=[C.POINTER(C.c_uint16),C.c_uint32,C.POINTER(C.c_uint32)];lib.Src_CopyRotated.restype=C.c_uint8
    lib.Src_TimerPlan.argtypes=[C.c_uint32,C.POINTER(C.c_uint32),C.POINTER(C.c_uint32)];lib.Src_TimerPlan.restype=C.c_uint8
    lib.Src_Fault.argtypes=[C.c_uint32];lib.SrcMock_Trigger.restype=C.c_uint32
    diag=Diag.in_dll(lib,'g_source_diag');dac=Dac.in_dll(lib,'src_mock_dac')
    tim=Tim.in_dll(lib,'src_mock_tim');stream=Stream.in_dll(lib,'src_mock_stream')
    rcc=Rcc.in_dll(lib,'src_mock_rcc');dma=Dma.in_dll(lib,'src_mock_dma')
    def word(name):return C.c_uint32.in_dll(lib,name)
    def init():lib.SrcMock_Reset();lib.Src_Init()
    init();check('boot_OFF_no_TRGO_DMA_DAC',diag.mode==0 and diag.state==0 and dac.CR==0 and not tim.CR1 and not stream.CR&1)
    check('nominal_clock_binding',diag.core_hz==168000000 and diag.timer_hz==84000000)
    for hz,valid in [(84000000,True),(42000000,True),(0,False),(84000001,False),(168000000,False)]:
        a=C.c_uint32();b=C.c_uint32();got=lib.Src_TimerPlan(hz,C.byref(a),C.byref(b))
        check('timer_plan_'+str(hz),bool(got)==valid and (not valid or hz//((a.value+1)*(b.value+1))==1000))
    check('timer_null_rejected',not lib.Src_TimerPlan(84000000,None,None))
    for mode,count,beats,bpm in [(2,1000,0,0),(3,1000,1,60),(4,2000,3,90)]:
        table=lib.Src_GetTable(mode).contents;codes=[table.codes[i] for i in range(count)]
        check('table_identity_'+str(mode),table.length==count and table.beats==beats and table.bpm==bpm)
        check('table_bounds_'+str(mode),min(codes)>=1024 and max(codes)<=3328 and max(codes)-min(codes)==1240)
        # 从量化样本独立找主要R峰，不拿元数据本身证明拍数。
        peaks=[i for i in range(count) if codes[i]>2848 and codes[i]>=codes[(i-1)%count] and codes[i]>codes[(i+1)%count]]
        if mode!=2:check('QRS_count_and_rational_rate_'+str(mode),len(peaks)==beats and len(peaks)*60000/count==bpm)
        init();check('start_mode_'+str(mode),lib.Src_ApplyMode(mode)==1)
        check('DMA_mapping_width_'+str(mode),(stream.CR>>25)&7==7 and (stream.CR>>11)&3==2 and (stream.CR>>13)&3==2)
        actual=[lib.SrcMock_Trigger() for _ in range(count*2+2)]
        check('pipeline_no_start_duplicate_or_wrap_skip_'+str(mode),actual==[codes[i%count] for i in range(len(actual))])
        check('UG_before_DAC_trigger_'+str(mode),word('src_mock_ug_while_trigger').value==0 and tim.PSC==83 and tim.ARR==999)
        check('DMA_counter_is_tables_not_beats_'+str(mode),diag.completed_tables==2 and diag.completed_dma_samples==count*2)
        old=diag.mode_changes;check('same_mode_no_restart_'+str(mode),lib.Src_ApplyMode(mode)==1 and diag.mode_changes==old)
        check('OFF_stops_output_'+str(mode),lib.Src_ApplyMode(0)==1 and dac.CR==0 and tim.CR1==0 and not stream.CR&1)
    init();check('static_same_code_no_DMA',lib.Src_ApplyMode(1)==1 and diag.state==1 and dac.DHR12R1==dac.DHR12R2==2048 and not tim.CR1)
    raw=(C.c_uint16*2)(2048,2049);out=(C.c_uint32*2)(123,456)
    check('rotate_first_point_preloaded',lib.Src_CopyRotated(raw,2,out)==1 and list(out)==[2049,2048])
    for bad in [0,4095]:
        raw[1]=bad;out[0]=123;out[1]=456
        check('invalid_code_no_partial_publish_'+str(bad),not lib.Src_CopyRotated(raw,2,out) and list(out)==[123,456])
    check('invalid_table_length',not lib.Src_CopyRotated(raw,0,out) and not lib.Src_CopyRotated(raw,2001,out))
    check('null_table_pointer',not lib.Src_CopyRotated(None,2,out) and not lib.Src_CopyRotated(raw,2,None))
    init();check('invalid_mode_safe_static',not lib.Src_ApplyMode(99) and diag.faults&2 and diag.state==3 and dac.CR==0x10001 and dac.DHR12R1==2048)
    check('fault_latched_no_auto_restart',not lib.Src_ApplyMode(3) and not tim.CR1 and diag.faults&2)
    lib.Src_ApplyMode(0);check('explicit_OFF_keeps_failure_evidence',diag.faults&2 and dac.CR==0)
    for clock,cfgr,name in [(16000000,(5<<10)|8,'HSI'),(168000000,(4<<10)|8,'APB1'),(168000000,(5<<10),'not_PLL')]:
        lib.SrcMock_Reset();word('SystemCoreClock').value=clock;rcc.CFGR=cfgr;lib.Src_Init()
        check('clock_drift_reject_'+name,diag.faults&1 and diag.state==3 and not lib.Src_ApplyMode(3))
    for flag in [1<<6,1<<8,1<<9,(1<<9)|(1<<11)]:
        init();lib.Src_ApplyMode(3);dma.HISR=flag;lib.DMA1_Stream5_IRQHandler()
        check('DMA_error_priority_'+str(flag),diag.faults&8 and diag.completed_tables==0 and not tim.CR1 and dac.DHR12R1==2048)
    for flag in [1<<13,1<<29]:
        init();lib.Src_ApplyMode(4);dac.SR=flag;lib.TIM6_DAC_IRQHandler()
        check('DAC_underrun_'+str(flag),diag.faults&16 and diag.state==3 and not tim.CR1)
    init();lib.Src_ApplyMode(3);dma.HISR=1<<9
    check('mode_change_preserves_pending_DMA_error',not lib.Src_ApplyMode(1) and diag.faults&8 and diag.last_dma_flags==1<<9)
    lib.DMA1_Stream5_IRQHandler();check('spurious_DMA_IRQ_keeps_original_flags',diag.last_dma_flags==1<<9)
    init();lib.Src_ApplyMode(3);dac.SR=1<<13
    check('mode_change_preserves_pending_DAC_error',not lib.Src_ApplyMode(4) and diag.faults&16 and diag.last_dac_flags==1<<13)
    lib.TIM6_DAC_IRQHandler();check('spurious_DAC_IRQ_keeps_original_flags',diag.last_dac_flags==1<<13)
    init();lib.Src_ApplyMode(3);dma.HISR=1<<9;dac.SR=1<<13
    check('pending_combined_errors_both_recorded',not lib.Src_ApplyMode(4) and diag.faults&24==24 and not tim.CR1)
    init();lib.Src_ApplyMode(3);word('src_mock_stuck').value=1
    check('DMA_disable_timeout_reset_latches',not lib.Src_ApplyMode(1) and diag.faults&32 and diag.state==3 and diag.dma_reset_count>=1)
    init();lib.Src_ApplyMode(3);word('src_mock_stuck').value=1;word('src_mock_reset_blocked').value=1
    check('unconfirmed_DMA_stop_highZ',not lib.Src_ApplyMode(1) and diag.state==4 and dac.CR==0 and not tim.CR1)
    lib.Src_ApplyMode(0);check('failed_OFF_not_false_success',diag.state==4 and diag.faults&32)
    init();word('src_mock_primask').value=1;lib.Src_ApplyMode(2)
    check('critical_section_preserves_disabled_IRQ',word('src_mock_primask').value==1)
    receipt.update(status='PASS',passed=len(receipt['checks']),total=len(receipt['checks']),
       source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').glob('*') if p.is_file()})
except BaseException as error:
    receipt.update(status='FAIL',error=type(error).__name__+': '+str(error));raise
finally:
    (OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf-8')
    # 固定公开摘要不含本机路径、UID、固件原件；失败日志也留在各次独立build目录。
    (ART/'host-summary.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'status':receipt['status'],'passed':receipt['passed'],'total':receipt['total']}))
