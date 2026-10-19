"""H2独立CAN-only构建；源码白名单、链接范围及符号检查是功能隔离验证，不运行安全扫描。"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'gateway/physical_can'
CO=ROOT/'gateway/canopen'
VENDOR=ROOT/'gateway/third_party/CANopenNode'
parser=argparse.ArgumentParser();parser.add_argument('--host',action='store_true');parser.add_argument('--h2r',action='store_true');args=parser.parse_args()
# 独立H2R输出保留原H2二进制及历史失败证据，不覆盖原受测镜像。
build=HERE/('build/h2r' if args.h2r else 'build/bench');build.mkdir(parents=True,exist_ok=True)
out=HERE/('evidence/h2r' if args.h2r else 'evidence/h2');out.mkdir(exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
name=('host-' if args.host else 'arm-')+stamp
commands=[];log=bytearray()
result={'mode':'CAN_ONLY_BENCH_HOST' if args.host else 'CAN_ONLY_BENCH_ARM','hardware':'NOT_RUN','network':'NOT_LINKED','exit_code':1}
result['variant']='H2R_IRQ_STATIC_RX' if args.h2r else 'H2_POLLING'
def run(cmd):
    cmd=list(map(str,cmd));commands.append(cmd)
    r=subprocess.run(cmd,capture_output=True);log.extend(r.stdout+r.stderr)
    if r.returncode:raise subprocess.CalledProcessError(r.returncode,cmd)
    return r.stdout.decode('utf-8',errors='replace')
sources=[HERE/'src/stack.c',HERE/'src/adapter.c',HERE/'src/lifecycle.c',HERE/'bench/bench.c',CO/'src/mp_can_driver.c',CO/'src/mp_od.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',VENDOR/'CANopen.c',*sorted((VENDOR/'301').glob('*.c'))]
includes=[HERE/'bench',HERE/'src',CO/'src',VENDOR]
try:
    if args.host:
        sources.append(HERE/'tests/bench_host.c')
        extra=['-DCAN_BENCH_IRQ'] if args.h2r else []
        run(['gcc','-std=c11','-O1','-g','-DCO_MULTIPLE_OD','-DCAN_ONLY_BENCH',*extra,'-Wall','-Wextra','-Wno-unused-parameter',*['-I'+str(p) for p in includes],*sources,'-o',build/'bench_host.exe'])
        run([build/'bench_host.exe','no-ack']);run([build/'bench_host.exe','unexpected-b'])
        if args.h2r:
            run(['gcc','-std=c11','-O1','-g','-DCO_MULTIPLE_OD','-DCAN_ONLY_BENCH','-Wall','-Wextra','-Werror',*['-I'+str(p) for p in includes],HERE/'bench/rx_irq.c',HERE/'tests/rx_irq_mmio.c','-o',build/'rx_irq_mmio.exe'])
            run([build/'rx_irq_mmio.exe'])
            sources += [HERE/'bench/rx_irq.c',HERE/'tests/rx_irq_mmio.c']
    else:
        spec=importlib.util.spec_from_file_location('base',ROOT/'gateway/esp_at_probe/build.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
        includes += [ROOT/'gateway/mqtt/src',*base.INCLUDES]
        # 明确排除原main/platform/网络库/配置实现；仅复用固定堆、启动和ST外设库。
        driver=[HERE/'bench/bxcan_irq.c',HERE/'bench/rx_irq.c'] if args.h2r else [HERE/'src/bxcan_physical.c']
        sources += [HERE/'bench/platform.c',*driver,ROOT/'gateway/mqtt/src/heap.c',ROOT/'gateway/esp_at_probe/src/system_stm32f4xx.c',ROOT/'gateway/esp_at_probe/src/syscalls.c',*base.SOURCES[4:]]
        flags=[*base.COMMON_FLAGS,'-DCO_MULTIPLE_OD','-DCAN_ONLY_BENCH',*(['-DCAN_BENCH_IRQ'] if args.h2r else []),*['-I'+str(p) for p in includes]]
        objects=[]
        for i,p in enumerate(sources):
            obj=build/(str(i)+'_'+p.stem+'.o');warnings=['-Wextra','-Werror'] if p.is_relative_to(HERE) else []
            run([base.GCC,*flags,*warnings,'-c',p,'-o',obj]);objects.append(obj)
        obj=build/'startup.o';run([base.GCC,*flags,'-c',base.STARTUP,'-o',obj]);objects.append(obj)
        elf=build/'can_only_bench.elf';binary=build/'can_only_bench.bin'
        run([base.GCC,*flags,'-T',HERE/'bench/STM32F407_BENCH.ld','-Wl,--gc-sections','-Wl,-Map='+str(build/'can_only_bench.map'),'--specs=nano.specs','--specs=nosys.specs','-o',elf,*objects,'-lm'])
        run([base.SIZE,elf]);run([base.OBJCOPY,'-O','binary',elf,binary])
        objdump=base.GCC.with_name('arm-none-eabi-objdump.exe' if base.GCC.suffix=='.exe' else 'arm-none-eabi-objdump')
        sections=run([objdump,'-h',elf]).splitlines();flash_sections=[]
        for i,line in enumerate(sections[:-1]):
            fields=line.split()
            if len(fields)>=7 and fields[0].isdigit() and all(f in sections[i+1] for f in ['CONTENTS','ALLOC','LOAD']):
                size=int(fields[2],16);address=int(fields[4],16)
                assert 0x08000000<=address and address+size<=0x08010000
                flash_sections.append({'section':fields[1],'load_address':hex(address),'bytes':size})
        assert flash_sections
        result['flash_load_sections']=flash_sections
        nm=base.GCC.with_name('arm-none-eabi-nm.exe' if base.GCC.suffix=='.exe' else 'arm-none-eabi-nm')
        # Windows工具可能输出CRLF；仅规范化用于断言的副本，原始工具日志保持不变。
        symbols=run([nm,'--defined-only',elf]).replace('\r','')
        assert not re.search(r'\b(?:gateway_config_valid|gateway_network_open|gateway_mqtt_open|esp_mqtt_\w+|at_command|FLASH_EraseSector|FLASH_Program\w*)$',symbols,re.M)
        assert 'CAN_ONLY_BENCH' in binary.read_bytes().decode('latin1')
        if args.h2r:
            assert re.search(r'\bT CAN1_RX0_IRQHandler$',symbols,re.M)
            assert 'H2R_IRQ_RX_QUEUE_128' in binary.read_bytes().decode('latin1')
            # 验证实际向量表槽位指向强IRQ实现，而非仅检查函数存在。
            irq=int(re.search(r'^([0-9a-fA-F]+) T CAN1_RX0_IRQHandler$',symbols,re.M)[1],16)
            vector=int.from_bytes(binary.read_bytes()[(16+20)*4:(16+21)*4],'little')
            assert vector==(irq|1)
            result['CAN1_RX0_vector']={'slot':36,'address':hex(vector),'strong_handler':True}
        data=binary.read_bytes();assert 8<=len(data)<=65536
        sp=int.from_bytes(data[:4],'little');reset=int.from_bytes(data[4:8],'little')
        assert 0x20000000<sp<=0x20020000 and 0x08000000<reset<0x08010000 and reset&1
        result['image']={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'start':'0x08000000','end_exclusive':hex(0x08000000+len(data)),'erase_sectors':list(range((len(data)+16383)//16384)),'protected_regions':['0x08060000..0x0807ffff','0x080e0000..0x080fffff']}
        result['isolation_checks']=['explicit_source_allowlist_no_network_or_config','no_network_flash_write_defined_symbols','64KiB_linker_and_vector_bounds','USART1_only_nonblocking_console','no_auto_NMT_until_S','test_time_only_explicit_T']
    result['exit_code']=0
except (subprocess.CalledProcessError,AssertionError) as e:
    result['failure_type']=type(e).__name__;result['exit_code']=getattr(e,'returncode',1)
finally:
    result['commands']=commands
    result['source_sha256']={(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else 'external-sdk/'+p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    # 新增头文件和链接脚本也参与镜像身份；不能只记录C源而遗漏构建边界。
    inputs=[Path(__file__),HERE/'bench/bench.h',HERE/'src/physical.h',HERE/'src/link_policy.h']
    if args.h2r: inputs += [HERE/'bench/rx_irq.h']
    if not args.host: inputs += [HERE/'bench/STM32F407_BENCH.ld',base.STARTUP]
    result['build_input_sha256']={(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else 'external-sdk/'+p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (out/(name+'.log')).write_bytes(log)
    (out/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    # latest只作索引，带时间戳原始失败/成功证据从不覆盖。
    (build/('host-latest.json' if args.host else 'arm-latest.json')).write_text(json.dumps({'result':str(out/(name+'.json'))}),encoding='utf-8')
print(name,'exit',result['exit_code'])
print(log.decode('utf-8',errors='replace')[-2500:] if result['exit_code'] or args.host else json.dumps(result.get('image',{})))
raise SystemExit(result['exit_code'])
