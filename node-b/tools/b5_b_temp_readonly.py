"""温度新B候选一次15秒只读接收核验；独立90秒监督，不发送UART字节。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import time
import b5_b_temp_update as update
import b4_runtime as base
import b5_sector3_write_supervisor as supervisor
from live_state_b import LiveLink
from resp_exploratory import decode

recovery=update.recovery;ro=update.ro;raw=update.app.raw;require=update.require;sha=update.sha
SCOPE='B5_B_TEMP_15S_READONLY'
READS={a:set(n) for a,n in ro.READS.items()}
RAM={'bio':(0x20001d20,120),'adc':(0x20000614,48),'registers':(0x20000644,12),
     'CAN':(0x2000377c,44),'temperature':(0x20004c78,64)}
for a,n in RAM.values():READS.setdefault(a,set()).add(n)

def bindings():
    return {**update.bindings(),'b5_b_temp_readonly.py':sha(Path(__file__).read_bytes()),
            'b4_runtime.py':sha(Path(base.__file__).read_bytes()),'resp_exploratory.py':sha(Path(decode.__code__.co_filename).read_bytes())}

def authorize(a,out):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'TEMP_RO_OWNER')
    require(a.get('tools_sha256')==bindings() and a.get('DLL_sha256')==raw.DLL_SHA,'TEMP_RO_TOOLS')
    require(a.get('card_sha256')==sha(update.CARD.read_bytes()),'TEMP_RO_CARD')
    require(a.get('session_timeout_s')==90 and a.get('seconds')==15 and a.get('probe_sessions')==1 and
            a.get('retries')==0 and a.get('expires_unix',0)>time.time(),'TEMP_RO_BUDGET')
    require(Path(a.get('output','')).resolve()==out.resolve(),'TEMP_RO_OUTPUT')
    b,m,files=update.load_binding(a['binding'],a['binding_sha256'])
    blob=recovery.read(Path(a['install_receipt']),False);proof=json.loads(blob)
    require(sha(blob)==a['install_receipt_sha256'] and proof.get('exit_code')==0 and proof.get('Close_completed') and
            proof.get('status')=='B_TEMP_INSTALL_FULL_VERIFY_AND_FLASH_BOOT_PASS' and
            proof.get('full_flash_sha256')==b['after_full_sha256'],'TEMP_RO_INSTALL_REQUIRED')
    recovery.protected(out.parent,False)
    return b,m,files

class Link(LiveLink):
    def call(self,name,*args,timeout=5):
        require(name in base.runtime.CALLS-{'JLINKARM_GetRegisterList','JLINKARM_GetRegisterName','JLINKARM_ReadReg'},'TEMP_RO_API')
        require(self.sdk_calls<3000,'TEMP_RO_SDK_BUDGET')
        if name=='JLINKARM_ExecCommand':
            cmd=args[0].decode('ascii')
            require(cmd in base.runtime.COMMANDS or cmd=='SetRestartOnClose = 1','TEMP_RO_COMMAND')
            if cmd=='SetRestartOnClose = 1':require(self.verified_running_flash,'TEMP_RO_CLOSE')
        if name=='JLINKARM_ReadMemEx':require(args[1] in READS.get(args[0],set()) and args[3]==0,'TEMP_RO_ADDRESS')
        self.sdk_calls+=1
        return raw.Link.call(self,name,*args,timeout=timeout)
    def read(self,address,size):
        require(size in READS.get(address,set()),'TEMP_RO_ADDRESS')
        data=(C.c_uint8*size)();n=self.call('JLINKARM_ReadMemEx',address,size,data,0,timeout=45 if size==1048576 else 5)
        require(n==size,'TEMP_RO_SHORT_READ');return bytes(data)

def decode_temp(blob):
    require(len(blob)==64,'TEMP_RO_DIAG_SIZE')
    names='received overflow uart_errors frames checksum_errors header_errors last_ms object_centi ambient_centi body_centi emissivity used present'.split()
    result=dict(zip(names,struct.unpack_from('<7I3H3B',blob)))
    result['last_frame_hex']=blob[49:61].hex()
    return result

def worker(a,auth_path,out,b,m,files):
    mark=json.loads(recovery.read(auth_path.with_suffix('.used'),False))
    require(mark['authorization_sha256']==sha(recovery.read(auth_path,False)),'TEMP_RO_SINGLE_USE')
    out.mkdir(exist_ok=False);recovery.protected(out,False);link=None;rows=[]
    result={'status':'STOP','exit_code':1,'explicit_reset_halt_go_target_writes':0,'UART_commands':0}
    try:
        link=Link(ro.DLL,out);link.started=min(link.started,mark['started_monotonic']);link.open()
        ident=raw.identity(link);require(ident==json.loads(files['identity-private.json']),'TEMP_RO_IDENTITY')
        raw.write_json(out/'identity-private.json',ident)
        raw.write_json(out/'entry-sticky-private.json',{'DHCSR':link.u32(ro.SYSTEM['DHCSR'])})
        state=ro.snapshot(link);raw.write_json(out/'entry-state-private.json',state);ro.check_running(link,state)
        link.set_close_resume(True)
        full=link.read(0x08000000,1048576);options=link.read(0x1fffc000,16)
        update.app.save(out,'full-private.bin',full);update.app.save(out,'options-private.bin',options)
        require(full==files['expected-full-private.bin'] and options==files['options-private.bin'],'TEMP_RO_FULL_OPTIONS')
        started=time.monotonic()
        while time.monotonic()-started<15:
            ro.check_running(link,ro.snapshot(link))
            blobs={name:link.read(*where) for name,where in RAM.items()}
            n=len(rows)
            for name,blob in blobs.items():update.app.save(out,str(n)+'-'+name+'-private.bin',blob)
            bio=decode(blobs['bio'],blobs['adc'],blobs['registers'])
            require(bio['adc']['init_errors']==0,'TEMP_RO_ADC_INIT')
            rows.append({'host_monotonic':time.monotonic(),'temperature':decode_temp(blobs['temperature']),
                         'bio':bio,'CAN':dict(zip(base.CAN_FIELDS,struct.unpack('<11I',blobs['CAN'])))})
            time.sleep(.2)
        raw.write_json(out/'observations-private.json',rows)
        require(len(rows)>20 and rows[-1]['bio']['samples']>rows[0]['bio']['samples'],'TEMP_RO_SAMPLING_STALLED')
        ro.check_running(link,ro.snapshot(link));link.set_close_resume(True)
        new=rows[-1]['temperature']['frames']-rows[0]['temperature']['frames']
        result.update(status='B_TEMP_READONLY_CAPTURED' if new else 'B_TEMP_NO_NEW_VALID_FRAMES',exit_code=0 if new else 3,
                      observations=len(rows),new_valid_frames=new,
                      temperature_quantity='NONHUMAN_OBJECT_SURFACE_UNCALIBRATED',full_flash_sha256=sha(full))
    except BaseException as e:
        if link:link.verified_running_flash=False
        result.update(status='STOP',exit_code=1,error_type=type(e).__name__,error_text_sha256=sha(str(e).encode()))
        raw.write_json(out/'failure-private.json',{'reason':str(e)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
                link.close();result['Close_completed']=True
            except BaseException as e:result.update(exit_code=1,Close_completed=False,close_error=type(e).__name__)
            result.update(sdk_calls=link.sdk_calls,close_resume=link.close_resume_enabled)
        raw.write_json(out/'receipt-private.json',result)
    print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}));return result['exit_code']

def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');args=p.parse_args()
    if not args.execute and not args.worker:print(json.dumps({'enabled':False,'scope':SCOPE}));return 0
    require(args.authorization and args.out,'TEMP_RO_AUTH_REQUIRED')
    a=json.loads(recovery.read(args.authorization,False));b,m,files=authorize(a,args.out)
    if args.worker:return worker(a,args.authorization,args.out,b,m,files)
    return supervisor.supervise(args.authorization,args.out,backend=__import__(__name__))

if __name__=='__main__':raise SystemExit(main())
