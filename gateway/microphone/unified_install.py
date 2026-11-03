"""统一C的sector0+4薄安装/回退入口；复用现有SDK白名单、CPU检查和监督器。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'node-b/tools'))
import abc_board_backup as backup
import b4_recovery as recovery
import b4_swd_install as engine

RANGES=((0x08000000,16384),(0x08010000,65536))
need=recovery.require
sha=recovery.digest


def hex_bytes(raw):
    result={};base=0;ended=False
    for line in raw.decode('ascii').splitlines():
        need(line.startswith(':') and not ended,'HEX_RECORD_OR_AFTER_EOF')
        b=bytes.fromhex(line[1:]);need(len(b)>=5 and len(b)==b[0]+5 and sum(b)%256==0,'HEX_LENGTH_CHECKSUM')
        n,kind=b[0],b[3];offset=int.from_bytes(b[1:3],'big')
        if kind==0:
            address=base+offset
            need(any(lo<=address<address+n<=lo+size for lo,size in RANGES),'HEX_CONFIG_OR_UNKNOWN_RANGE')
            for i,value in enumerate(b[4:4+n]):
                need(address+i not in result,'HEX_OVERLAP');result[address+i]=value
        elif kind==4:
            need(n==2 and not offset,'HEX_EXTENDED_ADDRESS');base=int.from_bytes(b[4:6],'big')<<16
        elif kind==1:need(n==0,'HEX_EOF');ended=True
        elif kind==5:need(n==4,'HEX_ENTRY')
        else:raise ValueError('HEX_UNSUPPORTED_RECORD')
    need(ended and result,'HEX_TRUNCATED');return result


def load_images(directory):
    meta=json.loads((directory/'unified-layout.json').read_text())
    need(meta['erase_sectors']==[0,4] and len(meta['images'])==2,'UNIFIED_LAYOUT_SCOPE')
    need(Path(meta['HEX']['file']).name==meta['HEX']['file'],'HEX_PATH')
    wire=(directory/meta['HEX']['file']).read_bytes();need(sha(wire)==meta['HEX']['SHA256'],'HEX_SHA')
    encoded=hex_bytes(wire);images=[];covered=set()
    for image,(address,size) in zip(meta['images'],RANGES):
        need(Path(image['file']).name==image['file'] and image['address']==address,'IMAGE_PATH_OR_ADDRESS')
        data=(directory/image['file']).read_bytes()
        need(0<len(data)<=size and len(data)==image['bytes'] and sha(data)==image['SHA256'],'IMAGE_SIZE_SHA')
        for i,value in enumerate(data):
            a=address+i
            need(encoded.get(a,255)==value,'HEX_BINARY_MISMATCH');covered.add(a)
        images.append((address,data))
    need(set(encoded)<=covered,'HEX_UNLISTED_DATA')
    sp,pc=int.from_bytes(images[0][1][:4],'little'),int.from_bytes(images[0][1][4:8],'little')
    need(0x20000000<sp<=0x20020000 and sp%8==0 and pc&1 and 0x08010000<=pc<0x08020000,'UNIFIED_BOOT_VECTOR')
    return images,meta


def prepare(a):
    probe=a.backup/'probe';proof=json.loads(recovery.read(a.backup/'receipt-private.json',False))
    need(proof['board']=='C' and proof['exit_code']==0 and proof['Close_completed'] and proof['independent_reads_match'],'C_BACKUP_REQUIRED')
    original=recovery.read(probe/'flash-1-private.bin',False)
    need(len(original)==1048576 and original==recovery.read(probe/'flash-2-private.bin',False),'C_BACKUP_MISMATCH')
    options=recovery.read(probe/'options-1-private.bin',False)
    need(len(options)==16 and options==recovery.read(probe/'options-2-private.bin',False),'C_OPTIONS_MISMATCH')
    identity=json.loads(recovery.read(probe/'identity-private.json',False));recovery.identity_check(identity)
    need(identity==json.loads(recovery.read(probe/'identity-after-private.json',False)),'C_IDENTITY_MISMATCH')
    before=original
    if a.current_install:
        prior=json.loads(recovery.read(a.current_install/'receipt-private.json',False))
        need(prior['board']=='C' and prior['exit_code']==0 and prior['Close_completed'],'CURRENT_INSTALL_REQUIRED')
        before=recovery.read(a.current_install/'probe/after-full-private.bin',False)
        need(sha(before)==prior['full_flash_sha256'] and
             json.loads(recovery.read(a.current_install/'probe/identity-after-private.json',False))==identity,'CURRENT_INSTALL_IDENTITY_OR_BYTES')
    need(all(identity['optcr']&(1<<(16+i)) for i in (0,4)),'SECTOR_WRITE_PROTECTED_NO_UNLOCK')
    expected=bytearray(original);layout=None
    if a.phase=='install':
        need(a.image_dir is not None,'IMAGE_DIR_REQUIRED');images,layout=load_images(a.image_dir)
        for address,data in images:expected[address-0x08000000:address-0x08000000+len(data)]=data
    else:need(a.current_install is not None,'RESTORE_NEEDS_VERIFIED_CURRENT_INSTALL')
    need(len(before)==len(expected)==1048576 and before[16384:65536]==expected[16384:65536]
         and before[131072:]==expected[131072:],'PROTECTED_FLASH_DRIFT')
    blocks={address:bytes(expected[address-0x08000000:address-0x08000000+size]) for address,size in RANGES}
    return {'before':before,'expected':bytes(expected),'options':options,'identity':identity,'blocks':blocks,'layout':layout}


class SegmentLink(engine.InstallLink):
    def __init__(self,out,blocks):
        self.blocks=blocks;self.written=set();super().__init__(out,16384)

    def call(self,name,*args,timeout=5):
        if name!='JLINKARM_WriteMem':return super().call(name,*args,timeout=timeout)
        address,size,ptr=args
        need(self.download_started and self.program_sha and address in self.blocks and address not in self.written,'SEGMENT_WRITE_SCOPE')
        need(size==len(self.blocks[address]) and C.string_at(ptr,size)==self.blocks[address],'SEGMENT_WRITE_BYTES')
        need(self.sdk_calls<1600 and len(self.written)<2,'SEGMENT_WRITE_BUDGET')
        self.written.add(address);self.counts[name]=self.counts.get(name,0)+1;self.sdk_calls+=1
        return engine.raw.Link.call(self,name,*args,timeout=timeout)


def execute(link,out,payload,phase):
    ref=payload['identity'];link.open();seen=engine.raw.identity(link);engine.raw.check_identity(seen)
    engine.raw.write_json(out/'identity-before-private.json',seen);need(seen==ref,'WRONG_C_OR_PROTECTION')
    engine.raw.write_json(out/'entry-sticky-private.json',{'DHCSR':link.u32(engine.readonly.SYSTEM['DHCSR'])})
    state=engine.readonly.snapshot(link);engine.raw.write_json(out/'entry-state-private.json',state)
    engine.readonly.check_running(link,state)
    link.set_close_resume(True)
    before=link.read(0x08000000,1048576);engine.save(out,'before-full-private.bin',before)
    need(before==payload['before'],'CURRENT_FLASH_DRIFT_BEFORE_HALT')
    need(link.read(0x1fffc000,16)==payload['options'],'OPTIONS_DRIFT_BEFORE_HALT')
    engine.readonly.check_running(link,engine.readonly.snapshot(link));link.set_close_resume(False)
    need(link.call('JLINKARM_Halt',timeout=3)==0,'HALT_FAILED')
    need(link.u32(engine.readonly.SYSTEM['DHCSR'])&engine.raw.HALT,'HALT_NOT_CONFIRMED')
    link.u32(engine.readonly.SYSTEM['DHCSR']);link.stable_halt();link.verified_running_flash=False
    link.program_sha=sha(b''.join(payload['blocks'].values()))
    engine.raw.write_json(out/'program-intent-private.json',{'phase':phase,'sectors':[0,4],
        'writes':[{'address':a,'bytes':len(b),'SHA256':sha(b)} for a,b in payload['blocks'].items()],
        'sector3_Options_and_all_other_regions':'PRESERVE'})
    link.call('JLINKARM_BeginDownload',0)
    for address,data in payload['blocks'].items():
        buf=(C.c_uint8*len(data)).from_buffer_copy(data)
        need(link.call('JLINKARM_WriteMem',address,len(data),buf)==len(data),'NATIVE_SEGMENT_SHORT_WRITE')
    need(link.call('JLINKARM_EndDownload',timeout=45)>=0,'NATIVE_LOADER_FAILED')
    need(link.u32(engine.readonly.SYSTEM['DHCSR'])&engine.raw.HALT,'LOADER_NOT_HALTED')
    actual=link.read(0x08000000,1048576);engine.save(out,'after-full-private.bin',actual)
    need(actual==payload['expected'],'FULL_VERIFY_FAILED')
    options=link.read(0x1fffc000,16);engine.save(out,'after-options-private.bin',options)
    need(options==payload['options'],'OPTIONS_CHANGED')
    seen=engine.raw.identity(link);engine.raw.write_json(out/'identity-after-private.json',seen);need(seen==ref,'POST_IDENTITY_DRIFT')
    link.fully_verified=True;link.policy('SetResetType = 0');need(link.call('JLINKARM_Reset')==0,'RESET_FAILED')
    core=engine.runtime.core_if_halted(link);engine.raw.write_json(out/'reset-core-private.json',core)
    regs=core.get('registers',{});need((regs.get('R15',0)&~1)==(int.from_bytes(actual[4:8],'little')&~1)
        and regs.get('MSP')==int.from_bytes(actual[:4],'little'),'RESET_VECTOR_MISMATCH')
    link.call('JLINKARM_Go');time.sleep(1);link.u32(engine.readonly.SYSTEM['DHCSR'])
    engine.readonly.check_running(link,engine.readonly.snapshot(link));link.set_close_resume(True)
    return {'exit_code':0,'status':'UNIFIED_C_'+phase.upper()+'_FULL_VERIFY_PASS','board':'C',
            'sectors':[0,4],'full_flash_sha256':sha(actual),'options_unchanged':True,'all_other_sectors_unchanged':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=('install','restore'),required=True)
    p.add_argument('--backup',type=Path,required=True);p.add_argument('--current-install',type=Path)
    p.add_argument('--image-dir',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--sector4-approved',action='store_true')
    p.add_argument('--worker',action='store_true');a=p.parse_args();payload=prepare(a)
    recovery.protected(a.out.parent,False);need(not a.out.exists(),'NEW_OUTPUT_REQUIRED')
    if not(a.execute or a.worker):
        print(json.dumps({'status':'PLAN_ONLY_REQUIRES_OWNER_SECTOR4_APPROVAL','sectors':[0,4],
                          'write_ranges':[[x,x+n] for x,n in RANGES]}));return 0
    need(a.sector4_approved,'OWNER_SECTOR4_APPROVAL_REQUIRED')
    if not a.worker:
        cmd=[sys.executable,'-X','utf8',str(Path(__file__)),*sys.argv[1:],'--worker']
        return backup.supervise(cmd,a.out)
    a.out.mkdir();out=a.out/'probe';out.mkdir();link=None;result={'exit_code':1,'status':'STOP','board':'C'}
    try:
        link=SegmentLink(out,payload['blocks']);result.update(execute(link,out,payload,a.phase))
    except (Exception,KeyboardInterrupt) as error:
        if link:link.verified_running_flash=False
        engine.raw.write_json(a.out/'failure-private.json',{'type':type(error).__name__,'reason':str(error)})
        result.update(error_type=type(error).__name__,error_SHA256=sha(str(error).encode()))
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:link.set_close_resume(False)
                link.close();result['Close_completed']=True
            except Exception as error:result.update(exit_code=1,Close_completed=False,close_error_type=type(error).__name__)
            result['native_actions']=link.counts
        engine.raw.write_json(a.out/'receipt-private.json',result)
    print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
