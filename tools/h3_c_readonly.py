"""F2当前C原件只读核验；无erase/write/go/自动复位或应用启动入口。"""
import argparse
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess

from gateway.physical_can.bench.flash_c import read_exact,protected_hashes,external_identity,verify_f4_identity
from gateway.physical_can.r2_config_record import validate

ROOT=Path(__file__).resolve().parents[1]
IMAGE='59229f1b34660f053538737fc0fd17c814fde5502a0dfe33603e8e08b72ca8a5'
RECORD='3b1a8c344dfad1d1faa82bc962811e50a467eec9adbc1cec5b2a32979c6a2c25'
FULL='102575dc940425d91b2db7c2a0f22ddf44c5cfab652b1b5ca0790f8924d3705b'
PROTECTED='b5a41c3758763bbec72769fab4a2533bf2db0b6312d93d25a695f9e4b9e02260'
OPTIONS='52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687'


def sha(data):return hashlib.sha256(data).hexdigest()


def plan():
    return {'action':'C_ROM_READ_ONLY','port':'COM15','image_bytes':43172,'image_sha256':IMAGE,
        'record_bytes':336,'record_generation':2,'record_sha256':RECORD,'expected_historical_64k_sha256':FULL,
        'double_read_range':['0x08000000','0x08010000'],'protected_sector_sha256':{'7':PROTECTED,'11':PROTECTED},
        'options_sha256':OPTIONS,'flash_write':False,'RAM_write':False,'automatic_reset':False,'automatic_go':False,
        'support_source_sha256':{name:sha((ROOT/name).read_bytes()) for name in (
            'gateway/physical_can/bench/flash_c.py','gateway/physical_can/r2_flash_c.py',
            'gateway/physical_can/r2_config_record.py','gateway/physical_can/h3_flash_c.py')}}


def authorize(card,identity_source):
    if card.get('auth_id')!='AUTH-AC-C-READONLY' or card.get('approved_by_owner') is not True:
        raise ValueError('C_READ_WINDOW_REQUIRED')
    expiry=datetime.fromisoformat(card['expires_utc'])
    if expiry.tzinfo is None or datetime.now(timezone.utc)>=expiry:raise ValueError('C_READ_WINDOW_EXPIRED')
    if card.get('tool_sha256')!=sha(Path(__file__).read_bytes()) or card.get('plan')!=plan():
        raise ValueError('C_READ_SCOPE_CHANGED')
    if card.get('source_commit')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip():
        raise ValueError('C_READ_SOURCE_CHANGED')
    if identity_source.resolve().is_relative_to(ROOT) or sha(identity_source.read_bytes())!=card.get('identity_source_sha256'):
        raise ValueError('C_EXTERNAL_IDENTITY_CHANGED')
    if card.get('field_state')!='A_OFF_JLINK_ABSENT_CAN_SEPARATED_C_COM15_MANUAL_ROM':
        raise ValueError('C_FIELD_STATE_REQUIRED')


def capture(boot,private):
    options=read_exact(boot,0x1FFFC000,16)
    if options[1]!=0xAA or sha(options)!=OPTIONS:raise RuntimeError('C_OPTIONS_CHANGED_STOP')
    protected=protected_hashes(boot)
    if any(v['sector_sha256']!=PROTECTED for v in protected.values()):raise RuntimeError('C_PROTECTED_CHANGED_STOP')
    first=read_exact(boot,0x08000000,65536);second=read_exact(boot,0x08000000,65536)
    # 先独占落盘保留不匹配原件，再判定；不把配置正文或UID输出到仓库。
    for name,data in (('c-current-first.bin',first),('c-current-second.bin',second)):
        with (private/name).open('xb') as f:f.write(data)
    if first!=second or any((private/name).read_bytes()!=first for name in ('c-current-first.bin','c-current-second.bin')):
        raise RuntimeError('C_DOUBLE_OR_DISK_READ_MISMATCH')
    if sha(first[:43172])!=IMAGE or sha(first[49152:49152+336])!=RECORD or validate(first[49152:49152+336])!=2:
        raise RuntimeError('C_APPLICATION_OR_RECORD_MISMATCH_STOP_NO_REFLASH')
    if sha(first)!=FULL:raise RuntimeError('C_FULL_CURRENT_STATE_DIFFERS_STOP')
    if protected_hashes(boot)!=protected or read_exact(boot,0x1FFFC000,16)!=options:
        raise RuntimeError('C_PROTECTION_CHANGED_DURING_READ_STOP')
    return {'exit_code':0,'gate':'CURRENT_C_ISOLATED_GENERATION2_DOUBLE_READ_MATCH','image_sha256':IMAGE,
        'record_sha256':RECORD,'record_generation':2,'actual_64k_sha256':sha(first),
        'double_read_match':True,'protected_unchanged':True,'options_unchanged':True,
        'flash_write':False,'RAM_write':False,'normal_cold_boot':'NOT_TESTED'}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('plan','read'))
    p.add_argument('--auth',type=Path);p.add_argument('--identity-source',type=Path);p.add_argument('--private-dir',type=Path)
    args=p.parse_args()
    if args.action=='plan':print(json.dumps(plan(),indent=2));return 0
    authorize(json.loads(args.auth.read_text()),args.identity_source)
    private=args.private_dir.resolve()
    if private.is_relative_to(ROOT) or not private.is_dir() or any(private.iterdir()):raise ValueError('EMPTY_RESTRICTED_DIRECTORY_REQUIRED')
    uart=None;raw=io.StringIO();result={'exit_code':1,'gate':'C_READ_STOPPED','flash_write':False,'RAM_write':False}
    try:
        from importlib.metadata import version
        if version('stm32loader')!='0.7.1':raise ValueError('LOADER_VERSION_CHANGED')
        import serial
        from stm32loader.uart import SerialConnection
        from stm32loader.bootloader import Stm32Bootloader
        from gateway.physical_can.r2_flash_c import synchronize_ready_rom
        with redirect_stdout(raw),redirect_stderr(raw):
            uart=serial.Serial(port=None,baudrate=115200,parity='E',timeout=2,write_timeout=2)
            uart.dtr=True;uart.rts=True;uart.port='COM15';uart.open()
            connection=SerialConnection('COM15',115200,'E');connection.serial_connection=uart
            boot=Stm32Bootloader(connection,device_family='F4',verbosity=0)
            # 只同步现场手动进入的ROM，不脉冲RESET/BOOT，不调用任何写入型Bootloader方法。
            synchronize_ready_rom(uart,boot);verify_f4_identity(boot,external_identity(args.identity_source))
            result=capture(boot,private)
    except Exception as error:
        result['failure_type']=type(error).__name__
    finally:
        if uart is not None:
            try:uart.close()
            except Exception:result.update(exit_code=1,close_failed=True)
        (private/'loader-private.log').write_text(raw.getvalue())
        (private/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
