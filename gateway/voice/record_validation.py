"""P6语音只读配置完整性校验；不提供配置生成/写入或Wi-Fi替换入口。"""
import struct
import zlib
MAGIC=0x32433348
COMMITTED=0x54494D43

class RecordError(ValueError):
    """固定错误码，不包含凭据或配置片段。"""


def validate_payload(payload):
    if len(payload)!=312 or struct.unpack_from('<I',payload)[0]!=0x31435747:
        raise RecordError('PAYLOAD_LAYOUT')
    if struct.unpack_from('<I',payload,4)[0]<1700000000:raise RecordError('PAYLOAD_TIME_FLOOR')
    offset=8
    for index,size in enumerate((33,65,65,33,65,41)):
        field=payload[offset:offset+size];offset+=size
        if field[-1] or (index!=1 and not field[0]):raise RecordError('PAYLOAD_FIELD')
        value=field.split(b'\0')[0]
        if any(c<32 or c in (34,92) for c in value):raise RecordError('PAYLOAD_AT_ESCAPE')
    # 原结构尾部两字节是对齐padding；封装时固定为零，避免把未初始化RAM落盘。
    if payload[310:]!=b'\0\0':raise RecordError('PAYLOAD_PADDING')


def validate(record):
    if len(record)!=336:raise RecordError('RECORD_SIZE')
    magic,version,header,size,generation,crc,commit=struct.unpack_from('<IHHIIII',record)
    if (magic,version,header,size,commit)!=(MAGIC,1,24,312,COMMITTED) or not generation:
        raise RecordError('RECORD_HEADER')
    if crc!=zlib.crc32(record[:16]+record[24:]):raise RecordError('RECORD_CRC')
    validate_payload(record[24:])
    return generation
