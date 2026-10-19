"""C的ROM只读预检：固定COM15，外部身份比较，保护区只输出摘要。"""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from gateway.physical_can.bench.flash_c import external_identity,verify_f4_identity,read_exact,protected_hashes


def main():
    from stm32loader.uart import SerialConnection
    from stm32loader.bootloader import Stm32Bootloader
    private=Path('E:/medical-monitor-h3-private')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    result={'action':'C_READ_ONLY_ROM_PREFLIGHT','flash_write_started':False,'exit_code':1,'stage':'EXTERNAL_INPUTS'}
    capture=io.StringIO();connection=None
    try:
        identity=external_identity(Path('E:/stm32/ai_serial_console/tools/flash.py'))
        previous=Path('E:/medical-monitor-node-a/gateway/physical_can/build/h2r/can_only_bench.bin').read_bytes()
        if hashlib.sha256(previous).hexdigest()!='79a5ddf9a49fe592f22f625269ef7fd88e1578aa36b1229477aa8b943eb35be5':
            raise ValueError('PREVIOUS_IMAGE_IDENTITY_CHANGED')
        connection=SerialConnection('COM15',115200,'E');connection.reset_active_high=True;connection.boot0_active_low=True
        with redirect_stdout(capture),redirect_stderr(capture):
            result['stage']='CONNECT_ROM';connection.connect();boot=Stm32Bootloader(connection,device_family='F4',verbosity=0)
            boot.reset_from_system_memory();boot.get()
            result['stage']='IDENTITY';verify_f4_identity(boot,identity);result['C_identity_match']=True
            options=read_exact(boot,0x1FFFC000,16)
            result['RDP_level_zero']=options[1]==0xAA
            if not result['RDP_level_zero']:raise ValueError('RDP_NOT_ZERO')
            result['stage']='APPLICATION_COMPARE'
            current=read_exact(boot,0x08000000,len(previous))
            if current!=previous:raise ValueError('CURRENT_C_APPLICATION_MISMATCH')
            result['application']={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest(),'H2R_match':True}
            result['stage']='PROTECTED_READ';result['protected']=protected_hashes(boot)
            config=read_exact(boot,0x080E0000,312)
            result['config']={'all_ff':all(c==255 for c in config),'magic_valid':int.from_bytes(config[:4],'little')==0x31435747,'bytes':312}
            result['options_sha256']=hashlib.sha256(options).hexdigest()
            result['stage']='APPLICATION_ROLLBACK_READ'
            # 只保存此次候选可能覆盖的sector0..2，绝不声称C整片可恢复。
            original=read_exact(boot,0x08000000,0xC000)
            backup=private/('c-sector0-2-'+stamp+'.bin');backup.write_bytes(original)
            result['application_backup']={'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest(),'private_file':backup.name,'sectors':[0,1,2]}
            connection.enable_reset(True)
        result.update(exit_code=0,stage='READ_ONLY_COMPLETE_RESET_ASSERTED_BEFORE_CLOSE')
    except BaseException as exc:
        result['failure_type']=type(exc).__name__
        # 底层异常可能含设备ID，只落受限目录，公开结果仅保存阶段和类型。
        capture.write('\n'+repr(exc))
    finally:
        if connection and connection.serial_connection:connection.serial_connection.close()
        (private/('c-read-'+stamp+'.raw.log')).write_text(capture.getvalue(),encoding='utf-8')
        (ROOT/'gateway/physical_can/evidence/h3'/('c-read-'+stamp+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
