"""336B台架配置封装；只在仓库外保存，CRC不提供保密或认证。"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

ROOT=Path(__file__).resolve().parents[2]
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


def pack(payload,generation):
    validate_payload(payload)
    if type(generation) is not int or not 1<=generation<=0xFFFFFFFF:raise RecordError('RECORD_GENERATION')
    header=struct.pack('<IHHII',MAGIC,1,24,312,generation)
    return header+struct.pack('<II',zlib.crc32(header+payload),COMMITTED)+payload


def validate(record):
    if len(record)!=336:raise RecordError('RECORD_SIZE')
    magic,version,header,size,generation,crc,commit=struct.unpack_from('<IHHIIII',record)
    if (magic,version,header,size,commit)!=(MAGIC,1,24,312,COMMITTED) or not generation:
        raise RecordError('RECORD_HEADER')
    if crc!=zlib.crc32(record[:16]+record[24:]):raise RecordError('RECORD_CRC')
    validate_payload(record[24:])
    return generation


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--payload',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--generation',type=int,required=True)
    args=parser.parse_args()
    try:
        # 私有输入/输出不能回落版本库；独占创建，不覆盖先前配置或备份。
        for path in (args.payload,args.output):
            if path.resolve().is_relative_to(ROOT):raise RecordError('EXTERNAL_PRIVATE_PATH_REQUIRED')
        record=pack(args.payload.read_bytes(),args.generation)
        import os
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(record)
        print(json.dumps({'exit_code':0,'bytes':len(record),'sha256':hashlib.sha256(record).hexdigest(),
                          'generation':args.generation,'encrypted':False,'flash_written':False}))
        return 0
    except Exception as exc:
        print(json.dumps({'exit_code':1,'failure_code':str(exc) if isinstance(exc,RecordError) else type(exc).__name__}))
        return 1


if __name__=='__main__':raise SystemExit(main())
