"""离线台架专用加载段/向量门禁，不放宽H3联网镜像的CAN强向量门禁。"""
import hashlib
import struct
import subprocess


def inspect(elf, binary, nm):
    data, image = elf.read_bytes(), binary.read_bytes()
    start, limit = 0x08000000, 0x08004000
    if data[:7] != b'\x7fELF\x01\x01\x01' or struct.unpack_from('<H', data, 18)[0] != 40:
        raise ValueError('BENCH_NOT_ARM32_LE')
    offset = struct.unpack_from('<I', data, 28)[0]
    size, count = struct.unpack_from('<HH', data, 42)
    loads = []
    for i in range(count):
        kind, pos, virtual, physical, length, memory, flags, alignment = struct.unpack_from('<8I', data, offset+i*size)
        if kind != 1 or not length:
            continue
        if not start <= physical < physical+length <= limit:
            raise ValueError('BENCH_LOAD_OUTSIDE_SECTOR0')
        if image[physical-start:physical-start+length] != data[pos:pos+length]:
            raise ValueError('BENCH_ELF_BIN_MISMATCH')
        loads.append({'start': physical, 'end_exclusive': physical+length})
    if not loads or max(s['end_exclusive'] for s in loads) != start+len(image):
        raise ValueError('BENCH_EXTENT_MISMATCH')
    sp, reset = struct.unpack_from('<II', image)
    if not 0x20000000 < sp <= 0x20020000 or sp % 8 or not reset & 1 or not start <= reset-1 < start+len(image):
        raise ValueError('BENCH_VECTOR_INVALID')
    symbols = subprocess.check_output([str(nm), '-g', str(elf)], text=True)
    # USART2=IRQ38、SysTick=系统向量15；同时证明CAN/ESP未链接强中断处理器。
    for name, slot in [('USART2_IRQHandler', 16+38), ('SysTick_Handler', 15)]:
        found = [line.split() for line in symbols.splitlines() if line.endswith(' '+name)]
        if len(found) != 1 or found[0][1] != 'T' or struct.unpack_from('<I', image, slot*4)[0] != int(found[0][0], 16) | 1:
            raise ValueError('BENCH_STRONG_VECTOR_MISSING_'+name)
    for name in ['CAN1_RX0_IRQHandler', 'USART3_IRQHandler']:
        if any(line.split()[1] == 'T' for line in symbols.splitlines() if line.endswith(' '+name)):
            raise ValueError('BENCH_FORBIDDEN_NETWORK_HANDLER')
    if any(name in symbols for name in ['MQTT_Connect', 'gateway_connect', 'h3_config_record_valid']):
        raise ValueError('BENCH_NETWORK_OR_CONFIG_LINKED')
    return {'sha256': hashlib.sha256(image).hexdigest(), 'bytes': len(image), 'start': start,
            'end_exclusive': start+len(image), 'erase_sectors': [0], 'load_segments': loads,
            'initial_sp': sp, 'reset_vector': reset, 'mass_erase': False, 'option_bytes_write': False,
            'network': 'NOT_LINKED', 'UART2_vector': 'STRONG', 'hardware': 'NOT_RUN'}
