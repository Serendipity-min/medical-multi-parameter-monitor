"""双总线C的软件链接验证，既不构建云连接配置，也不执行下载。"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    targets = parser.add_mutually_exclusive_group()
    targets.add_argument('--network-link', action='store_true', help='仅链接完整H3 MQTT传输，不运行固件/网络')
    targets.add_argument('--bench', action='store_true', help='独立禁联网台架及本地测试TIME，仅构建不部署')
    targets.add_argument('--b5', action='store_true', help='B5手工武装MOCK网络完整候选；只构建，禁止部署')
    args = parser.parse_args()
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
    reference_sha = {}
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
    log = bytearray(); commands = []

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
        target = 'B5_CLOUD_MOCK_GATEWAY' if args.b5 else ('B4_GATEWAY_BENCH' if args.bench else ('B4_GATEWAY_NETWORK_SOFTWARE' if args.network_link else 'B4_GATEWAY_LINK_ONLY'))
        elf = out / (target + '.elf')
        linker = ROOT/'gateway/b5/flash.ld' if args.b5 else (HERE / 'bench_flash.ld' if args.bench else ROOT / 'gateway/mqtt/STM32F407ZGT6_FLASH.ld')
        run([base.GCC, *flags, '-T', linker,
             '-Wl,--gc-sections', '-Wl,-Map=' + str(out / 'gateway.map'), '--specs=nano.specs', '--specs=nosys.specs',
             *objects, '-lm', '-o', elf])
        run([base.SIZE, elf]); run([base.OBJCOPY, '-O', 'binary', elf, out / (target + '.bin')])
        if args.b5:
            nm=base.GCC.with_name('arm-none-eabi-nm'+base.GCC.suffix)
            symbols=run([nm,elf]);(out/'symbols.txt').write_bytes(symbols)
            table={p[2]:(int(p[0],16),p[1]) for line in symbols.decode().splitlines() if len(p:=line.split())==3}
            image=(out/(target+'.bin')).read_bytes()
            # F407 SDK: CAN2_RX0_IRQn=64，向量号=16+64；不能错用CAN2_TX的63。
            for name,index in (('CAN1_RX0_IRQHandler',36),('CAN2_RX0_IRQHandler',80),('USART3_IRQHandler',55)):
                if table.get(name,(0,'W'))[1]!='T' or int.from_bytes(image[index*4:index*4+4],'little')!=(table[name][0]|1):
                    raise RuntimeError('B5实际中断向量未绑定:'+name)
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
            image=(out/(target+'.bin')).read_bytes();vector=int.from_bytes(image[53*4:54*4],'little')
            if handler[1]!='T' or wake[1]!='T' or vector!=(handler[0]|1):
                raise RuntimeError('台架USART1中断向量/唤醒入口未实际链接')
            irq_vector_verified=True
            forbidden = ('gateway_network_open', 'gateway_mqtt_open', 'gateway_config_valid',
                         'h3_config_record_valid', 'FLASH_EraseSector', 'FLASH_ProgramWord')
            if any(name.encode() in symbols for name in forbidden):
                raise RuntimeError('台架ELF包含禁止的网络/配置/写入符号')
            if 'gateway/mqtt/src' in '\n'.join(str(p.relative_to(ROOT)) for p in sources if p.is_relative_to(ROOT)):
                # heap.c是既有纯内存分配封装，不含网络/配置；其余传输源不允许混入。
                if any('gateway/mqtt/src' in p.as_posix() and p.name != 'heap.c' for p in sources):
                    raise RuntimeError('台架源白名单失败')
        status = 'PASS'
    except RuntimeError as error:
        log.extend(str(error).encode())
    (out / 'build.log').write_bytes(log)
    (out / 'executed-builder.py').write_bytes(Path(__file__).read_bytes())
    headers = [*HERE.glob('*.h'), *vendor.rglob('*.h'), *ROOT.glob('gateway/canopen/src/*.h'),
               ROOT / 'gateway/data_model/model.h', ROOT / 'gateway/storage/router.h']
    if args.network_link:
        headers += list((out / 'reference-h3').rglob('*.h'))
    if args.b5:
        headers += [*ROOT.glob('gateway/b5/*.h'),*ROOT.glob('gateway/mqtt/src/*.h')]
    report = {'version': 'B5-001' if args.b5 else 'B4-0.2', 'status': status,
              'scope': 'B5_CLOUD_MOCK_SOFTWARE_ONLY_NOT_DEPLOYED' if args.b5 else ('C_ISOLATED_BENCH_LOCAL_TEST_TIME_NOT_DEPLOYED' if args.bench else ('C_DUAL_CAN_ARM_NETWORK_SOFTWARE_BUILD_NOT_DEPLOYED' if args.network_link else 'C_DUAL_CAN_ARM_LINK_ONLY')),
              'bench_time': 'LOCAL_TEST_EPOCH_NOT_UTC' if args.bench else None,
              'bench_window_limit_ms': 180000 if args.bench else None,
              'bench_forbidden_symbols_absent': bool(args.bench and status == 'PASS'),
              'bench_UART_IRQ_vector_verified':irq_vector_verified,
              'linker_sha256': hashlib.sha256((ROOT/'gateway/b5/flash.ld' if args.b5 else (HERE / 'bench_flash.ld' if args.bench else ROOT / 'gateway/mqtt/STM32F407ZGT6_FLASH.ld')).read_bytes()).hexdigest(),
              'hardware_eligible': False, 'network_transport': 'B5_H3_TRANSPORT_B4_RETRY_DRIVER_ARM_LINKED_NOT_EXECUTED' if args.b5 else ('H3_FROZEN_SOURCE_LINKED_NOT_EXECUTED' if args.network_link else 'NOT_LINKED_NOT_DEPLOYED'),
              'h3_reference_commit': 'a5cdd5b0b1ad48108fd631136e9de69e30582f2d', 'h3_reference_sha256': reference_sha, 'commands': commands,
              'log_sha256': hashlib.sha256(log).hexdigest(),
              'header_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in headers},
              'artifact_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*') if p.suffix in ('.bin', '.elf')},
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
