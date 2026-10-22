"""VOICE-002唯一应用扇区事务：新鲜双读原件、精确48KiB块、配置/保护区不写。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from tools import h3_c_jlink as base
from gateway.physical_can.r2_config_record import validate

ROOT=Path(__file__).resolve().parents[2]
CURRENT='49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4'
IMAGE='b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe'
RECORD='395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b'
START=0x08000000; APP=49152; FULL=65536
def sha(b):return hashlib.sha256(b).hexdigest()


def plan(binary,manifest):
    image=binary.read_bytes();m=json.loads(manifest.read_text(encoding='utf-8'))
    if m.get('exit_code')!=0 or not m.get('cloud_voice') or m['image']['sha256']!=sha(image):raise ValueError('VOICE_IMAGE_NOT_FROZEN')
    if not 32768<len(image)<=APP or m['image']['erase_sectors']!=[0,1,2] or m['compiled_MQTT_port']!=8883:raise ValueError('VOICE_IMAGE_SCOPE')
    return {'role':'C','image_bytes':len(image),'image_sha256':sha(image),
        'write_start':START,'write_end_exclusive':START+APP,'erase_sectors':[0,1,2],
        'write_block_sha256':sha(image.ljust(APP,b'\xff')),'current_64k_sha256':CURRENT,
        'record_sha256':RECORD,'preserve_sectors':[3,4,5,6,7,8,9,10,11],
        'automatic_go':False,'mass_erase':False,'options_write':False}


def check_original(data):
    if len(data)!=FULL or sha(data)!=CURRENT or sha(data[:43172])!=IMAGE:raise ValueError('VOICE_ORIGINAL_CHANGED')
    if sha(data[APP:APP+336])!=RECORD or validate(data[APP:APP+336])!=3:raise ValueError('VOICE_CONFIG_CHANGED')


class Window(base.Window):
    def controller(self,label):
        b=self.read(label,[('controller',0x40023c0c,8)])['controller']
        if int.from_bytes(b[:4],'little')&0x100f2 or int.from_bytes(b[4:],'little')!=0x80000000:raise ValueError('VOICE_CONTROLLER_NOT_CLEAN_LOCKED')
        return b

    def snapshot(self):
        identity=self.identity_read('identity');protected=self.protection('protected');self.controller('clean')
        a=self.read('first',[('flash64k',START,FULL)])['flash64k']
        b=self.read('second',[('flash64k',START,FULL)])['flash64k']
        if a!=b or (self.private/'first-flash64k.bin').read_bytes()!=a or (self.private/'second-flash64k.bin').read_bytes()!=a:raise ValueError('VOICE_DOUBLE_READ_DISK_MISMATCH')
        check_original(a)
        return {'exit_code':0,'action':'FRESH_C_READONLY_BACKUP','sha256':sha(a),'identity_match':True,
                'config_generation':3,'protected_verified':True,'bytes_each':FULL,'reads':2,'target':'HALTED_NO_GO'}

    def transact(self,block,expected_before,label):
        if len(block)!=APP or len(expected_before)!=FULL:raise ValueError('VOICE_BLOCK_SIZE')
        identity=self.identity_read('identity');protected=self.protection('protected');controller=self.controller('clean')
        freeze=int.from_bytes(identity['freeze'],'little')|(1<<12)
        first=self.read('first',[('flash64k',START,FULL)],[f'w4 0xE0042008 {hex(freeze)}'])['flash64k']
        second=self.read('second',[('flash64k',START,FULL)])['flash64k']
        if first!=second or first!=expected_before:raise ValueError('VOICE_CURRENT_BACKUP_MISMATCH_NO_WRITE')
        p=self.private/'exact-application-block.bin';p.write_bytes(block)
        if p.read_bytes()!=block:raise ValueError('VOICE_BLOCK_DISK_MISMATCH')
        (self.private/'write-attempt.json').write_text(json.dumps({'label':label,'block_sha256':sha(block),'erase_sectors':[0,1,2]}),encoding='utf-8')
        after=self.read('after',[('flash64k',START,FULL)],
            [f'loadbin {p.as_posix()}, {hex(START)}','h',f'verifybin {p.as_posix()}, {hex(START)}'])['flash64k']
        if after!=block+first[APP:]:raise ValueError('VOICE_APPLICATION_OR_CONFIG_READBACK_FAILED_STOP')
        if self.protection('protected-after')!=protected or self.controller('clean-after')!=controller:raise ValueError('VOICE_PROTECTION_OR_CONTROLLER_CHANGED_STOP')
        end=self.identity_read('identity-after')
        if any(identity[k]!=end[k] for k in ('chip','size','uid','options')):raise ValueError('VOICE_IDENTITY_CHANGED_STOP')
        restored=self.read('debug-restored',[('freeze',0xE0042008,4)],
                           [f'w4 0xE0042008 {hex(int.from_bytes(identity["freeze"],"little"))}'])['freeze']
        if restored!=identity['freeze']:raise ValueError('VOICE_DEBUG_RESTORE_FAILED_STOP')
        return {'exit_code':0,'action':label,'before_sha256':sha(first),'after_sha256':sha(after),
                'block_sha256':sha(block),'sector3_7_11_options_unchanged':True,'target':'HALTED_NO_GO'}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('plan','read','program','restore'))
    p.add_argument('--image',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--private-dir',type=Path);p.add_argument('--card',type=Path);p.add_argument('--prior',type=Path);a=p.parse_args()
    scope=plan(a.image,a.manifest)
    if a.action=='plan':print(json.dumps(scope,indent=2));return 0
    card=json.loads(a.card.read_text(encoding='utf-8'))
    if card.get('contract')!='MPM-C-VOICE-002' or card.get('owner_blanket_authorized') is not True or card.get('action')!=a.action:raise ValueError('VOICE_OPERATION_CARD_REQUIRED')
    expiry=datetime.fromisoformat(card['expires_utc'])
    if expiry.tzinfo is None or datetime.now(timezone.utc)>=expiry:raise ValueError('VOICE_OPERATION_WINDOW_EXPIRED')
    if card.get('scope')!=scope or card.get('tool_sha256')!=sha(Path(__file__).read_bytes()) or card.get('head')!=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip():raise ValueError('VOICE_FROZEN_SCOPE_CHANGED')
    private=a.private_dir.resolve();boundary=Path('E:/medical-monitor-c-voice-cloud-private').resolve()
    if not private.is_relative_to(boundary) or private==boundary or not private.is_dir() or any(private.iterdir()):raise ValueError('VOICE_EMPTY_RESTRICTED_DIRECTORY_REQUIRED')
    ref=json.loads(Path(card['identity_reference']).read_text(encoding='utf-8'));source=Path(ref['identity_source'])
    if sha(source.read_bytes())!=ref['identity_source_sha256']:raise ValueError('VOICE_PRIVATE_IDENTITY_CHANGED')
    try:
        bridge=base.Bridge(private);w=Window(private,bridge,base.external_identity(source))
        if a.action=='read':r=w.snapshot()
        else:
            original=(a.prior/'first-flash64k.bin').read_bytes();check_original(original)
            if (a.prior/'second-flash64k.bin').read_bytes()!=original:raise ValueError('VOICE_PRIOR_DOUBLE_BACKUP_MISMATCH')
            new=a.image.read_bytes().ljust(APP,b'\xff')
            r=w.transact(new,original,'CLOUD_VOICE_APPLICATION_VERIFIED') if a.action=='program' else w.transact(original[:APP],new+original[APP:],'ORIGINAL_H3_APPLICATION_RESTORED')
        r['VTref_voltages']=bridge.voltages
    except Exception as error:
        r={'exit_code':1,'state':'STOPPED_NO_AUTOMATIC_RETRY_OR_RESTORE','error_type':type(error).__name__}
        if type(error) is ValueError:r['error_code']=str(error)
    (private/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2));return r['exit_code']


if __name__=='__main__':raise SystemExit(main())
