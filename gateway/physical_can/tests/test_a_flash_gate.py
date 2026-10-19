"""用假J-Link/合成私有文件验证A下载门禁及失败即停；不会访问真实探针。"""
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('flash_a',Path(__file__).resolve().parents[1]/'bench/flash_a.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class TestGate(unittest.TestCase):
    def run_case(self,problem=None):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'repo';here=root/'gateway/physical_can';out=here/'evidence/h2';out.mkdir(parents=True)
            build=here/'build/bench';build.mkdir(parents=True)
            private=Path(temp)/'private';private.mkdir()
            uid=b'A'*12 # 明确的合成身份，仅Host夹具使用。
            (private/'uid.bin').write_bytes(uid)
            data=bytearray(b'\xff'*24000);data[:4]=(0x20020000).to_bytes(4,'little');data[4:8]=(0x08000101).to_bytes(4,'little')
            image=bytes(data);(build/'node_a_a1.bin').write_bytes(image)
            backup=bytearray(b'\xff'*0x100000);backup[:8]=image[:8];backup=bytes(backup)
            for n in ('flash-first.bin','flash-second.bin'):(private/n).write_bytes(backup)
            (private/'private-summary.json').write_text(json.dumps({'exit_code':0,'independent_reads_match':True,'backup_sha256':m.digest(backup)}))
            plan={'exit_code':0,'original_A_source_unchanged':True,'image_sha256':m.digest(image),'affected_sectors':[0,1]}
            if problem=='sha':plan['image_sha256']='0'*64
            if problem=='vectors':
                image=bytes(len(image));(build/'node_a_a1.bin').write_bytes(image);plan['image_sha256']=m.digest(image)
            (out/'node-a-image-plan.json').write_text(json.dumps(plan))
            events=[];programmed=False
            def run(cmd,**kw):
                nonlocal programmed
                if cmd[0]=='git':return type('R',(),{'returncode':0})()
                text=kw['input'].decode('ascii');events.append(text)
                if 'loadbin ' in text:programmed=True
                for line in text.splitlines():
                    match=re.match(r'savebin (.+), (0x[0-9a-fA-F]+), (0x[0-9a-fA-F]+)$',line)
                    if not match:continue
                    path=Path(match[1]);address=int(match[2],16);length=int(match[3],16)
                    values={0xE0042000:(0x10016413).to_bytes(4,'little'),0x1fff7a10:(b'B'*12 if problem=='identity' else uid),0x40023c14:(0xfffaaed).to_bytes(4,'little'),0xE0042008:bytes(4)}
                    if address==0x08000000:
                        value=bytearray(backup)
                        if programmed:
                            value[:len(image)]=image
                            if problem=='outside':value[0x10000]=0
                        value=bytes(value)
                    else:value=values[address]
                    assert len(value)==length;path.write_bytes(value)
                return type('R',(),{'returncode':0,'stdout':b'HOST_FAKE_JLINK','stderr':b''})()
            argv=['flash_a.py','--commit','f'*40,'--backup-dir',str(private),'--confirm-role','A']
            with patch.object(m,'ROOT',root),patch.object(m,'HERE',here),patch.object(m.subprocess,'check_output',return_value='f'*40+'\n'),patch.object(m.subprocess,'run',side_effect=run),patch('sys.argv',argv),patch('sys.stdout',new_callable=io.StringIO):
                result=m.main()
            report=json.loads(next(out.glob('a-download-*.json')).read_text())
            return result,report,events
    def test_success_bounded_without_mass_erase(self):
        rc,r,events=self.run_case();self.assertEqual(rc,0);self.assertTrue(r['outside_64KiB_unchanged'])
        self.assertEqual(sum('loadbin ' in s for s in events),1)
        self.assertFalse(any(re.search(r'^(erase|g|go|unlock)\b',s,re.M) for s in events))
    def test_wrong_sha_never_connects(self):
        rc,r,events=self.run_case('sha');self.assertEqual(rc,1);self.assertFalse(events)
    def test_invalid_vectors_never_connects(self):
        rc,r,events=self.run_case('vectors');self.assertEqual(rc,1);self.assertFalse(events)
    def test_identity_failure_never_programs(self):
        rc,r,events=self.run_case('identity');self.assertEqual(rc,1);self.assertFalse(r['flash_write_started'])
        self.assertFalse(any('loadbin ' in s for s in events))
    def test_unrelated_flash_change_stops_without_retry(self):
        rc,r,events=self.run_case('outside');self.assertEqual(rc,1)
        self.assertEqual(r['failure_code'],'A_OUTSIDE_APPLICATION_CHANGED_STOP')
        self.assertEqual(sum('loadbin ' in s for s in events),1)

if __name__=='__main__':unittest.main()
