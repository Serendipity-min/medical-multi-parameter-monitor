"""复用C现有SPL/GNU工具链，仅构建禁联网MIC台架；不访问设备。"""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    spec = importlib.util.spec_from_file_location('c_sdk', ROOT/'gateway/esp_at_probe/build.py')
    sdk = importlib.util.module_from_spec(spec); spec.loader.exec_module(sdk)
    out = ROOT/'node-b/build'/('mic-bench-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir()
    driver = sdk.LIBRARY/'Libraries/STM32F4xx_StdPeriph_Driver/src'
    sources = [HERE/'bench_main.c', HERE/'mic_format.c', ROOT/'gateway/dual_can/system_hse.c',
               ROOT/'gateway/esp_at_probe/src/syscalls.c',
               *[driver/n for n in ('stm32f4xx_rcc.c','stm32f4xx_gpio.c','stm32f4xx_usart.c')], sdk.STARTUP]
    flags = [*sdk.COMMON_FLAGS, '-DHSE_VALUE=8000000', '-I'+str(HERE),
             '-I'+str(ROOT/'gateway/dual_can'), *['-I'+str(p) for p in sdk.INCLUDES]]
    receipt = {'status':'FAIL', 'scope':'MIC_BENCH_BUILD_ONLY', 'device_operations':0, 'commands':[]}
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
        elf = out/'MIC_BENCH.elf'; binary = out/'MIC_BENCH.bin'
        run([sdk.GCC,*flags,'-T',ROOT/'gateway/b5/flash.ld','-Wl,--gc-sections',
             '-Wl,-Map='+str(out/'MIC_BENCH.map'),'--specs=nano.specs','--specs=nosys.specs',
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
        for name,index in (('DMA1_Stream0_IRQHandler',27),('SysTick_Handler',15)):
            address = {p[2]:(int(p[0],16),p[1]) for line in simple.splitlines() if len(p:=line.split())==3}[name]
            assert address[1]=='T' and int.from_bytes(image[index*4:index*4+4],'little') == address[0]|1
        address,bytes_,_ = table['dma_words']
        assert 0x20000000 <= address < address+bytes_ <= 0x20020000 and bytes_ == 2560
        assert len(image) <= 49152
        assert not any(n.encode() in symbols for n in ('FLASH_EraseSector','FLASH_ProgramWord','gateway_network_open','gateway_mqtt_open'))
        receipt.update(status='MIC_BENCH_BUILD_PASS', BIN_bytes=len(image), ELF_load_segments=loads,
                       DMA_buffer_address=hex(address),DMA_buffer_bytes=bytes_,strong_IRQ_vectors_verified=True,
                       sector3_not_in_image=True,network_and_Flash_write_symbols_absent=True,
                       artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (elf,binary,out/'symbols.txt')})
    except subprocess.CalledProcessError as error:
        receipt['failure_native_exit_code'] = error.returncode
    finally:
        (out/'build.log').write_bytes(log)
        receipt['source_SHA256'] = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'external/'+p.name:
                                   hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        (ROOT/'node-b/build/mic-bench-current-pointer.json').write_text(json.dumps({'out':str(out)})+'\n')
    print(json.dumps({'status':receipt['status'],'out':str(out),'BIN_bytes':receipt.get('BIN_bytes')}))
    return 0 if receipt['status']=='MIC_BENCH_BUILD_PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
