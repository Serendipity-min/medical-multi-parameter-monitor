"""复用C现有SPL/GNU工具链，仅构建禁联网MIC台架；不访问设备。"""
import datetime
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--network',action='store_true');args=parser.parse_args()
    spec = importlib.util.spec_from_file_location('c_sdk', ROOT/'gateway/esp_at_probe/build.py')
    sdk = importlib.util.module_from_spec(spec); spec.loader.exec_module(sdk)
    out = ROOT/'node-b/build'/('mic-bench-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir()
    driver = sdk.LIBRARY/'Libraries/STM32F4xx_StdPeriph_Driver/src'
    sources = [HERE/'bench_main.c', HERE/'mic_format.c', ROOT/'gateway/dual_can/system_hse.c',
               ROOT/'gateway/esp_at_probe/src/syscalls.c',
               *[driver/n for n in ('stm32f4xx_rcc.c','stm32f4xx_gpio.c','stm32f4xx_usart.c')], sdk.STARTUP]
    flags = [*sdk.COMMON_FLAGS, '-fstack-usage', '-DHSE_VALUE=8000000', '-I'+str(HERE),
             '-I'+str(ROOT/'gateway/dual_can'), *['-I'+str(p) for p in sdk.INCLUDES]]
    if args.network:
        mqtt=ROOT/'gateway/third_party/coreMQTT'
        sources += [HERE/'network_main.c',HERE/'network_transport.c',HERE/'mic_protocol.c',ROOT/'gateway/data_model/model.c',
                    *[ROOT/'gateway/mqtt/src'/n for n in ('platform.c','mqtt_transport_adapter.c','heap.c','gateway_assert.c')],
                    *[mqtt/'source'/n for n in ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')],
                    *[ROOT/'gateway/voice'/n for n in ('tts_frame.c','tts_queue.c','tts_uart_port.c')]]
        flags += ['-DMIC_NETWORK_BENCH','-DMP_TTS_BENCH','-DMP_H3_PERSISTENT_CONFIG','-DMP_H3_FRESH_SNTP',
                  '-DMP_H3_WIFI_AWAKE','-DMP_CAN_RX_IRQ','-DMP_MQTT_TLS_PORT=18884','-DMP_MQTT_GATEWAY_ID="GW-MIC-TEST"',
                  '-I'+str(ROOT/'gateway/mqtt/src'),'-I'+str(ROOT/'gateway/voice'),
                  '-I'+str(mqtt/'source/include'),'-I'+str(mqtt/'source/interface')]
    target='MIC_NETWORK_BENCH' if args.network else 'MIC_BENCH'
    receipt = {'status':'FAIL', 'scope':'C_ONLY_VOICE_NETWORK_BUILD_NOT_TRIBOARD_CONCURRENCY' if args.network else 'MIC_BENCH_BUILD_ONLY', 'device_operations':0, 'commands':[]}
    log = bytearray()

    def run(args):
        r = subprocess.run(list(map(str,args)), capture_output=True, timeout=90)
        log.extend(r.stdout+r.stderr)
        receipt['commands'].append({'tool':Path(str(args[0])).name,'actual_exit_code':r.returncode})
        r.check_returncode()
        return r.stdout

    try:
        objects = []
        for i, source in enumerate(sources):
            obj = out/f'{i}.o'; extra = ['-Wextra','-Werror'] if source.parent == HERE else []
            run([sdk.GCC,*flags,*extra,'-c',source,'-o',obj]); objects.append(obj)
        elf = out/(target+'.elf'); binary = out/(target+'.bin')
        run([sdk.GCC,*flags,'-T',ROOT/'gateway/b5/flash.ld','-Wl,--gc-sections',
             '-Wl,-Map='+str(out/(target+'.map')),'--specs=nano.specs','--specs=nosys.specs',
             *objects,'-lm','-o',elf])
        run([sdk.SIZE,elf]); run([sdk.OBJCOPY,'-O','binary',elf,binary])
        symbols = run([sdk.GCC.with_name('arm-none-eabi-nm.exe'),'-S',elf])
        (out/'symbols.txt').write_bytes(symbols)
        table = {p[3]:(int(p[0],16),int(p[1],16),p[2]) for line in symbols.decode().splitlines()
                 if len(p:=line.split())==4}
        image = binary.read_bytes(); raw = elf.read_bytes(); loads = []
        assert raw[4:6] == b'\x01\x01'
        off = struct.unpack_from('<I',raw,28)[0]; size,count = struct.unpack_from('<HH',raw,42)
        for i in range(count):
            typ,_,vaddr,paddr,filesz,memsz,_,_ = struct.unpack_from('<8I',raw,off+i*size)
            if typ != 1: continue
            if filesz: assert 0x08000000 <= paddr < paddr+filesz <= 0x0800c000
            assert 0x08000000 <= vaddr < 0x0800c000 or 0x20000000 <= vaddr <= vaddr+memsz <= 0x20020000
            loads.append({'physical_address':hex(paddr),'virtual_address':hex(vaddr),'file_bytes':filesz,'memory_bytes':memsz})
        # 无size的汇编/别名符号另以普通nm核对。
        simple = run([sdk.GCC.with_name('arm-none-eabi-nm.exe'),elf]).decode()
        irqs=[('DMA1_Stream0_IRQHandler',27),('SysTick_Handler',15)]
        if args.network:irqs += [('USART2_IRQHandler',54),('USART3_IRQHandler',55)]
        for name,index in irqs:
            address = {p[2]:(int(p[0],16),p[1]) for line in simple.splitlines() if len(p:=line.split())==3}[name]
            assert address[1]=='T' and int.from_bytes(image[index*4:index*4+4],'little') == address[0]|1
        address,bytes_,_ = table['dma_words']
        assert 0x20000000 <= address < address+bytes_ <= 0x20020000 and bytes_ == 2560
        assert len(image) <= 49152
        forbidden=['FLASH_EraseSector','FLASH_ProgramWord']
        if not args.network:forbidden+=['gateway_network_open','gateway_mqtt_open']
        assert not any(n.encode() in symbols for n in forbidden)
        if args.network:assert b'CAN_Init' not in symbols
        receipt.update(status='MIC_BENCH_BUILD_PASS', BIN_bytes=len(image), ELF_load_segments=loads,
                       DMA_buffer_address=hex(address),DMA_buffer_bytes=bytes_,strong_IRQ_vectors_verified=True,
                       sector3_not_in_image=True,Flash_write_symbols_absent=True,network_linked=args.network,
                       artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (elf,binary,out/'symbols.txt')})
    except subprocess.CalledProcessError as error:
        receipt['failure_native_exit_code'] = error.returncode
    finally:
        (out/'build.log').write_bytes(log)
        receipt['source_SHA256'] = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'external/'+p.name:
                                   hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        pointer='mic-network-current-pointer.json' if args.network else 'mic-bench-current-pointer.json'
        (ROOT/'node-b/build'/pointer).write_text(json.dumps({'out':str(out)})+'\n')
    print(json.dumps({'status':receipt['status'],'out':str(out),'BIN_bytes':receipt.get('BIN_bytes')}))
    return 0 if receipt['status']=='MIC_BENCH_BUILD_PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
