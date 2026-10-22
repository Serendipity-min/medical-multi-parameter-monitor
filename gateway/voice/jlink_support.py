"""P6语音台架的最小维护依赖，提取自已验H3代码；导入不连接板卡。

只保留角色/保护区读取与白名单Bridge；不移入旧H3的烧录CLI、网络或配置写入入口。
"""
import ast
import hashlib
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
from stm32loader.bootloader import Stm32Bootloader

JLINK=Path('D:/keil/ARM/Segger/JLink.exe')
expected=SimpleNamespace(OPTIONS='52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687', PROTECTED='b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260')

class GateError(RuntimeError):
    """异常消息只用预定义状态码，不携带任何原始读回数据。"""


def external_identity(path):
    # literal_eval只读取声明值，不执行外部脚本，且不输出UID。
    tree=ast.parse(path.read_text(encoding='utf-8'))
    wanted={}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            for target in n.targets:
                if isinstance(target,ast.Name) and target.id in ('EXPECTED_UID','EXPECTED_CHIP_ID'):
                    wanted[target.id]=ast.literal_eval(n.value)
    if set(wanted)!=set(('EXPECTED_UID','EXPECTED_CHIP_ID')):raise GateError('IDENTITY_SOURCE_INVALID')
    return wanted


def sha(data):return hashlib.sha256(data).hexdigest()


class Bridge:
    def __init__(self,private):self.private=private;self.index=0;self.voltages=[];self.download_observation='NO_LOAD_REQUEST'
    def validate_commands(self,commands,write=False):
        # 子类只能显式扩展维护事务；旧隔离入口维持原命令白名单。
        allowed=('savebin ','loadbin ','verifybin ','w4 0xE0042008 ') if write else ('savebin ',)
        if not all(s in ('connect','h','q') or s.startswith(allowed) for s in commands):
            raise ValueError('COMMAND_OUTSIDE_C_SCOPE')
    def execute(self,commands,write=False):
        self.validate_commands(commands,write)
        self.index+=1;text='\n'.join(commands)+'\n';stem=self.private/('jlink-'+str(self.index))
        with stem.with_suffix('.commands').open('x') as f:f.write(text)
        r=subprocess.run([str(JLINK),'-device','STM32F407ZG','-if','SWD','-speed','1000'],
            input=text.encode('ascii'),capture_output=True,timeout=90,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        raw=r.stdout+r.stderr;stem.with_suffix('.raw.log').write_bytes(raw)
        if any(s.startswith('loadbin ') for s in commands):
            # loadbin提交不等于物理擦写；SEGGER对相同内容会跳过，必须如实区分。
            self.download_observation=('SKIPPED_IDENTICAL' if b'flash download skipped. flash contents already match' in raw.lower()
                else 'NOT_DETERMINED_FROM_SDK_LOG')
        match=re.search(rb'VTref\s*=\s*([0-9.]+)V',raw)
        if r.returncode:raise RuntimeError('JLINK_PROCESS_NONZERO')
        if not match or not 3.0<=float(match[1])<=3.6:raise RuntimeError('C_VTREF_NOT_VERIFIED_STOP')
        self.voltages.append(float(match[1]))


class Window:
    def __init__(self,private,bridge,identity):self.private=private;self.bridge=bridge;self.identity=identity

    def read(self,label,specs,extra=()):
        commands=['connect','h',*extra]
        for name,address,length in specs:
            p=self.private/(label+'-'+name+'.bin')
            if p.exists() or any(c in p.as_posix() for c in (' ', ',', '\n','\r')):
                raise ValueError('C_PRIVATE_PATH_OCCUPIED_OR_INVALID')
            commands.append(f'savebin {p.as_posix()}, {hex(address)}, {hex(length)}')
        self.bridge.execute([*commands,'q'],write=bool(extra))
        result={}
        for name,_,length in specs:
            data=(self.private/(label+'-'+name+'.bin')).read_bytes()
            if len(data)!=length:raise RuntimeError('C_JLINK_READ_LENGTH_MISMATCH')
            result[name]=data
        return result

    def identity_read(self,label):
        data=self.read(label,[('chip',0xE0042000,4),('size',0x1FFF7A22,2),
            ('uid',0x1FFF7A10,12),('options',0x1FFFC000,16),('freeze',0xE0042008,4),
            ('boot-alias',0x00000000,8),('system-rom',0x1FFF0000,8)])
        if int.from_bytes(data['chip'],'little')&0xFFF!=int(self.identity['EXPECTED_CHIP_ID'],16) or int.from_bytes(data['size'],'little')!=1024:
            raise RuntimeError('C_JLINK_CHIP_OR_CAPACITY_MISMATCH')
        if Stm32Bootloader.format_uid(data['uid'])!=self.identity['EXPECTED_UID']:
            raise RuntimeError('C_JLINK_UID_MISMATCH_STOP')
        if data['options'][1]!=0xAA or sha(data['options'])!=expected.OPTIONS:
            raise RuntimeError('C_JLINK_OPTIONS_MISMATCH_STOP')
        return data

    def protection(self,label):
        data=self.read(label,[('sector7',0x08060000,0x20000),('sector11',0x080E0000,0x20000),
            ('options',0x1FFFC000,16)])
        if any(sha(data[k])!=expected.PROTECTED for k in ('sector7','sector11')) or sha(data['options'])!=expected.OPTIONS:
            raise RuntimeError('C_JLINK_PROTECTION_MISMATCH_STOP')
        return data
