"""单次C授权窗口：诊断握手/复位后仅核验身份并备份，绝不发送Flash写指令。"""
from pathlib import Path
from datetime import datetime,timezone
from contextlib import redirect_stdout,redirect_stderr
import io,json,sys,time
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root))
from gateway.physical_can import r2_flash_c as gate
from gateway.physical_can.bench.flash_c import external_identity,verify_f4_identity,GateError
from gateway.esp_at_probe.build import LIBRARY
reference=json.loads(Path('E:/medical-monitor-h3-private/r2-current-window-reference.json').read_text())
work=Path(reference['private_dir']);window=json.loads((work/'owner-window.json').read_text())
manifest=json.loads((root/'gateway/physical_can/evidence/h3-r2/persistent-isolated/isolated-arm-result.json').read_text())
image=(root/'gateway/physical_can/build/h3-r2-persistent-isolated/gateway_physical_can.bin').read_bytes()
record=Path(reference['record']).read_bytes();plan=gate.offline_plan(manifest,image,record)
identity_path=Path('E:/stm32/ai_serial_console/tools/flash.py')
gate.check_window(window,'backup',plan,reference['source_commit'],gate.sha(identity_path.read_bytes()))
gate.verify_sources(manifest,reference['source_commit'],LIBRARY)
if any((work/n).exists() for n in ('baseline.json','c-sector0-3-first.bin','c-sector0-3-second.bin')):raise GateError('BACKUP_ALREADY_PRESENT')
out=root/'gateway/physical_can/evidence/h3-r2/c-window'
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');target=out/('controlled-rom-backup-'+stamp+'.json')
result={'role':'C','action':'CONTROLLED_ROM_RESET_READ_ONLY_BACKUP','exit_code':1,'flash_write_started':False,'normal_cold_boot':'NOT_TESTED'}
def save(stage):
    result['stage']=stage;target.write_text(json.dumps(result,indent=2));print(stage,flush=True)
capture=io.StringIO();uart=None
try:
    from importlib.metadata import version
    if version('stm32loader')!='0.7.1':raise GateError('LOADER_VERSION_CHANGED')
    import serial
    from stm32loader.uart import SerialConnection
    from stm32loader.bootloader import Stm32Bootloader
    save('READ_ONLY_SERIAL_DIAGNOSTIC')
    with redirect_stdout(capture),redirect_stderr(capture):
        uart=serial.Serial(port=None,baudrate=115200,parity='E',timeout=.3,write_timeout=2)
        uart.dtr=True;uart.rts=True;uart.port='COM15';uart.open();time.sleep(.3)
        raw=uart.read(256)
        result['passive_even']={'bytes':len(raw),'known_gateway_marker':b'GW ' in raw,'ack_seen':b'\x79' in raw,'nack_seen':b'\x1f' in raw}
        uart.parity='N';raw=uart.read(256)
        result['passive_none']={'bytes':len(raw),'known_gateway_marker':b'GW ' in raw}
        uart.parity='E';uart.timeout=2
        connection=SerialConnection('COM15',115200,'E');connection.serial_connection=uart
        # 复用此前成功C下载的极性，只对RESET做一次脉冲，RTS保持原True不改变BOOT接线。
        connection.reset_active_high=True;connection.boot0_active_low=True
        connection.enable_reset(True);time.sleep(.1);connection.enable_reset(False)
        result['controlled_reset_sent']=True
        boot=Stm32Bootloader(connection,device_family='F4',verbosity=0)
        gate.synchronize_ready_rom(uart,boot)
        verify_f4_identity(boot,external_identity(identity_path))
        result['C_identity_match']=True
    save('C_IDENTITY_VERIFIED_READING_BACKUP_AND_PROTECTION')
    with redirect_stdout(capture),redirect_stderr(capture):
        previous=json.loads((root/'gateway/physical_can/evidence/h3/c-download-20261020T074926Z.json').read_text())
        backup=gate.capture_backup(boot,previous,work,gate.sha(identity_path.read_bytes()))
        with (work/'baseline.json').open('x') as f:json.dump(backup,f,indent=2)
    result.update(exit_code=0,backup={k:v for k,v in backup.items() if k!='private_files'})
    save('BACKUP_VERIFIED_NO_FLASH_WRITE')
except BaseException as exc:
    result['failure_code']=str(exc) if isinstance(exc,GateError) else type(exc).__name__
finally:
    if uart:uart.close()
    target.write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
raise SystemExit(result['exit_code'])
