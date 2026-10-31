"""三板联调备份薄入口：复用只读SDK与CPU检查；无签名、nonce或目标写入。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import c_b4_readonly as ro


def backup(board,out):
    out.mkdir();probe=out/'probe';probe.mkdir();link=None
    result={'board':board,'status':'STOP','exit_code':1,'target_writes':0,'native_side_effects':'UNRESOLVED'}
    try:
        link=ro.CReadLink(probe);link.open()
        ident=ro.raw.identity(link);ro.raw.check_identity(ident)
        ro.raw.write_json(probe/'identity-private.json',ident)
        if board=='B':
            ro.require(ident['uid_hex']==json.loads(ro.B_REFERENCE.read_text())['uid_hex'],'ABC_PROBE_IS_NOT_KNOWN_B')
        ro.raw.write_json(probe/'entry-sticky-private.json',{'DHCSR':link.u32(ro.SYSTEM['DHCSR'])})
        state=ro.snapshot(link);ro.raw.write_json(probe/'entry-state-private.json',state);ro.check_running(link,state)
        link.set_close_resume(True)
        full=[];options=[]
        for n in (1,2):
            o=link.read(0x1fffc000,16);data=link.read(0x08000000,1048576)
            (probe/f'flash-{n}-private.bin').write_bytes(data);(probe/f'options-{n}-private.bin').write_bytes(o)
            full.append(data);options.append(o)
            state=ro.snapshot(link);ro.raw.write_json(probe/f'after-{n}-state-private.json',state);ro.check_running(link,state)
        ro.require(full[0]==full[1] and options[0]==options[1],'ABC_BACKUP_DOUBLE_READ_MISMATCH')
        after=ro.raw.identity(link);ro.raw.write_json(probe/'identity-after-private.json',after)
        ro.require(after==ident,'ABC_IDENTITY_DRIFT')
        sp=int.from_bytes(full[0][:4],'little');reset=int.from_bytes(full[0][4:8],'little')
        ro.require(0x20000000<sp<=0x20020000 and reset&1 and 0x08000000<reset<0x08100000,'ABC_BACKUP_VECTOR_INVALID')
        if board=='A':
            b_ident=json.loads(ro.B_REFERENCE.read_text())
            ro.require(ident['uid_hex']!=b_ident['uid_hex'],'ABC_PROBE_IS_KNOWN_B')
        result.update(status='ABC_BOARD_DOUBLE_READ_BACKUP_PASS',exit_code=0,bytes=1048576,
            full_sha256=ro.digest(full[0]),options_sha256=ro.digest(options[0]),independent_reads_match=True,
            existing_vectors_plausible=True,role_basis='CURRENT_OWNER_PHYSICAL_ROUTE',
            app_64KiB_sha256=ro.digest(full[0][:65536]),outside_64KiB_sha256=ro.digest(full[0][65536:]),
            sector3_sha256=ro.digest(full[0][49152:65536]))
    except (Exception,KeyboardInterrupt) as error:
        if link:link.verified_running_flash=False
        ro.raw.write_json(out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(error_type=type(error).__name__,error_sha256=ro.digest(str(error).encode()))
    finally:
        if link:
            try:link.close();result['Close_completed']=True
            except Exception as error:result.update(exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
        ro.raw.write_json(out/'receipt-private.json',result)
    print(json.dumps(result));return result['exit_code']


def supervise(cmd,out):
    started=time.monotonic();reason=None
    with out.with_name(out.name+'-worker.log').open('xb') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        try:
            while child.poll() is None:
                if (out/'STOP').exists():reason='OWNER_STOP'
                if time.monotonic()-started>180:reason='BACKUP_SESSION_TIMEOUT'
                heartbeat=out/'probe/heartbeat-events.jsonl'
                if heartbeat.exists():
                    lines=heartbeat.read_text().rsplit('\n',1)[0].splitlines()
                    if lines:
                        event=json.loads(lines[-1])
                        if event.get('active') and time.monotonic()>event['deadline_monotonic']:reason='SDK_TIMEOUT'
                if reason:child.kill();break
                time.sleep(.05)
        finally:
            if child.poll() is None:child.kill()
            native=child.wait(timeout=5)
    out.mkdir(exist_ok=True);ro.raw.write_json(out/'supervisor-private.json',{'worker_native_exit_code':native,'reason':reason})
    print(json.dumps({'worker_native_exit_code':native,'stop_reason':reason}))
    return 4 if reason else native


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=('A','B','C'),required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true')
    a=p.parse_args()
    if not(a.execute or a.worker):print('BACKUP_NOT_STARTED');return 0
    out=a.out.resolve();ro.require(out.parent.is_relative_to(Path('E:/medical-monitor-node-b-precan-private/20261023')),'ABC_PRIVATE_ROOT')
    ro.require(out.parent.stat().st_file_attributes&0x4000 and not out.exists(),'ABC_PRIVATE_OUTPUT')
    if a.worker:return backup(a.board,out)
    return supervise([sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--board',a.board,'--out',str(out)],out)


if __name__=='__main__':raise SystemExit(main())
