"""只编译独立源板Keil工程，保留每次真实日志/产物，完全不调用J-Link。"""
from pathlib import Path
import argparse,contextlib,datetime,hashlib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parent.parent
ART=ROOT.parent/'artifacts/ecg-source'
@contextlib.contextmanager
def mapping(path):
    # 老Keil不可靠支持中文路径；只占用空闲自有SUBST映射，不修改用户已有映射。
    letter=next((x for x in 'RSTUVW' if not Path(x+':/').exists()),None)
    if not letter:raise RuntimeError('没有空闲构建映射')
    subprocess.run(['subst',letter+':',str(path)],check=True)
    try:yield letter+':/'
    finally:
        listing=subprocess.run(['subst'],capture_output=True,check=True).stdout.decode('gbk',errors='replace')
        if any(line.startswith(letter+':\\:') and str(path).casefold() in line.casefold() for line in listing.splitlines()):
            subprocess.run(['subst',letter+':','/d'],check=True)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--keil-home',type=Path,default=Path('D:/keil'))
    args=parser.parse_args();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run=ROOT/'build'/('arm-'+stamp);run.mkdir(parents=True)
    result={'scope':'ORDINARY_ARM_OFFLINE_BUILD','hardware_operations':[],'status':'PREPARING'}
    # 构建前封存当前源码/工具身份，每次失败也能回溯准确输入。
    inputs=[p for p in ROOT.rglob('*') if p.is_file() and 'build' not in p.relative_to(ROOT).parts]
    (run/'input-manifest.json').write_text(json.dumps({'files':[{
        'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()
    } for p in inputs]},ensure_ascii=False,indent=2),'utf-8')
    try:
        with mapping(ROOT.resolve()) as prefix:
            cp=subprocess.run([str(args.keil_home/'UV4/UV4.exe'),'-r',prefix+'MPM_ECG_SOURCE.uvprojx',
                               '-o',prefix+'build/'+run.name+'/build.log'],capture_output=True,timeout=180)
        (run/'launcher.stdout.log').write_bytes(cp.stdout);(run/'launcher.stderr.log').write_bytes(cp.stderr)
        result['exit_code']=cp.returncode
        log=(run/'build.log').read_text(errors='replace')
        counts=re.search(r'(\d+) Error\(s\),\s*(\d+) Warning\(s\)',log)
        if counts:result.update(errors=int(counts[1]),warnings=int(counts[2]))
        if cp.returncode or '0 Error(s)' not in log:raise RuntimeError('ARM构建失败，保留原始日志')
        resources=re.search(r'Code=(\d+) RO-data=(\d+) RW-data=(\d+) ZI-data=(\d+)',log)
        if not resources:raise RuntimeError('没有真实资源报告')
        axf=ROOT/'build/MPM_ECG_SOURCE.axf';shutil.copyfile(axf,run/axf.name)
        exe=args.keil_home/'ARM/ARMCC/bin/fromelf.exe'
        for mode,name in [('--bin','MPM_ECG_SOURCE.bin'),('-s','symbols.txt')]:
            converted=subprocess.run([str(exe),mode,'--output',str(run/name),str(run/axf.name)],capture_output=True,timeout=60)
            if converted.returncode:raise RuntimeError('fromelf失败')
        # 归档map为本地证据，避免用历史产物；公开只保留必要符号/资源摘要。
        maps=list((ROOT/'build').glob('*.map'))
        for p in maps:shutil.copyfile(p,run/p.name)
        symbols=(run/'symbols.txt').read_text(errors='replace')
        expected=['DMA1_Stream5_IRQHandler','TIM6_DAC_IRQHandler','g_source_dma_buffer','Src_ApplyMode','g_source_requested_mode']
        if not all(x in symbols for x in expected):raise RuntimeError('缺少源板关键符号')
        address=re.search(r'\bg_source_dma_buffer\s+0x([0-9a-fA-F]+)',symbols)
        if not address or not 0x20000000<=int(address[1],16)<0x20020000:raise RuntimeError('DMA缓冲未落普通SRAM')
        result.update(status='PASS',resources=dict(zip(['code','ro','rw','zi'],map(int,resources.groups()))),
            dma_buffer_address='0x'+address[1],outputs={p.name:{'bytes':p.stat().st_size,
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in run.iterdir() if p.suffix in ['.bin','.axf','.map']})
        # 删去绝对构建路径后另存可公开日志，原日志保留；不修改固件源文件来脱敏。
        public=log.replace(str(ROOT),'[SOURCE_PROJECT]').replace(str(ROOT).replace('\\','/'),'[SOURCE_PROJECT]')
        public=re.sub(r'[RSTUVW]:[\\/]', '[BUILD_ROOT]/',public)
        # 只清理本轮生成的公开日志行尾；原始日志和ST/受测源文件保持原字节。
        public='\n'.join(line.rstrip() for line in public.splitlines())+'\n'
        (ART/'arm-build.log.txt').write_text(public,'utf-8')
    except BaseException as error:
        result.update(status='FAIL',error=type(error).__name__+': '+str(error));raise
    finally:
        (run/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
        (ART/'arm-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
