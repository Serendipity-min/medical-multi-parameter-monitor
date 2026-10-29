"""B温度工程候选sector0/1/2单事务安装；默认禁用，不接C或云。"""
import argparse
import json
from pathlib import Path
import time
import b4_recovery as recovery
import b4_swd_install as app
import b5_sector3_write_supervisor as supervisor
ro=app.readonly

ROOT=Path(__file__).resolve().parents[2]
SCOPE='B5_B_TEMP_APP012_UPDATE'
CARD=ROOT/'node-b/docs/AUTH-B5-TEMP-AND-SEPARATE-CHANNELS-001-R1.md'
BEFORE_BIN='676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82'
CANDIDATE_BIN='a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2'
require=recovery.require
sha=recovery.digest

def bindings():
    return {**app.bindings(),'b5_b_temp_update.py':sha(Path(__file__).read_bytes()),
            'b5_sector3_write_supervisor.py':sha(Path(supervisor.__file__).read_bytes())}

def load_binding(path,expected_sha,synthetic=False):
    blob=recovery.read(Path(path),synthetic);require(sha(blob)==expected_sha,'TEMP_BINDING_SHA')
    b=json.loads(blob);m,files=recovery.load_package(Path(b['package']),b['manifest_sha256'],synthetic)
    require(m['board_role']=='B' and m['sectors']==[0,1,2],'TEMP_SECTORS')
    require(m['candidate_bytes']==40928 and m['candidate_sha256']==CANDIDATE_BIN,'TEMP_CANDIDATE')
    require(sha(files['before-full-private.bin'][:39948])==BEFORE_BIN,'TEMP_BEFORE_BIN')
    require(b['before_full_sha256']==m['files']['before-full-private.bin']['sha256'] and
            b['after_full_sha256']==m['files']['expected-full-private.bin']['sha256'],'TEMP_FULL_BINDING')
    return b,m,files

def authorize(a,out):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE,'TEMP_OWNER_REQUIRED')
    require(a.get('phase')=='install','TEMP_INSTALL_ONLY_NO_AUTORESTORE')
    require(a.get('tools_sha256')==bindings() and a.get('DLL_sha256')==app.raw.DLL_SHA,'TEMP_TOOL_SHA')
    require(a.get('card_sha256')==sha(CARD.read_bytes()),'TEMP_CARD_SHA')
    require(a.get('session_timeout_s')==180 and a.get('probe_sessions')==1 and a.get('retries')==0 and
            a.get('expires_unix',0)>time.time(),'TEMP_BUDGET')
    require(Path(a.get('output','')).resolve()==out.resolve(),'TEMP_OUTPUT')
    blob=recovery.read(Path(a['site_record']),False)
    require(sha(blob)==a.get('site_record_sha256'),'TEMP_SITE_SHA')
    site=json.loads(blob)
    require(all(site.get(k) is True for k in ('JLink_on_B','B_J5','C_unchanged_STOPPED',
            'ESP_present_powered_exception','CAN_GND_BOOT_unchanged','module_3V3_GND_RC_PC10_TD_PC11',
            'no_other_program','no_human')),'TEMP_SITE_INCOMPLETE')
    require(a.get('B5START')==0 and a.get('sector3_options_writes')==0,'TEMP_SCOPE')
    recovery.protected(out.parent,False)
    return load_binding(a['binding'],a['binding_sha256'])

class InstallLink(app.InstallLink):
    def read(self,address,size):
        first=super().read(address,size)
        if (address,size) in ((0x08000000,1048576),(0x1fffc000,16)):
            second=super().read(address,size);n=getattr(self,'double_count',0);self.double_count=n+1
            app.save(self.out,'double-read-'+str(n)+'-private.bin',second)
            require(first==second,'TEMP_DOUBLE_READ_DRIFT')
        return first

def worker(a,auth_path,out,b,m,files):
    mark=json.loads(recovery.read(auth_path.with_suffix('.used'),False))
    require(mark['authorization_sha256']==sha(recovery.read(auth_path,False)),'TEMP_SINGLE_USE')
    out.mkdir(exist_ok=False);recovery.protected(out,False);link=None
    result={'status':'STOP','exit_code':1,'automatic_retry_or_restore':False}
    try:
        link=InstallLink(out,49152);link.started=min(link.started,mark['started_monotonic'])
        result=app.execute(link,out,dict(a,board='B'),m,files)
        result.update(status='B_TEMP_INSTALL_FULL_VERIFY_AND_FLASH_BOOT_PASS',double_full_options=True,
                      binding_sha256=a['binding_sha256'],sensor_or_sector3_writes=0)
    except BaseException as error:
        if link:link.verified_running_flash=False
        result.update(status='STOP',exit_code=1,error_type=type(error).__name__,error_text_sha256=sha(str(error).encode()))
        app.raw.write_json(out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
                link.close();result['Close_completed']=True
            except BaseException as error:result.update(exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
            result.update(sdk_calls=link.sdk_calls,actions=link.counts,close_resume=link.close_resume_enabled)
        result.update(scope=SCOPE,B5START=0,sensor_UART_commands=0,C_or_cloud_writes=0)
        app.raw.write_json(out/'receipt-private.json',result)
        for p in out.iterdir():
            if p.is_file():recovery.protected(p,False)
    print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}))
    return result['exit_code']

def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');args=p.parse_args()
    if not args.execute and not args.worker:
        print(json.dumps({'enabled':False,'scope':SCOPE,'tools_sha256':bindings()}));return 0
    require(args.authorization and args.out,'TEMP_AUTH_REQUIRED')
    a=json.loads(recovery.read(args.authorization,False));b,m,files=authorize(a,args.out)
    if args.worker:return worker(a,args.authorization,args.out,b,m,files)
    return supervisor.supervise(args.authorization,args.out,backend=__import__(__name__))

if __name__=='__main__':raise SystemExit(main())
