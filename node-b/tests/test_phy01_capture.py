"""PHY01 真实解析/裁定的合成正负例，不打开串口或SDK。"""
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import phy01_capture as p

def fixture(profile):
    rows=[];limit,mode=p.PROFILES[profile]
    def add(kind,ident,tick,data=b'',flags=0):
        rows.append(dict(kind=kind,bus=1,id=ident,tick=tick,data=data.ljust(8,b'\0').hex(),
                         dlc=len(data),flags=flags,seq=len(rows)+1))
    add(9,0,0,b'\0'*8)
    if profile.startswith('BD'):
        add(3,0,0,b'\x80\x02');add(3,0,0,b'\x01\x04')
    for tick in range(0,limit,500):
        add(1,0x704,tick,b'\x05')
        if profile.startswith('BD'):add(1,0x702,tick,b'\x7f')
        if tick%1000:continue
        add(1,0x684,tick,struct.pack('<II',16,1));add(1,0x484,tick,struct.pack('<II',1577836800+tick//1000,tick))
        add(1,0x384,tick,struct.pack('<4H',0,0,2370,10))
        add(8,8,tick,struct.pack('<iI',2370,p.codec.value_hash([2370])),4|256|(1<<16))
        add(10,8,tick,struct.pack('<Q',1577836800000+tick))
        for ident,a,b,flags in ((1,0,100,0),(2,0,1,0),(4,0x08000000,0,0),(5,128,0,0),(7,limit,500000,mode)):
            add(5,ident,tick,struct.pack('<II',a,b),flags)
    add(6,0,limit,struct.pack('<II',limit,0));return rows

class Tests(unittest.TestCase):
    def test_D60(self):
        r=p.assess(fixture('D60'),'D60');self.assertEqual(r['failures'],[])
        self.assertEqual(r['D_raw_model_matches'],60);self.assertEqual(r['D_received_temperature_C_range'],[23.7,23.7])
    def test_BD15(self):self.assertEqual(p.assess(fixture('BD15'),'BD15')['failures'],[])
    def test_BD300_requires_300s_stop_and_both_sources(self):
        rows=fixture('BD300');r=p.assess(rows,'BD300')
        self.assertEqual(r['failures'],[]);self.assertEqual(r['D_valid_models'],300)
        self.assertEqual(r['CAN_RX_counts']['0x702'],600)
        rows[-1]=dict(rows[-1],data=struct.pack('<II',15000,0).hex())
        self.assertIn('STOP_LIMIT_OR_ERROR',p.assess(rows,'BD300')['failures'])
    def test_small_window_rejects_ECG(self):
        rows=fixture('BD15');at=next(i for i,r in enumerate(rows) if r['kind']==1);rows[at]=dict(rows[at],id=0x182)
        self.assertIn('ECG_STREAM_IN_SMALL_FRAME_WINDOW',p.assess(rows,'BD15')['failures'])
    def test_old_15s_image_rejected(self):
        rows=[dict(r,flags=0) if r['kind']==5 and r['id']==7 else r for r in fixture('BD15')]
        self.assertIn('C_WRONG_PROFILE',p.assess(rows,'BD15')['failures'])
    def test_busoff_or_capture_loss_rejected(self):
        for ident,data,flags in ((1,struct.pack('<II',4,0),0),(1,struct.pack('<II',0,0),1),(2,struct.pack('<II',1,0),0)):
            rows=fixture('BD15');at=next(i for i,r in enumerate(rows) if r['kind']==5 and r['id']==ident)
            rows[at]=dict(rows[at],data=data.hex(),flags=flags)
            self.assertNotEqual(p.assess(rows,'BD15')['failures'],[])
    def test_model_value_mismatch_rejected(self):
        rows=fixture('D60');at=next(i for i,r in enumerate(rows) if r['kind']==8)
        rows[at]=dict(rows[at],data=struct.pack('<iI',3650,p.codec.value_hash([3650])).hex())
        self.assertIn('D_MODEL_RAW_VALUE_MISMATCH',p.assess(rows,'D60')['failures'])
    def test_wire_gap_or_bad_stop_rejected(self):
        rows=fixture('BD15');rows[-1]=dict(rows[-1],data=struct.pack('<II',15001,0).hex())
        self.assertIn('STOP_LIMIT_OR_ERROR',p.assess(rows,'BD15')['failures'])
        self.assertIn('SERIAL_SEQUENCE_GAP',p.assess(rows[:2]+rows[3:],'BD15')['failures'])
    def test_source_emergency_rejected(self):
        row=dict(kind=1,bus=1,id=0x84,data='1081100000000000',flags=0)
        with self.assertRaisesRegex(ValueError,'SOURCE_EMCY'):p.check_row(row,'BD15')
    def test_B60_HR_qualification(self):
        from test_b4_capture_decode import fixture as b_fixture
        rows=[r for r in b_fixture() if r['tick']<60000]
        rows.append(dict(b_fixture()[-1],tick=60000,seq=rows[-1]['seq']+1,data=struct.pack('<II',60000,0).hex()))
        rows.insert(len(rows)-1,dict(kind=5,bus=1,id=5,tick=60000,data=struct.pack('<II',128,0).hex(),flags=0,seq=0))
        rows=[dict(r,seq=i+1) for i,r in enumerate(rows)]
        self.assertEqual(p.assess(rows,'B60')['failures'],[])
        at=next(i for i,r in enumerate(rows) if r['kind']==1 and r['id']==0x382 and r['tick']==25000)
        rows[at]=dict(rows[at],data=struct.pack('<4H',0,0,0,0).hex())
        self.assertIn('HR_NOT_VALID_NOMINAL60',p.assess(rows,'B60')['failures'])

if __name__=='__main__':unittest.main(verbosity=2)
