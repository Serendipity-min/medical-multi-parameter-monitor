"""联网IRQ候选的离线下载计划：从ELF实际加载段核对，不凭文件名推断擦除范围。"""
import hashlib
import struct
import subprocess

START = 0x08000000
LIMIT = 0x08060000  # sector7起点，配置扇区7/11均不可进入应用加载范围。
BOUNDARIES = [START, START+0x4000, START+0x8000, START+0xC000,
              START+0x10000, START+0x20000, START+0x40000, LIMIT]


def inspect(elf, binary, nm):
    data, image = elf.read_bytes(), binary.read_bytes()
    if data[:7] != b'\x7fELF\x01\x01\x01' or struct.unpack_from('<H', data, 18)[0] != 40:
        raise ValueError('H3_ELF_NOT_ARM32_LE')
    phoff = struct.unpack_from('<I', data, 28)[0]
    entsize, count = struct.unpack_from('<HH', data, 42)
    loads = []
    for i in range(count):
        kind, offset, virtual, physical, size, memory, flags, align = struct.unpack_from('<8I', data, phoff+i*entsize)
        if kind != 1 or not size:
            continue
        if not START <= physical < physical+size <= LIMIT:
            raise ValueError('H3_LOAD_TOUCHES_PROTECTED_OR_NONFLASH')
        if image[physical-START:physical-START+size] != data[offset:offset+size]:
            raise ValueError('H3_ELF_BIN_MISMATCH')
        loads.append({'start': physical, 'end_exclusive': physical+size, 'bytes': size})
    if not loads or not 0 < len(image) <= LIMIT-START or max(p['end_exclusive'] for p in loads) != START+len(image):
        raise ValueError('H3_IMAGE_EXTENT_MISMATCH')
    sp, reset = struct.unpack_from('<II', image)
    if not 0x20000000 < sp <= 0x20020000 or sp%8 or not reset&1 or not START <= reset-1 < START+len(image):
        raise ValueError('H3_BAD_VECTOR')
    symbols = subprocess.check_output([str(nm), '-g', str(elf)], text=True)
    handlers = [line.split() for line in symbols.splitlines() if line.endswith(' CAN1_RX0_IRQHandler')]
    vector = struct.unpack_from('<I', image, (16+20)*4)[0]
    if len(handlers) != 1 or handlers[0][1] != 'T' or vector != int(handlers[0][0], 16)|1:
        raise ValueError('H3_IRQ_NOT_STRONG_VECTOR')
    # 擦除按实际Flash扇区交集计算，不能将16KiB公式用于sector4及以后的非等长扇区。
    sectors = [i for i in range(7) if BOUNDARIES[i] < START+len(image)]
    return {'sha256': hashlib.sha256(image).hexdigest(), 'bytes': len(image),
            'start': START, 'end_exclusive': START+len(image), 'erase_sectors': sectors,
            'load_segments': loads, 'initial_sp': sp, 'reset_vector': reset,
            'CAN1_RX0_vector': {'address': vector, 'strong_handler': True},
            'protected_sectors': [7, 11], 'mass_erase': False, 'option_bytes_write': False}
