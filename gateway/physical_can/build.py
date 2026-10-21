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
parser=argparse.ArgumentParser();parser.add_argument('--host',action='store_true');parser.add_argument('--irq',action='store_true');parser.add_argument('--isolated',action='store_true');parser.add_argument('--wifi-awake',action='store_true');parser.add_argument('--fresh-sntp',action='store_true');parser.add_argument('--rx-order',action='store_true');parser.add_argument('--peer-cycle',action='store_true');parser.add_argument('--wire',type=Path);parser.add_argument('--persistent-config',action='store_true');parser.add_argument('--evidence-dir',type=Path);args=parser.parse_args()
if args.persistent_config and (not args.irq or args.host):parser.error('--persistent-config requires ARM IRQ candidate')
if args.peer_cycle and (not args.host or not args.irq or args.rx_order or args.wire):parser.error('--peer-cycle requires --host --irq alone')
if args.isolated and not args.irq:parser.error('--isolated requires --irq')
if args.wifi_awake and not args.irq:parser.error('--wifi-awake requires --irq')
if args.fresh_sntp and not args.irq:parser.error('--fresh-sntp requires --irq')
build=HERE/(('build/h3-r2-persistent-isolated' if args.isolated else 'build/h3-r2-persistent-normal') if args.persistent_config else 'build/h3-isolated' if args.isolated else 'build/h3-irq' if args.irq else 'build');build.mkdir(parents=True,exist_ok=True)
# 新验收显式选择证据目录，避免重跑覆盖R2原始构建回执；默认路径保留兼容。
evidence=args.evidence_dir or HERE/(('evidence/h3-r2/persistent-isolated' if args.isolated else 'evidence/h3-r2/persistent-normal') if args.persistent_config else 'evidence/h3' if args.irq else 'evidence');evidence.mkdir(parents=True,exist_ok=True)
# 列表复用项目源码，不复制修改 coreMQTT、TLS、AT、PUBACK 或原模拟目标。
common=[HERE/'src/stack.c',HERE/'src/adapter.c',CO/'src/mp_can_driver.c',CO/'src/mp_od.c',ROOT/'gateway/data_model/model.c',ROOT/'gateway/storage/router.c',VENDOR/'CANopen.c',*sorted((VENDOR/'301').glob('*.c'))]
commands=[]
def run(cmd,input_data=None):
    commands.append(list(map(str,cmd)))
    r=subprocess.run(list(map(str,cmd)),capture_output=True,input=input_data)
    log.extend(r.stdout+r.stderr)
    if r.returncode: raise subprocess.CalledProcessError(r.returncode,cmd)
log=bytearray();result={'feature':'H3_NETWORK_IRQ' if args.irq else 'LEGACY_POLLING','mode':'HOST' if args.host else 'ARM_PHYSICAL_CAN1_CANDIDATE','hardware':'NOT_RUN','wifi_awake':args.wifi_awake,'fresh_sntp':args.fresh_sntp}
try:
    if args.host:
        sources=[*common,HERE/('tests/peer_power_cycle.c' if args.peer_cycle else 'tests/network_order.c' if args.rx_order else 'tests/wire.c' if args.wire else 'tests/protocol.c')]
        if args.rx_order: sources.append(HERE/'bench/rx_irq.c')
        # 重启回归直接编译生产驱动，仅用Host头文件替换寄存器/时钟边界。
        if args.peer_cycle:sources += [HERE/'src/bxcan_network_irq.c',HERE/'bench/rx_irq.c']
        run(['gcc','-std=c11','-O1','-g','-DCO_MULTIPLE_OD',*(['-DMP_CAN_RX_IRQ'] if args.irq else []),*(['-DMP_H3_TEST_SOURCE','-DMP_MQTT_TLS_PORT=8884'] if args.isolated else []),'-Wall','-Wextra','-Wno-unused-parameter',*(['-I'+str(HERE/'tests/hw')] if args.peer_cycle else []),'-I'+str(HERE/'src'),'-I'+str(HERE/'bench'),'-I'+str(MQTT/'src'),'-I'+str(CO/'src'),'-I'+str(VENDOR),*sources,'-o',build/'physical_host.exe'])
        start=len(log)
        run([build/'physical_host.exe'],args.wire.read_bytes() if args.wire else None)
        if args.peer_cycle:
            for fault in ('busoff','unknown-error','stuck'):run([build/'physical_host.exe',fault])
        if args.wire:
            (evidence/'node-a-to-c-canonical.jsonl').write_bytes(log[start:])
            result['wire_sha256']=hashlib.sha256(args.wire.read_bytes()).hexdigest()
    else:
        spec=importlib.util.spec_from_file_location('base',ROOT/'gateway/esp_at_probe/build.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
        vendor=ROOT/'gateway/third_party/coreMQTT'
        includes=[HERE/'src',HERE/'bench',MQTT/'src',CO/'src',VENDOR,vendor/'source/include',vendor/'source/interface',*base.INCLUDES]
        flags=[*base.COMMON_FLAGS,'-DCO_MULTIPLE_OD',*(['-DMP_CAN_RX_IRQ','-DHSE_VALUE=8000000'] if args.irq else []),*(['-DMP_H3_WIFI_AWAKE'] if args.wifi_awake else []),*(['-DMP_H3_TEST_SOURCE','-DMP_MQTT_TLS_PORT=8884',*(['-DMP_H3_VOLATILE_CONFIG'] if not args.persistent_config else [])] if args.isolated else []),*(['-DMP_H3_PERSISTENT_CONFIG'] if args.persistent_config else []),*['-I'+str(p) for p in includes]]
        if args.fresh_sntp:flags.append('-DMP_H3_FRESH_SNTP')
        # 启动与 G 共用硬件就绪后单次 NMT 入口；Host 协议夹具无需链接物理生命周期。
        sources=[*common,HERE/'src/main.c',HERE/'src/lifecycle.c',*([HERE/'src/bxcan_network_irq.c',HERE/'bench/rx_irq.c'] if args.irq else [HERE/'src/bxcan_physical.c']),*[p for p in sorted((MQTT/'src').glob('*.c')) if p.name!='main.c'],*base.SOURCES[1:],vendor/'source/core_mqtt.c',vendor/'source/core_mqtt_serializer.c',vendor/'source/core_mqtt_state.c']
        if args.irq:
            # 精确替换独立候选的系统时钟文件；不改原HSI模板或第三方SDK。
            sources=[p for p in sources if p.name!='system_stm32f4xx.c']+[HERE/'src/system_hse.c']
        objects=[]
        for i,source in enumerate(sources):
            # 仅候选项目代码启用额外告警为错误，不更改固定第三方核心的编译语义。
            warnings=['-Wextra','-Werror'] if source.is_relative_to(HERE/'src') else []
            obj=build/(str(i)+'_'+source.stem+'.o');run([base.GCC,*flags,*warnings,'-c',source,'-o',obj]);objects.append(obj)
        startup=build/'startup.o';run([base.GCC,*flags,'-c',base.STARTUP,'-o',startup]);objects.append(startup)
        elf=build/'gateway_physical_can.elf'
        run([base.GCC,*flags,'-T',(HERE/'H3_PERSISTENT_FLASH.ld' if args.persistent_config else HERE/'H3_ISOLATED_FLASH.ld' if args.isolated else HERE/'H3_NETWORK_FLASH.ld' if args.irq else MQTT/'STM32F407ZGT6_FLASH.ld'),'-Wl,--gc-sections','-Wl,-Map='+str(build/'gateway_physical_can.map'),'--specs=nano.specs','--specs=nosys.specs','-o',elf,*objects,'-lm'])
        run([base.SIZE,elf]);run([base.OBJCOPY,'-O','binary',elf,build/'gateway_physical_can.bin'])
        if args.irq:
            from image_manifest import inspect
            result['image'] = inspect(elf,build/'gateway_physical_can.bin',base.TOOLCHAIN/('arm-none-eabi-nm.exe' if __import__('sys').platform=='win32' else 'arm-none-eabi-nm'))
            if args.persistent_config:
                # 应用镜像绝不能携带配置或进入sector3；配置写入仍须单独授权与原件门禁。
                if any(i>2 for i in result['image']['erase_sectors']):raise ValueError('PERSISTENT_APP_OVERLAPS_SECTOR3')
                result['persistent_config']={'address':0x0800C000,'sector':3,'record_bytes':336,
                    'erase_bytes':16384,'runtime_flash_writes':False,'encrypted':False,
                    'physical_write_authorization':'REQUIRED_NOT_GRANTED','flash_configuration_written':False}
            elif args.isolated:
                if result['image']['initial_sp'] != 0x2001FE00:raise ValueError('H3_RAM_CONFIG_NOT_RESERVED')
                result['volatile_config']={'address':0x2001FE00,'bytes':312,'reserved_bytes':512,'flash_configuration_written':False}
    result['exit_code']=0
except subprocess.CalledProcessError as e:
    result['exit_code']=e.returncode
except ValueError as e:
    # 下载计划门禁失败同样保留非零构建证据，不能被finally中的缺失退出码掩盖。
    result.update(exit_code=1,validation_error=str(e))
finally:
    name=('peer-cycle-' if args.peer_cycle else 'rx-order-' if args.rx_order else '')+('isolated-' if args.isolated else '')+('wire' if args.wire else 'host' if args.host else 'arm')
    (evidence/(name+'.log')).write_bytes(log)
    result['commands']=commands
    # SDK 在仓库外，单独命名并保存字节摘要，不能因 relative_to 异常掩盖真实构建退出码。
    result['source_sha256']={(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else 'external-sdk/'+p.relative_to(base.LIBRARY).as_posix()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    if args.irq:
        # 下载前复核头文件/启动向量/链接脚本，不能只校验C文件而漏掉内存布局变化。
        inputs=[Path(__file__),HERE/'image_manifest.py',HERE/'H3_NETWORK_FLASH.ld',HERE/'H3_ISOLATED_FLASH.ld',HERE/'H3_PERSISTENT_FLASH.ld',
                *sorted((HERE/'src').glob('*.h')),*sorted((HERE/'bench').glob('*.h')),
                *sorted((MQTT/'src').glob('*.h'))]
        if not args.host:inputs.append(base.STARTUP)
        result['build_input_sha256']={(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else 'external-sdk/'+p.relative_to(base.LIBRARY).as_posix()):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (evidence/(name+'-result.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(name,'exit',result['exit_code']);print(log.decode('utf-8',errors='replace')[-3500:])
raise SystemExit(result['exit_code'])
