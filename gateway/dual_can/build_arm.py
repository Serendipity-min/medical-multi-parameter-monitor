"""双总线C的软件链接验证，既不构建云连接配置，也不执行下载。"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument('--network-link', action='store_true', help='仅链接完整H3 MQTT传输，不运行固件/网络')
    targets.add_argument('--bench', action='store_true', help='独立禁联网台架及本地测试TIME，仅构建不部署')
    targets.add_argument('--b5', action='store_true', help='B5手工武装MOCK网络完整候选；只构建，禁止部署')
    parser.add_argument('--egress-final', action='store_true', help='仅B5出口收尾候选，离线构建')
    parser.add_argument('--tri', action='store_true', help='A/B双CAN与B5云端集成候选，保护原48KiB分区')
    parser.add_argument('--audio-link', action='store_true', help='仅离线保留MIC/TTS完整API与CCM缓存，不启用录音或新增现场命令')
    parser.add_argument('--unified', action='store_true', help='真实三板语音统一运行候选；不执行设备操作')
    parser.add_argument('--five-node', action='store_true', help='五板静态来源候选；仅离线构建')
    parser.add_argument('--five-appliance', action='store_true', help='五板自动启动/KEY1/事实回复候选；仅离线构建，不部署')
    parser.add_argument('--field01', action='store_true', help='Issue #8 手动单窗网络探针，只构建')
    parser.add_argument('--bench-seconds', type=int, choices=(15,60,300), help='PHY隔离诊断单次硬时限；仅bench分段布局')
    parser.add_argument('--bench-small-frames', action='store_true', help='300秒候选仅保留B心跳与D温度；离线构建，不授权超规格上电')
    parser.add_argument('--bench-five-segments', action='store_true', help='五板双段完整CAN取证，固定60秒，无网络/音频')
    parser.add_argument('--split-flash', action='store_true', help='统一候选分段布局：sector0向量、sector4代码；只构建，写sector4另需负责人确认')
    parser.add_argument('--tls-port',type=int,help='统一候选的隔离TLS入口，默认1883；不更改原B5的8883目标')
    args = parser.parse_args()
    if args.tri and not (args.b5 and args.egress_final):parser.error('--tri requires --b5 --egress-final')
    if args.audio_link and not args.tri:parser.error('--audio-link requires --tri')
    if args.unified and (not args.tri or args.audio_link):parser.error('--unified requires --tri and excludes --audio-link')
    if args.split_flash and not (args.unified or args.bench):parser.error('--split-flash requires --unified or --bench')
    if args.five_node and not (args.split_flash and (args.unified or args.bench)):parser.error('--five-node requires split unified/bench')
    if args.five_appliance and not (args.five_node and args.unified):parser.error('--five-appliance requires --five-node --unified')
    if args.field01 and (not args.five_appliance or args.tls_port not in (None,28895)):parser.error('--field01 requires --five-appliance and isolated TLS port 28895')
    if args.bench_seconds is not None and not (args.bench and args.split_flash and args.five_node):parser.error('--bench-seconds requires --bench --split-flash --five-node')
    if args.bench_small_frames and args.bench_seconds!=300:parser.error('--bench-small-frames requires --bench-seconds 300; 15s already small')
    if args.bench_five_segments and (args.bench_seconds!=60 or args.bench_small_frames):parser.error('--bench-five-segments requires 60s full-frame bench')
    small_frames=args.bench_seconds==15 or args.bench_small_frames
    if args.tls_port is not None and (not args.unified or not 1<=args.tls_port<=65535):parser.error('--tls-port requires --unified and port1..65535')
    if args.egress_final and not args.b5:parser.error('--egress-final requires --b5')
    spec = importlib.util.spec_from_file_location('b4_sdk', ROOT / 'gateway/esp_at_probe/build.py')
    base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT / 'node-b/build' / ('b4-c-arm-' + stamp); out.mkdir(parents=True)
    vendor = ROOT / 'gateway/third_party/CANopenNode'
    sources = [HERE / name for name in ('arm_link.c', 'system_hse.c', 'b4_bus.c', 'b4_gateway.c', 'b4_bxcan.c')]
    sources += [ROOT / 'gateway/canopen/src/mp_od.c', ROOT / 'gateway/data_model/model.c', ROOT / 'gateway/storage/router.c',
                ROOT / 'gateway/mqtt/src/heap.c', ROOT / 'gateway/esp_at_probe/src/syscalls.c', vendor / 'CANopen.c',
                *sorted((vendor / '301').glob('*.c'))]
    sources += [base.LIBRARY / 'Libraries/STM32F4xx_StdPeriph_Driver/src' / name for name in
                ('stm32f4xx_rcc.c', 'stm32f4xx_gpio.c', 'stm32f4xx_can.c', 'misc.c')]
    flags = [*base.COMMON_FLAGS, '-DCO_MULTIPLE_OD', '-DMP_FRAME_MAX_SAMPLES=100', '-DMP_CACHE_CAPACITY=64',
             '-DHSE_VALUE=8000000', '-I' + str(HERE),
             '-I' + str(ROOT / 'gateway/canopen/src'), '-I' + str(vendor),
             *['-I' + str(p) for p in base.INCLUDES]]
    if args.tri:flags += ['-DMP_ABC_TRI_CANDIDATE', '-flto']
    if args.five_node:flags += ['-DMP_FIVE_NODE']
    if args.field01:flags += ['-DMP_FIVE_FIELD01']
    if args.five_appliance:flags += ['-DMP_FIVE_APPLIANCE']
    if args.bench_seconds is not None:flags += [f'-DB4_BENCH_LIMIT_MS={args.bench_seconds*1000}u', '-DB4_FIVE_CAPTURE' if args.bench_five_segments else '-DB4_PHY_DIAGNOSTIC']
    if small_frames:flags += ['-DB4_PHY_SMALL_FRAMES']
    reference_sha = {}
    if args.egress_final:
        # 总80个MpFrame槽不增：从历史划8槽给实时，配合可推进ACK和时效调度。
        flags.remove('-DMP_CACHE_CAPACITY=64')
        flags += ['-DMP_B5_EGRESS_FINAL','-DMP_LIVE_CAPACITY=24','-DMP_CACHE_CAPACITY=56','-fstack-usage']
    if args.b5:
        # H3逐文件引入的传输与当前双CAN真实驱动一起编译，不能复用旧网络链接产物。
        transport = ROOT / 'gateway/mqtt/src'
        probe = ROOT / 'gateway/esp_at_probe/src'
        sources = [p for p in sources if p.name not in ('arm_link.c', 'syscalls.c', 'heap.c')]
        sources += [ROOT / 'gateway/b5/network_main.c', ROOT / 'gateway/b5/b5_policy.c',
                    *[transport / n for n in ('gateway_transport.c','mqtt_transport_adapter.c','platform.c','heap.c','gateway_assert.c')],
                    probe / 'syscalls.c', probe / 'stm32f4xx_it.c',
                    base.LIBRARY / 'Libraries/STM32F4xx_StdPeriph_Driver/src/stm32f4xx_usart.c']
        mqtt = ROOT / 'gateway/third_party/coreMQTT'
        sources += [mqtt/'source'/n for n in ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')]
        flags += ['-DMP_B5_CLOUD_CANDIDATE', '-DMP_CAN_RX_IRQ', '-DMP_H3_FRESH_SNTP',
                  '-DMP_H3_PERSISTENT_CONFIG', '-DMP_H3_WIFI_AWAKE', '-DMP_MQTT_GATEWAY_ID="GW-B5-001"',
                  '-I'+str(ROOT/'gateway/b5'), '-I'+str(transport), '-I'+str(probe),
                  '-I'+str(mqtt/'source/include'), '-I'+str(mqtt/'source/interface')]
    if args.bench:
        # 白名单独立入口；不导入H3传输源/配置头，也不构建网络或麦克风驱动。
        sources = [p for p in sources if p.name != 'arm_link.c']
        sources += [HERE / 'bench_main.c', HERE / 'b4_bench.c', HERE / 'b4_capture.c', HERE / 'b4_capture_uart.c',
                    base.LIBRARY / 'Libraries/STM32F4xx_StdPeriph_Driver/src/stm32f4xx_usart.c']
        flags += ['-DB4_CAPTURE_SERIAL=1']
    if args.network_link:
        # 按提交逐字节取出源码到构建目录，不修改H3工作区、云端或私有配置。
        ref = 'a5cdd5b0b1ad48108fd631136e9de69e30582f2d'
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', ref,
            'gateway/mqtt/src', 'gateway/esp_at_probe/src'], cwd=ROOT).decode().splitlines()
        names += ['gateway/data_model/model.h']
        for name in names:
            file = out / 'reference-h3' / name; file.parent.mkdir(parents=True, exist_ok=True)
            data = subprocess.check_output(['git', 'show', ref + ':' + name], cwd=ROOT)
            file.write_bytes(data); reference_sha[name] = hashlib.sha256(data).hexdigest()
        # 冻结传输C源保持原字节；其相对包含的公共模型头必须与本目标的100点ABI一致。
        (out / 'reference-h3/gateway/data_model/model.h').write_bytes((ROOT / 'gateway/data_model/model.h').read_bytes())
        transport = out / 'reference-h3/gateway/mqtt/src'
        probe = out / 'reference-h3/gateway/esp_at_probe/src'
        sources = [p for p in sources if p.name not in ('arm_link.c', 'syscalls.c', 'heap.c')]
        sources += [HERE / 'network_main.c', *[p for p in transport.glob('*.c') if p.name != 'main.c'],
                    probe / 'syscalls.c', probe / 'stm32f4xx_it.c',
                    base.LIBRARY / 'Libraries/STM32F4xx_StdPeriph_Driver/src/stm32f4xx_usart.c']
        mqtt = ROOT / 'gateway/third_party/coreMQTT'
        sources += [mqtt / 'source' / name for name in ('core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c')]
        flags += ['-DMP_H3_FRESH_SNTP', '-I' + str(transport), '-I' + str(probe),
                  '-I' + str(out / 'reference-h3/gateway/physical_can/src'),
                  '-I' + str(mqtt / 'source/include'), '-I' + str(mqtt / 'source/interface')]
    if args.audio_link or args.unified:
        sources += [ROOT/'gateway/microphone'/n for n in ('bench_main.c','mic_format.c')]
        sources += [ROOT/'gateway/microphone'/n for n in (('mic_protocol.c','unified_audio.c') if args.unified else ('link_probe.c',))]
        sources += [ROOT/'gateway/voice'/n for n in ('tts_frame.c','tts_queue.c','tts_uart_port.c')]
        flags += ['-DMIC_SHARED_RUNTIME','-DMIC_NETWORK_BENCH','-DMP_CLOUD_VOICE',
                  '-I'+str(ROOT/'gateway/microphone'),'-I'+str(ROOT/'gateway/voice')]
        if args.unified:flags += ['-DMP_FINAL_UNIFIED',f'-DMP_MQTT_TLS_PORT={args.tls_port or (28895 if args.five_appliance else 1883)}']
    linker = ROOT/'gateway/b5/flash.ld' if args.b5 else (HERE/'bench_flash.ld' if args.bench else ROOT/'gateway/mqtt/STM32F407ZGT6_FLASH.ld')
    if args.audio_link or args.unified:
        template=linker.read_text(encoding='utf-8')
        memory='  RAM (xrw)   : ORIGIN = 0x20000000, LENGTH = 128K'
        assert template.count(memory)==1 and template.count('  /DISCARD/')==1
        template=template.replace(memory,memory+'\n  CCM (rw)    : ORIGIN = 0x10000000, LENGTH = 64K')
        template=template.replace('  /DISCARD/', '  .ccm_audio (NOLOAD) : { *(.ccm_audio) } > CCM\n\n'+
                                  ('  .audio_link_probe : { KEEP(*(.audio_link_probe)) } > FLASH\n\n' if args.audio_link else '')+'  /DISCARD/')
        linker=out/'audio-ccm-link.ld';linker.write_text(template,encoding='utf-8')
    if args.split_flash:
        template=linker.read_text(encoding='utf-8').replace('  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 48K',
            '  FLASH (rx)  : ORIGIN = 0x08010000, LENGTH = 64K\n  BOOT (rx)   : ORIGIN = 0x08000000, LENGTH = 16K')
        first=template.index('  } > FLASH');template=template[:first]+template[first:].replace('  } > FLASH','  } > BOOT',1)
        template=template.replace('<=0x0800C000','<=0x08020000').replace('APPLICATION_OVERLAPS_CONFIG_SECTOR3','CODE_EXCEEDS_SECTOR4')
        linker=out/'split-link.ld';linker.write_text(template,encoding='utf-8')
    log = bytearray(); commands = []; audio_layout=None

    def run(command):
        p = subprocess.run(list(map(str, command)), capture_output=True, timeout=120)
        log.extend(p.stdout + p.stderr); commands.append({'argv': list(map(str, command)), 'exit_code': p.returncode})
        if p.returncode: raise RuntimeError('构建失败，真实退出=' + str(p.returncode))
        return p.stdout

    status = 'FAIL'; irq_vector_verified=False
    try:
        objects = []
        for i, source in enumerate(sources):
            obj = out / (str(i) + '.o')
            warnings = ['-Wextra', '-Werror'] if source.is_relative_to(HERE) else []
            run([base.GCC, *flags, *warnings, '-c', source, '-o', obj]); objects.append(obj)
        obj = out / 'startup.o'; run([base.GCC, *flags, '-c', base.STARTUP, '-o', obj]); objects.append(obj)
        target = 'FIVE_FIELD01_C' if args.field01 else 'FIVE_APPLIANCE_C_2S_V1' if args.five_appliance else 'ABC_UNIFIED_C_V1' if args.unified else 'ABC_AUDIO_LINK_PROBE' if args.audio_link else 'ABC_TRI_CLOUD_CANDIDATE' if args.tri else 'B5_CLOUD_MOCK_GATEWAY' if args.b5 else ('B4_GATEWAY_BENCH' if args.bench else ('B4_GATEWAY_NETWORK_SOFTWARE' if args.network_link else 'B4_GATEWAY_LINK_ONLY'))
        elf = out / (target + '.elf')
        run([base.GCC, *flags, '-T', linker,
             '-Wl,--gc-sections', '-Wl,-Map=' + str(out / 'gateway.map'), '--specs=nano.specs', '--specs=nosys.specs',
             *objects, '-lm', '-o', elf])
        run([base.SIZE, elf])
        if args.split_flash:
            run([base.OBJCOPY,'-O','ihex',elf,out/(target+'.hex')])
            raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];step,count=struct.unpack_from('<HH',raw,42)
            pieces=[]
            for i in range(count):
                typ,fileoff,_,pa,fs,_,_,_=struct.unpack_from('<8I',raw,off+i*step)
                if typ==1 and fs:
                    assert (0x08000000<=pa<pa+fs<=0x08004000) or (0x08010000<=pa<pa+fs<=0x08020000)
                    pieces.append((pa,raw[fileoff:fileoff+fs]))
            for name,lo,hi in (('boot',0x08000000,0x08004000),('code',0x08010000,0x08020000)):
                selected=[(a,b) for a,b in pieces if lo<=a<hi];assert selected
                end=max(a+len(b) for a,b in selected);data=bytearray(b'\xff'*(end-lo))
                for a,b in selected:data[a-lo:a-lo+len(b)]=b
                (out/(target+'-'+name+'.bin')).write_bytes(data)
        else:run([base.OBJCOPY, '-O', 'binary', elf, out / (target + '.bin')])
        if args.b5:
            nm=base.GCC.with_name('arm-none-eabi-nm'+base.GCC.suffix)
            symbols=run([nm,elf]);(out/'symbols.txt').write_bytes(symbols)
            table={p[2]:(int(p[0],16),p[1]) for line in symbols.decode().splitlines() if len(p:=line.split())==3}
            image=(out/(target+('-boot.bin' if args.split_flash else '.bin'))).read_bytes()
            # F407 SDK: CAN2_RX0_IRQn=64，向量号=16+64；不能错用CAN2_TX的63。
            for name,index in (('CAN1_RX0_IRQHandler',36),('CAN2_RX0_IRQHandler',80),('USART3_IRQHandler',55)):
                if table.get(name,(0,'W'))[1]!='T' or int.from_bytes(image[index*4:index*4+4],'little')!=(table[name][0]|1):
                    raise RuntimeError('B5实际中断向量未绑定:'+name)
            if args.audio_link or args.unified:
                for name,index in (('DMA1_Stream0_IRQHandler',27),('USART2_IRQHandler',54),('SysTick_Handler',15)):
                    assert table.get(name,(0,'W'))[1]=='T' and int.from_bytes(image[index*4:index*4+4],'little')==table[name][0]|1
                sizes=run([nm,'-S',elf]).decode()
                sized={p[3]:(int(p[0],16),int(p[1],16)) for line in sizes.splitlines() if len(p:=line.split())==4}
                dma=[v for n,v in sized.items() if n.startswith('dma_words')]
                assert len(dma)==1 and dma[0][1]==2560 and 0x20000000<=dma[0][0]<dma[0][0]+dma[0][1]<=0x20020000
                pcm=[v for n,v in sized.items() if n=='pcm' or n.startswith('pcm.lto')]
                assert len(pcm)==1 and pcm[0][1]==64000 and 0x10000000<=pcm[0][0]<pcm[0][0]+pcm[0][1]<=0x10010000
                raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];step,count=struct.unpack_from('<HH',raw,42);loads=[]
                for i in range(count):
                    typ,_,va,pa,fs,ms,_,_=struct.unpack_from('<8I',raw,off+i*step)
                    if typ!=1:continue
                    assert not fs or 0x08000000<=pa<pa+fs<=0x0800c000 or (args.split_flash and 0x08010000<=pa<pa+fs<=0x08020000)
                    loads.append({'RAM_start':va,'load_start':pa,'load_bytes':fs,'memory_bytes':ms})
                audio_layout={'load_segments':loads,'DMA':dma[0],'PCM':pcm[0],
                              'audio_IRQ_priority':8,'CAN_IRQ_priority':3,'runtime_enabled':args.unified}
            if len(image)>49152 or any(n.encode() in symbols for n in ('FLASH_EraseSector','FLASH_ProgramWord')):
                raise RuntimeError('B5应用越过sector2或包含Flash写入口')
            irq_vector_verified=True
        if args.bench:
            # 检查实际ELF符号，防止仅靠入口宏声称禁联网；nm不访问调试器或设备。
            nm = base.GCC.with_name('arm-none-eabi-nm' + base.GCC.suffix)
            symbols = run([nm, elf])
            (out / 'symbols.txt').write_bytes(symbols)
            # 真实向量必须指向强USART1处理器，不能只链接到弱Default_Handler就声称IRQ已启用。
            table={parts[2]:(int(parts[0],16),parts[1]) for line in symbols.decode().splitlines()
                   if len(parts:=line.split())==3}
            handler=table.get('USART1_IRQHandler',(0,'W'))
            wake=table.get('b4_capture_uart_wake',(0,'W'))
            image=(out/(target+('-boot.bin' if args.split_flash else '.bin'))).read_bytes();vector=int.from_bytes(image[53*4:54*4],'little')
            if handler[1]!='T' or wake[1]!='T' or vector!=(handler[0]|1):
                raise RuntimeError('台架USART1中断向量/唤醒入口未实际链接')
            for name,index in (('CAN2_RX0_IRQHandler',80),('SysTick_Handler',15)):
                if table.get(name,(0,'W'))[1]!='T' or int.from_bytes(image[index*4:index*4+4],'little')!=(table[name][0]|1):
                    raise RuntimeError('台架实际中断向量未绑定:'+name)
            irq_vector_verified=True
            forbidden = ('gateway_network_open', 'gateway_mqtt_open', 'gateway_config_valid',
                         'h3_config_record_valid', 'FLASH_EraseSector', 'FLASH_ProgramWord')
            if any(name.encode() in symbols for name in forbidden):
                raise RuntimeError('台架ELF包含禁止的网络/配置/写入符号')
            if 'gateway/mqtt/src' in '\n'.join(str(p.relative_to(ROOT)) for p in sources if p.is_relative_to(ROOT)):
                # heap.c是既有纯内存分配封装，不含网络/配置；其余传输源不允许混入。
                if any('gateway/mqtt/src' in p.as_posix() and p.name != 'heap.c' for p in sources):
                    raise RuntimeError('台架源白名单失败')
        if args.split_flash:
            def artifact(p):return {'file':p.name,'SHA256':hashlib.sha256(p.read_bytes()).hexdigest()}
            layout={'schema':1,'target':target,'erase_sectors':[0,4],'sector4_owner_approval_required':True,
                'images':[dict(address=a,bytes=(out/(target+'-'+n+'.bin')).stat().st_size,
                    **artifact(out/(target+'-'+n+'.bin'))) for n,a in [('boot',0x08000000),('code',0x08010000)]],
                'HEX':artifact(out/(target+'.hex')),'ELF':artifact(elf),'TLS_port':None if args.bench else args.tls_port or (28895 if args.five_appliance else 1883),
                'time_policy':'LOCAL_TEST_TIME_NEVER_CLOUD' if args.bench else 'B5_FRESH_SNTP_UNCHANGED',
                'normal_runtime_limit':'FIELD01 PRE once up to 60s; START once; ready45s; window150s; hard210s; audio64chunks' if args.field01 else f'B4START one-shot {args.bench_seconds or 180}s' if args.bench else 'FIVE automatic; explicit STOP; audio maximum2s' if args.five_appliance else 'UNISTART manual-stop; B5START retains420s',
                'sector3_options_and_all_other_sectors':'PRESERVE'}
            (out/'unified-layout.json').write_text(json.dumps(layout,indent=2)+'\n')
        status = 'PASS'
    except RuntimeError as error:
        log.extend(str(error).encode())
    (out / 'build.log').write_bytes(log)
    (out / 'executed-builder.py').write_bytes(Path(__file__).read_bytes())
    headers = [*HERE.glob('*.h'), *vendor.rglob('*.h'), *ROOT.glob('gateway/canopen/src/*.h'),
               ROOT / 'gateway/data_model/model.h', ROOT / 'gateway/data_model/roles.h', ROOT / 'gateway/storage/router.h']
    if args.network_link:
        headers += list((out / 'reference-h3').rglob('*.h'))
    if args.b5:
        headers += [*ROOT.glob('gateway/b5/*.h'),*ROOT.glob('gateway/mqtt/src/*.h')]
    if args.field01:headers += [ROOT / 'gateway/b5/field01_probe.inc', ROOT / 'gateway/mqtt/src/field01_preflight.inc']
    if args.audio_link or args.unified:headers += [*ROOT.glob('gateway/microphone/*.h'),*ROOT.glob('gateway/voice/*.h')]
    report = {'ABC_tri_candidate': args.tri, 'version': 'B5-001' if args.b5 else 'B4-0.2', 'status': status,
              'scope': 'FINAL_UNIFIED_C_REAL_RUNTIME_OFFLINE_NOT_DEPLOYED' if args.unified else 'B5_CLOUD_MOCK_SOFTWARE_ONLY_NOT_DEPLOYED' if args.b5 else ('C_ISOLATED_BENCH_LOCAL_TEST_TIME_NOT_DEPLOYED' if args.bench else ('C_DUAL_CAN_ARM_NETWORK_SOFTWARE_BUILD_NOT_DEPLOYED' if args.network_link else 'C_DUAL_CAN_ARM_LINK_ONLY')),
              'bench_time': 'LOCAL_TEST_EPOCH_NOT_UTC' if args.bench else None,
              'bench_window_limit_ms': (args.bench_seconds or 180)*1000 if args.bench else None,
              'bench_traffic_policy': 'NODE1_2_4_5_OP_BOTH_BUSES_FULL_WAVE' if args.bench_five_segments else 'NODE2_PREOP_NODE4_OP_NO_ECG' if small_frames else 'NODE2_OP' if args.bench else None,
              'bench_forbidden_symbols_absent': bool(args.bench and status == 'PASS'),
              'bench_UART_IRQ_vector_verified':irq_vector_verified,
              'linker_sha256': hashlib.sha256(linker.read_bytes()).hexdigest(),
              'audio_link_probe':args.audio_link,'audio_layout':audio_layout,
              'field01':args.field01,'unified_runtime':args.unified,'five_node':args.five_node,'five_appliance':args.five_appliance,'split_flash_requires_owner_approval':args.split_flash,
              'hardware_eligible': False, 'network_transport': 'B5_H3_TRANSPORT_B4_RETRY_DRIVER_ARM_LINKED_NOT_EXECUTED' if args.b5 else ('H3_FROZEN_SOURCE_LINKED_NOT_EXECUTED' if args.network_link else 'NOT_LINKED_NOT_DEPLOYED'),
              'h3_reference_commit': 'a5cdd5b0b1ad48108fd631136e9de69e30582f2d', 'h3_reference_sha256': reference_sha, 'commands': commands,
              'log_sha256': hashlib.sha256(log).hexdigest(),
              'header_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in headers},
              'artifact_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*') if p.suffix in ('.bin', '.elf','.hex')},
              'source_sha256': {(str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'external-sdk/' + p.name):
                                hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(str(out.relative_to(ROOT)), status)
    if args.b5 and status=='PASS':
        print(json.dumps({'artifact_sha256':report['artifact_sha256'],'IRQ_vectors_verified':irq_vector_verified}))
    else: print(log.decode(errors='replace')[-4500:])
    return int(status != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
