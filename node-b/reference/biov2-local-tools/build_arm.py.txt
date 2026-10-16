"""只构建隔离实验副本并归档真实退出码/符号/资源，不连接开发板。"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

root=Path(__file__).resolve().parent
base=root.parent
sys.path.insert(0,str(base/'工具'))
from acq_swd import ascii_mapping

project=root/'实验固件'
evidence=root/'证据'
with ascii_mapping(project) as prefix:
    # 盘符只属于本轮构建；Keil历史版本用短路径避免中文命令行解析歧义。
    args=['D:/keil/UV4/UV4.exe','-b',prefix+'USER/BIO_V2.uvprojx','-o',prefix+'build.log']
    result=subprocess.run(args,capture_output=True,timeout=180)
    (evidence/'arm_launcher.stdout.log').write_bytes(result.stdout)
    (evidence/'arm_launcher.stderr.log').write_bytes(result.stderr)
    log=(project/'build.log').read_bytes() if (project/'build.log').exists() else b''
    (evidence/'arm_build.log').write_bytes(log)
    decoded=log.decode('utf-8',errors='replace')
    if result.returncode not in [0,1] or not re.search(r'0 Error\(s\)',decoded):
        (evidence/'arm_failure.json').write_text(json.dumps({'exit':result.returncode,'command':args}),encoding='utf-8')
        raise SystemExit(1)
    axf=project/'OBJ/BIO_V2.axf'
    outputs={}
    for mode,file in [('--bin',project/'OBJ/BIO_V2.bin'),('-s',evidence/'symbols.txt')]:
        converted=subprocess.run(['D:/keil/ARM/ARMCC/bin/fromelf.exe',mode,'--output',str(file),str(axf)],capture_output=True)
        if converted.returncode:
            (evidence/'fromelf_error.log').write_bytes(converted.stderr)
            raise SystemExit(converted.returncode)
        outputs[file.name]={'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'bytes':file.stat().st_size}
    outputs[axf.name]={'sha256':hashlib.sha256(axf.read_bytes()).hexdigest(),'bytes':axf.stat().st_size}
    symbols=(evidence/'symbols.txt').read_text(errors='replace')
    # 构建身份必须证明旧处理函数不在ELF中，不能仅靠文件名声称已独立重写。
    old_symbols=re.findall(r'\b(?:PanTompkins_\w+|RespRate_\w+|ECG_Filter_\w+|EcgDespike|ecg_median)\b',symbols)
    assert not old_symbols,old_symbols
    resources=re.search(r'Program Size: Code=(\d+) RO-data=(\d+) RW-data=(\d+) ZI-data=(\d+)',decoded)
    assert resources
    receipt={'exit_code':result.returncode,'errors':0,'ordinary_build_only':True,'old_algorithm_symbols':old_symbols,
             'resources':dict(zip(['code','ro','rw','zi'],map(int,resources.groups()))),'outputs':outputs}
    (evidence/'arm_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))
