"""合成NOR+既有SDK替身验证分段薄入口；不加载真实DLL。"""
import argparse
import ctypes
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'node-b/tests'))
sys.path.insert(0,str(Path(__file__).parent))
from test_b4_swd_install import Fake
import unified_install as u


def record(address,kind,data):
    b=bytes((len(data),address>>8,address&255,kind))+data
    return ':'+(b+bytes((-sum(b)&255,))).hex().upper()


class SegmentedFake(Fake):
    def __init__(self,*a):super().__init__(*a);self.writes=[];self.short=False
    def call(self,name,*a,**kw):
        if name=='JLINKARM_WriteMem':
            self.counts[name]=self.counts.get(name,0)+1
            assert (a[0],a[1]) in u.RANGES
            self.writes.append((a[0],ctypes.string_at(a[2],a[1])))
            return a[1]-1 if self.short else a[1]
        if name=='JLINKARM_EndDownload':
            self.counts[name]=self.counts.get(name,0)+1;data=bytearray(self.image)
            for address,b in self.writes:
                start=address-0x08000000;data[start:start+len(b)]=b
            if self.corrupt:data[49152]^=1
            self.image=bytes(data);return 0
        return super().call(name,*a,**kw)


class UnifiedInstallTests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'node-b/build';self.tmp=tempfile.TemporaryDirectory(dir=folder,prefix='unified-install-synthetic-')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.assertTrue(self.root.resolve().is_relative_to(folder.resolve()))
        self.probe=self.root/'backup/probe';self.probe.mkdir(parents=True)
        self.orig=bytearray(b'\xa5'*1048576);self.orig[:8]=(0x20020000).to_bytes(4,'little')+(0x08000101).to_bytes(4,'little')
        self.orig=bytes(self.orig);self.opts=b'\xaa\x55'*8
        self.ident={'cpuid':0x410fc241,'device_id':0x10000413,'uid_hex':'5a'*12,'capacity_kib':1024,'optcr':0x0fffaaed,'flash_sr':0}
        for n in (1,2):
            (self.probe/f'flash-{n}-private.bin').write_bytes(self.orig)
            (self.probe/f'options-{n}-private.bin').write_bytes(self.opts)
        for name in ('identity-private.json','identity-after-private.json'):(self.probe/name).write_text(json.dumps(self.ident))
        (self.probe.parent/'receipt-private.json').write_text(json.dumps({'board':'C','exit_code':0,'Close_completed':True,'independent_reads_match':True}))
        self.images=self.root/'images';self.images.mkdir();hexlines=[];items=[]
        for name,address,n in (('boot.bin',0x08000000,512),('code.bin',0x08010000,1024)):
            b=bytearray(b'\x3c'*n)
            if address==0x08000000:b[:8]=(0x20020000).to_bytes(4,'little')+(0x08010101).to_bytes(4,'little')
            (self.images/name).write_bytes(b);items.append({'address':address,'bytes':n,'file':name,'SHA256':u.sha(b)})
            hexlines.append(record(0,4,(address>>16).to_bytes(2,'big')))
            for i in range(0,n,16):hexlines.append(record(i,0,b[i:i+16]))
        hexlines.append(record(0,1,b''));wire=('\n'.join(hexlines)+'\n').encode();(self.images/'image.hex').write_bytes(wire)
        self.meta={'erase_sectors':[0,4],'images':items,'HEX':{'file':'image.hex','SHA256':u.sha(wire)}}
        self.save_meta();self.a=argparse.Namespace(backup=self.probe.parent,current_install=None,phase='install',image_dir=self.images)

    def save_meta(self):(self.images/'unified-layout.json').write_text(json.dumps(self.meta))
    def prepare(self):
        with patch.object(u.recovery,'protected',side_effect=lambda p,s:Path(p)):return u.prepare(self.a)
    def run_install(self,payload,fake,cold_boot=False):
        out=self.root/('run-'+str(len(list(self.root.glob('run-*')))));out.mkdir()
        expected=payload['expected'];core={'registers':{'R15':int.from_bytes(expected[4:8],'little'),'MSP':int.from_bytes(expected[:4],'little')}}
        with patch.object(u.time,'sleep'),patch.object(u.engine.runtime,'core_if_halted',return_value=core):
            return u.execute(fake,out,payload,self.a.phase,cold_boot)

    def test_cold_boot_verifies_without_reset_or_go(self):
        f=SegmentedFake(self.orig,self.opts)
        result=self.run_install(self.prepare(),f,cold_boot=True)
        self.assertEqual(result['boot_mode'],'PHYSICAL_COLD_BOOT_REQUIRED')
        self.assertNotIn('JLINKARM_Reset',f.counts)
        self.assertNotIn('JLINKARM_Go',f.counts)
        self.assertFalse(f.close_resume_enabled)

    def test_cold_boot_stops_on_loader_reset_sticky(self):
        class ResetAfterLoad(SegmentedFake):
            def u32(self,address):
                value=super().u32(address)
                if address==u.engine.readonly.SYSTEM['DHCSR'] and self.counts.get('JLINKARM_EndDownload'):
                    value|=1<<25
                return value
        f=ResetAfterLoad(self.orig,self.opts)
        with self.assertRaisesRegex(ValueError,'LOADER_RESET_OBSERVED'):
            self.run_install(self.prepare(),f,cold_boot=True)
        self.assertNotIn('JLINKARM_Reset',f.counts)
        self.assertNotIn('JLINKARM_Go',f.counts)

    def test_install_and_rollback_exact_full_original(self):
        payload=self.prepare();fake=SegmentedFake(self.orig,self.opts);r=self.run_install(payload,fake)
        self.assertEqual(r['exit_code'],0);self.assertEqual([a for a,b in fake.writes],[0x08000000,0x08010000])
        self.assertEqual(fake.image[16384:65536],self.orig[16384:65536]);self.assertEqual(fake.image[131072:],self.orig[131072:])
        self.assertEqual(fake.counts['JLINKARM_WriteMem'],2)
        current=self.root/'current';(current/'probe').mkdir(parents=True)
        (current/'probe/after-full-private.bin').write_bytes(fake.image)
        (current/'probe/identity-after-private.json').write_text(json.dumps(self.ident))
        (current/'receipt-private.json').write_text(json.dumps({**r,'Close_completed':True}))
        self.a.current_install=current;self.a.phase='restore';restore=self.prepare()
        f=SegmentedFake(fake.image,self.opts);self.run_install(restore,f);self.assertEqual(f.image,self.orig)

    def test_short_write_never_resets_or_continues_download(self):
        f=SegmentedFake(self.orig,self.opts);f.short=True
        with self.assertRaisesRegex(ValueError,'SHORT_WRITE'):self.run_install(self.prepare(),f)
        self.assertNotIn('JLINKARM_EndDownload',f.counts);self.assertNotIn('JLINKARM_Reset',f.counts)

    def test_wrong_identity_fault_ROM_and_halt_before_download(self):
        for field in ('wrong_uid','fault','rom','halted'):
            f=SegmentedFake(self.orig,self.opts);setattr(f,field,True)
            with self.subTest(field=field),self.assertRaises((ValueError,RuntimeError)):self.run_install(self.prepare(),f)
            self.assertNotIn('JLINKARM_Halt',f.counts);self.assertNotIn('JLINKARM_Go',f.counts)

    def test_flash_drift_before_halt(self):
        f=SegmentedFake(self.orig[:-1]+b'\0',self.opts)
        with self.assertRaisesRegex(ValueError,'FLASH_DRIFT'):self.run_install(self.prepare(),f)
        self.assertNotIn('JLINKARM_Halt',f.counts)

    def test_full_verify_catches_sector3_change_and_never_boots(self):
        f=SegmentedFake(self.orig,self.opts);f.corrupt=True
        with self.assertRaisesRegex(ValueError,'FULL_VERIFY'):self.run_install(self.prepare(),f)
        self.assertNotIn('JLINKARM_Reset',f.counts);self.assertNotIn('JLINKARM_Go',f.counts)

    def test_options_drift_before_halt(self):
        f=SegmentedFake(self.orig,b'\x00'*16)
        with self.assertRaisesRegex(ValueError,'OPTIONS_DRIFT'):self.run_install(self.prepare(),f)
        self.assertNotIn('JLINKARM_Halt',f.counts)

    def test_hex_checksum_hole_overlap_and_truncation(self):
        good=(self.images/'image.hex').read_bytes()
        with self.assertRaisesRegex(ValueError,'CHECKSUM'):u.hex_bytes(good.replace(b'F2',b'F3',1))
        with self.assertRaisesRegex(ValueError,'RANGE'):u.hex_bytes((record(0,4,b'\x08\x00')+'\n'+record(0xbff8,0,b'x'*16)+'\n').encode())
        line=record(0,0,b'x');wire=(record(0,4,b'\x08\x00')+'\n'+line+'\n'+line+'\n').encode()
        with self.assertRaisesRegex(ValueError,'OVERLAP'):u.hex_bytes(wire)
        with self.assertRaisesRegex(ValueError,'TRUNCATED'):u.hex_bytes(b'')

    def test_binary_and_path_tamper(self):
        f=self.images/'code.bin';f.write_bytes(b'x'*1024)
        with self.assertRaisesRegex(ValueError,'SHA'):u.load_images(self.images)
        self.meta['HEX']['file']='../outside.hex';self.save_meta()
        with self.assertRaisesRegex(ValueError,'HEX_PATH'):u.load_images(self.images)

    def test_unapproved_sector4_execution_never_instantiates_SDK(self):
        argv=['tool','--phase','install','--backup',str(self.probe.parent),'--image-dir',str(self.images),'--out',str(self.root/'new'),'--execute']
        with patch.object(sys,'argv',argv),patch.object(u.recovery,'protected',side_effect=lambda p,s:Path(p)),patch.object(u,'SegmentLink') as sdk,patch.object(u.backup,'supervise') as worker:
            with self.assertRaisesRegex(ValueError,'OWNER_SECTOR4'):u.main()
            sdk.assert_not_called();worker.assert_not_called()

    def test_segment_write_guard_denies_config_and_duplicate(self):
        f=object.__new__(u.SegmentLink);f.blocks={0x08000000:b'a'*16384,0x08010000:b'b'*65536}
        f.download_started=True;f.program_sha='known';f.written=set();f.sdk_calls=0;f.counts={}
        for address in (0x08004000,0x0800c000,0x1fffc000):
            with self.assertRaisesRegex(ValueError,'WRITE_SCOPE'):f.call('JLINKARM_WriteMem',address,16,None)
        b=(ctypes.c_uint8*16384).from_buffer_copy(f.blocks[0x08000000])
        with patch.object(u.engine.raw.Link,'call',return_value=16384):self.assertEqual(f.call('JLINKARM_WriteMem',0x08000000,16384,b),16384)
        with self.assertRaisesRegex(ValueError,'WRITE_SCOPE'):f.call('JLINKARM_WriteMem',0x08000000,16384,b)


if __name__=='__main__':unittest.main()
