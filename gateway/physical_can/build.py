"""独立物理候选：显式替换三个模拟/回环入口，其余 MQTT/Router/第三方文件原样复用。"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
CO=ROOT/'gateway/canopen';VENDOR=ROOT/'gateway/third_party/CANopenNode';MQTT=ROOT/'gateway/mqtt'
parser=argparse.ArgumentParser();parser.add_argument('--host',action='store_true');parser.add_argument('--wire',type=Path);args=parser.parse_args()
build=HERE/'build';build.mkdir(exist_ok=True)
evidence=HERE/'evidence';evidence.mkdir(exist_ok=True)
# 列表复用项目源码，不复制修改 coreMQTT、TLS、AT、PUBACK 或原模拟目标。
common=[HERE/'src/stack.c',HERE/'src/adapter.c',CO/'src/mp_can_driver.c',CO/'src/mp_od.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',VENDOR/'CANopen.c',*sorted((VENDOR/'301').glob('*.c'))]
commands=[]
def run(cmd,input_data=None):
    commands.append(list(map(str,cmd)))
    r=subprocess.run(list(map(str,cmd)),capture_output=True,input=input_data)
    log.extend(r.stdout+r.stderr)
    if r.returncode: raise subprocess.CalledProcessError(r.returncode,cmd)
log=bytearray();result={'mode':'HOST' if args.host else 'ARM_PHYSICAL_CAN1_CANDIDATE','hardware':'NOT_RUN'}
try:
    if args.host:
        sources=[*common,HERE/('tests/wire.c' if args.wire else 'tests/protocol.c')]
        run(['gcc','-std=c11','-O1','-g','-DCO_MULTIPLE_OD','-Wall','-Wextra','-Wno-unused-parameter','-I'+str(HERE/'src'),'-I'+str(CO/'src'),'-I'+str(VENDOR),*sources,'-o',build/'physical_host.exe'])
        start=len(log)
        run([build/'physical_host.exe'],args.wire.read_bytes() if args.wire else None)
        if args.wire:
            (evidence/'node-a-to-c-canonical.jsonl').write_bytes(log[start:])
            result['wire_sha256']=hashlib.sha256(args.wire.read_bytes()).hexdigest()
    else:
        spec=importlib.util.spec_from_file_location('base',ROOT/'gateway/esp_at_probe/build.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
        vendor=ROOT/'gateway/third_party/coreMQTT'
        includes=[HERE/'src',MQTT/'src',CO/'src',VENDOR,vendor/'source/include',vendor/'source/interface',*base.INCLUDES]
        flags=[*base.COMMON_FLAGS,'-DCO_MULTIPLE_OD',*['-I'+str(p) for p in includes]]
        sources=[*common,HERE/'src/main.c',HERE/'src/bxcan_physical.c',*[p for p in sorted((MQTT/'src').glob('*.c')) if p.name!='main.c'],*base.SOURCES[1:],vendor/'source/core_mqtt.c',vendor/'source/core_mqtt_serializer.c',vendor/'source/core_mqtt_state.c']
        objects=[]
        for i,source in enumerate(sources):
            # 仅候选项目代码启用额外告警为错误，不更改固定第三方核心的编译语义。
            warnings=['-Wextra','-Werror'] if source.is_relative_to(HERE/'src') else []
            obj=build/(str(i)+'_'+source.stem+'.o');run([base.GCC,*flags,*warnings,'-c',source,'-o',obj]);objects.append(obj)
        startup=build/'startup.o';run([base.GCC,*flags,'-c',base.STARTUP,'-o',startup]);objects.append(startup)
        elf=build/'gateway_physical_can.elf'
        run([base.GCC,*flags,'-T',MQTT/'STM32F407ZGT6_FLASH.ld','-Wl,--gc-sections','-Wl,-Map='+str(build/'gateway_physical_can.map'),'--specs=nano.specs','--specs=nosys.specs','-o',elf,*objects,'-lm'])
        run([base.SIZE,elf]);run([base.OBJCOPY,'-O','binary',elf,build/'gateway_physical_can.bin'])
    result['exit_code']=0
except subprocess.CalledProcessError as e:
    result['exit_code']=e.returncode
finally:
    name='wire' if args.wire else 'host' if args.host else 'arm'
    (evidence/(name+'.log')).write_bytes(log)
    result['commands']=commands
    # SDK 在仓库外，单独命名并保存字节摘要，不能因 relative_to 异常掩盖真实构建退出码。
    result['source_sha256']={(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else 'external-sdk/'+p.relative_to(base.LIBRARY).as_posix()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (evidence/(name+'-result.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(name,'exit',result['exit_code']);print(log.decode('utf-8',errors='replace')[-3500:])
raise SystemExit(result['exit_code'])
