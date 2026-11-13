"""只比较既有ELF32制品文件；不调用SDK、编译器或设备。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct

SHA=lambda data:hashlib.sha256(data).hexdigest()


def sections(raw):
    if raw[:6]!=b'\x7fELF\x01\x01':raise ValueError('ELF32_LE_REQUIRED')
    offset=struct.unpack_from('<I',raw,32)[0]
    entry,count,names=struct.unpack_from('<HHH',raw,46)
    rows=[struct.unpack_from('<IIIIIIIIII',raw,offset+i*entry) for i in range(count)]
    strings=raw[rows[names][4]:rows[names][4]+rows[names][5]]
    result={}
    for row in rows:
        name=strings[row[0]:].split(b'\0',1)[0].decode('ascii')
        data=raw[row[4]:row[4]+row[5]] if row[1]!=8 else b''
        result[name]=(row[2],row[3],row[5],data,row[4])
    return result


def comment_tokens(data):
    return [re.sub(rb'^p[0-9a-f]+-[0-9]+$',b'<COMPILER_TEMP_MARKER>',part)
            for part in data.split(b'\0') if part]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--old-build',type=Path,action='append',required=True)
    parser.add_argument('--new-build',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    new_elf=(args.new_build/'firmware/OBJ/BIO_V2.axf').read_bytes()
    new_sections=sections(new_elf)
    new_receipt=json.loads((args.new_build/'receipt.json').read_text())
    new_symbols=(args.new_build/'symbols.txt').read_bytes()
    normalize=lambda data:re.sub(rb'b4-arm-\d{8}T\d{12}Z',b'<BUILD_DIRECTORY>',data)
    comparisons=[]
    for old in args.old_build:
        elf=(old/'firmware/OBJ/BIO_V2.axf').read_bytes();old_sections=sections(elf)
        changed=[name for name in sorted(set(old_sections)|set(new_sections)) if old_sections.get(name)!=new_sections.get(name)]
        allocated_equal=all(old_sections.get(name)==new_sections.get(name) for name in set(old_sections)|set(new_sections)
                            if (old_sections.get(name) or new_sections[name])[0]&2)
        old_receipt=json.loads((old/'receipt.json').read_text())
        oc=old_sections['.comment'];nc=new_sections['.comment']
        old_without_comment=elf[:oc[4]]+bytes(oc[2])+elf[oc[4]+oc[2]:]
        new_without_comment=new_elf[:nc[4]]+bytes(nc[2])+new_elf[nc[4]+nc[2]:]
        comparisons.append({'old_build':old.name,'new_build':args.new_build.name,
            'old_axf_sha256':SHA(elf),'new_axf_sha256':SHA(new_elf),
            'changed_sections':changed,'all_allocated_sections_equal':allocated_equal,
            'all_file_bytes_outside_comment_equal':old_without_comment==new_without_comment,
            'comment_equal_after_null_padding_and_temp_marker_normalization':comment_tokens(old_sections['.comment'][3])==comment_tokens(new_sections['.comment'][3]),
            'comment_token_multisets_equal_after_normalization':Counter(comment_tokens(oc[3]))==Counter(comment_tokens(nc[3])),
            'symbols_equal_after_build_directory_normalization':normalize((old/'symbols.txt').read_bytes())==normalize(new_symbols),
            'compile_input_hashes_equal':old_receipt['source_sha256']==new_receipt['source_sha256']})
    ok=all(x['all_allocated_sections_equal'] and x['changed_sections']==['.comment'] and
           x['all_file_bytes_outside_comment_equal'] and x['comment_token_multisets_equal_after_normalization'] and
           x['symbols_equal_after_build_directory_normalization'] and x['compile_input_hashes_equal'] for x in comparisons)
    result={'status':'NONALLOCATED_METADATA_DIFFERENCE_CONFIRMED' if ok else 'DIFFERENCE_REQUIRES_REVIEW',
            'exit_code':0 if ok else 1,'comparisons':comparisons,'tool_sha256':SHA(Path(__file__).read_bytes()),
            'limit':'Raw hashes remain different; do not replace frozen runtime bindings without PI review'}
    with args.out.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
    return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
