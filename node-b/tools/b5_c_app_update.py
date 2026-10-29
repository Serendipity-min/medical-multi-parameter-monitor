"""B5 C出口修正版：独立sector0/1/2事务，保留gen5与旧应用原件；默认无目标操作。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import time

import b4_recovery as recovery
import b4_swd_install as app
import b5_g2ro as ro
import b5_sector3_write_supervisor as supervision

ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'B5_C_EGRESS_APP012_UPDATE'
RESTORE = 'B5_C_EGRESS_APP012_RESTORE'
CARD = ROOT/'node-b/docs/AUTH-B5-C-EGRESS-RETEST-001-R1.md'
BEFORE = 'a5239d616523621593b5e76fd70212aa199e72603b85e359492d642448fff528'
BEFORE_R1 = '533133d9e7b73b459b65126075e878a571e6b345d0fa58a152d609bc70605d06'
BEFORE_R2 = '1b56bc00b84714c326fe8d75162ee873a7caa7a07c24fa35b30b7e69601c6ea0'
BEFORE_R4 = '45274e8ab217777986f666c0a386926d532c5fde2199d86ccd7ffaaed202fc9c'
BEFORE_TEMP = '3369c5de14c2f81b37a2ca3a684ac80c65a2b50c63aba9e3ee892a074bb84fbd'
BEFORE_FINAL_R1 = 'b9e7518ec2af1b780534a97e769054630e19b6a4600800a6db2dea98b8f675ea'
BEFORE_FINAL_R2 = '707d88987431cb4cdf4580d8f627ba58eea4980429d95fc6dcde6ceb8718ca4a'
OLD_FLAGS = 0x20001918
require = recovery.require
sha = recovery.digest


def bindings():
    return {**app.bindings(), 'b5_c_app_update.py': sha(Path(__file__).read_bytes()),
            'b5_g2ro.py': sha(Path(ro.__file__).read_bytes()),
            'b5_sector3_write_supervisor.py': sha(Path(supervision.__file__).read_bytes())}


def load_binding(path, expected_sha, synthetic=False):
    blob = recovery.read(Path(path), synthetic)
    require(sha(blob) == expected_sha, 'C_UPDATE_BINDING_SHA')
    b = json.loads(blob)
    m, files = recovery.load_package(Path(b['package']), b['manifest_sha256'], synthetic)
    require(m['board_role'] == 'C' and m['sectors'] == [0, 1, 2], 'C_UPDATE_SECTORS')
    require(m['files']['before-full-private.bin']['sha256'] == b['before_full_sha256']
            and m['files']['expected-full-private.bin']['sha256'] == b['after_full_sha256'], 'C_UPDATE_IMAGES')
    if not synthetic and b['before_full_sha256'] != BEFORE:
        expected_flags=0x20001dc2 if b['before_full_sha256'] in (BEFORE_FINAL_R1,BEFORE_FINAL_R2) else 0x2000191a
        require(b['before_full_sha256'] in (BEFORE_R1,BEFORE_R2,BEFORE_R4,BEFORE_TEMP,BEFORE_FINAL_R1,BEFORE_FINAL_R2) and b.get('before_flags_address') == expected_flags,
                'C_UPDATE_GEN5_BASELINE')
        proof_blob=recovery.read(Path(b['prior_install_receipt']),False);proof=json.loads(proof_blob)
        require(sha(proof_blob)==b['prior_install_receipt_sha256']
                and proof.get('status')=='C_EGRESS_INSTALL_FULL_VERIFY_DISARMED_PASS'
                and proof.get('exit_code')==0 and proof.get('Close_completed') is True
                and proof.get('DISARMED') is True and proof.get('full_flash_sha256')==b['before_full_sha256'],
                'C_UPDATE_PREDECESSOR_NOT_PASS')
    symbols = recovery.read(Path(b['symbols']), synthetic)
    elf = recovery.read(Path(b['ELF']), synthetic)
    require(sha(symbols) == b['symbols_sha256'] and sha(elf) == b['ELF_sha256'], 'C_UPDATE_ABI_ARTIFACTS')
    table = {name: int(address, 16) for address, name in
             re.findall(r'^([0-9a-fA-F]+)\s+\w\s+(\w+)\s*$', symbols.decode('ascii'), re.M)}
    address = b['flags_address']
    require(0x20000000 <= address < 0x20020000-4 and
            [table.get(n) for n in ('mqtt_connected','network_open','stopped','armed')] ==
            [address+i for i in range(4)], 'C_UPDATE_FLAG_LAYOUT')
    return b, m, files


def authorize(a, out):
    require(a.get('enabled') is True and a.get('owner_approved') is True
            and a.get('scope') in (SCOPE, RESTORE), 'C_UPDATE_OWNER_SCOPE')
    require(a.get('phase') == ('install' if a['scope'] == SCOPE else 'restore'), 'C_UPDATE_PHASE')
    require(a.get('tools_sha256') == bindings() and a.get('DLL_sha256') == ro.raw.DLL_SHA, 'C_UPDATE_TOOL_DRIFT')
    card=a.get('card_name',CARD.name)
    require(card in (CARD.name,'AUTH-B5-C-EGRESS-RETEST-001-R2.md','AUTH-B5-C-EGRESS-RETEST-001-R4.md',
                    'AUTH-B5-TEMP-AND-SEPARATE-CHANNELS-001-R2.md','AUTH-B5-C-EGRESS-FINAL-APP-001-R1.md',
                    'AUTH-B5-C-EGRESS-FINAL-APP-001-R2.md','AUTH-B5-C-EGRESS-DIAGNOSTIC-001-R3.md','AUTH-B5-C-REPAIR-R4-BATCH.md')
            and a.get('card_sha256') == sha((CARD.parent/card).read_bytes()), 'C_UPDATE_CARD_DRIFT')
    require(a.get('expires_unix',0) > time.time() and a.get('session_timeout_s') == 180
            and a.get('probe_sessions') == 1 and a.get('retries') == 0, 'C_UPDATE_BUDGET')
    require(Path(a.get('output','')).resolve() == out.resolve(), 'C_UPDATE_OUTPUT')
    site_blob = recovery.read(Path(a['site_record']), False)
    require(sha(site_blob) == a.get('site_record_sha256'), 'C_UPDATE_SITE_SHA')
    site = json.loads(site_blob)
    require(all(site.get(k) is True for k in ('cold_all_dark_10s','JLink_on_C','C_J5','B_OFF',
                'C_USB_disconnected','CAN_GND_BOOT_unchanged','ESP_present_powered_exception',
                'no_other_program','no_human')), 'C_UPDATE_SITE_INCOMPLETE')
    b, m, files = load_binding(a['binding'], a['binding_sha256'])
    if card in ('AUTH-B5-C-EGRESS-FINAL-APP-001-R1.md','AUTH-B5-C-EGRESS-FINAL-APP-001-R2.md','AUTH-B5-C-EGRESS-DIAGNOSTIC-001-R3.md','AUTH-B5-C-REPAIR-R4-BATCH.md'):
        version='R4' if card=='AUTH-B5-C-REPAIR-R4-BATCH.md' else 'R3' if card.endswith('-R3.md') else 'R2' if card.endswith('-R2.md') else 'R1'
        frozen=json.loads((ROOT/('node-b/evidence/'+('B5-C-REPAIR-R4' if version=='R4' else 'B5-C-EGRESS-FINAL-'+version)+'/candidate.json')).read_text())
        require(frozen['status']=='FROZEN_SOFTWARE_PASS' and b['before_full_sha256']==frozen.get('predecessor_full_sha256',BEFORE_TEMP) and
                b['candidate_sha256']==frozen['BIN_sha256'] and b['after_full_sha256']==frozen['expected_new_full_sha256'],
                'C_UPDATE_FINAL_CANDIDATE_REQUIRED')
    recovery.protected(out.parent, False)
    return b, m, files


class InstallLink(app.InstallLink):
    def __init__(self, out, size, before_flags, after_flags):
        self.before_flags = before_flags
        self.flags_addresses = {before_flags,after_flags}
        super().__init__(out, size)
        ro.ReadLink.install_log_filters(self)

    def flags(self, address):
        require(address in self.flags_addresses, 'C_UPDATE_FLAGS_RANGE')
        require(self.sdk_calls < 1600, 'C_UPDATE_SDK_BUDGET')
        data = (C.c_uint8*4)(); self.sdk_calls += 1
        n = ro.raw.Link.call(self, 'JLINKARM_ReadMemEx', address, 4, data, 0)
        self.io.write(json.dumps({'operation':'C_UPDATE_FLAGS','address':hex(address),'returned':n})+'\n');self.io.flush()
        require(n == 4, 'C_UPDATE_FLAGS_SHORT_READ')
        return bytes(data)

    def call(self, name, *args, timeout=5):
        # 原安装器已在此之前核验完整before/options及正常CPU，才检查DISARMED并消费Halt。
        if name == 'JLINKARM_Halt':
            require(self.flags(self.before_flags) == bytes(4), 'C_UPDATE_BEFORE_NOT_DISARMED')
        return super().call(name, *args, timeout=timeout)

    def read(self, address, size):
        first = super().read(address, size)
        if (address,size) in ((0x08000000,1048576),(0x1fffc000,16)):
            second = super().read(address, size)
            number = getattr(self,'double_reads',0); self.double_reads = number+1
            app.save(self.out, 'double-read-'+str(number)+'-private.bin', second)
            require(first == second, 'C_UPDATE_DOUBLE_READ_DRIFT')
        return first


def worker(a, auth_path, out, b, m, files):
    mark=json.loads(recovery.read(auth_path.with_suffix('.used'),False))
    require(mark['authorization_sha256'] == sha(recovery.read(auth_path,False)), 'C_UPDATE_SINGLE_USE_MARKER')
    out.mkdir(exist_ok=False); recovery.protected(out,False)
    link = None; result = {'status':'STOP','exit_code':1,'automatic_retry_or_restore':False}
    try:
        old_flags=b.get('before_flags_address',OLD_FLAGS)
        before_flags = old_flags if a['phase'] == 'install' else b['flags_address']
        address = b['flags_address'] if a['phase'] == 'install' else old_flags
        link = InstallLink(out,49152,before_flags,address)
        link.started=min(link.started,mark['started_monotonic'])
        result = app.execute(link,out,dict(a,board='C'),m,files)
        flags = link.flags(address); app.save(out,'DISARMED-private.bin',flags)
        require(flags == bytes(4), 'C_UPDATE_AFTER_NOT_DISARMED')
        result.update(status='C_EGRESS_'+a['phase'].upper()+'_FULL_VERIFY_DISARMED_PASS',
                      binding_sha256=a['binding_sha256'],flags_address=address,DISARMED=True,
                      double_full_options=True,config_sector3_unchanged=True)
    except BaseException as error:
        if link: link.verified_running_flash=False
        result.update(status='STOP',exit_code=1,error_type=type(error).__name__,error_text_sha256=sha(str(error).encode()))
        app.raw.write_json(out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
                link.close();result['Close_completed']=True
            except BaseException as error:result.update(exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
            result.update(sdk_calls=link.sdk_calls,actions=link.counts,close_resume=link.close_resume_enabled)
        result.update(scope=a['scope'],ESP_autonomous_network='UNKNOWN_NO_AT_COMMANDS',B5START=0)
        if result['exit_code']:result['status']='STOP'
        app.raw.write_json(out/'receipt-private.json',result)
        for p in out.iterdir():
            if p.is_file():recovery.protected(p,False)
    print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}))
    return result['exit_code']


def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');args=p.parse_args()
    if not args.execute and not args.worker:
        print(json.dumps({'enabled':False,'scopes':[SCOPE,RESTORE],'tools_sha256':bindings()}));return 0
    try:
        require(args.authorization and args.out,'C_UPDATE_AUTH_REQUIRED')
        a=json.loads(recovery.read(args.authorization,False));b,m,files=authorize(a,args.out)
        if args.worker:return worker(a,args.authorization,args.out,b,m,files)
        return supervision.supervise(args.authorization,args.out,backend=__import__(__name__))
    except BaseException as error:
        print(json.dumps({'status':'STOP_BEFORE_TARGET','error_type':type(error).__name__,'exit_code':1}));return 1


if __name__ == '__main__':raise SystemExit(main())
