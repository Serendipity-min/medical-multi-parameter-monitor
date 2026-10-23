"""合成180秒双通道原始CAN及C重建校验，检查损坏/缺包/重启负例。"""
import binascii
from functools import lru_cache
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import b4_capture_decode as d

def packet(kind,ident,tick,data=b'',flags=0,seq=1):
    p=bytearray(32);p[:6]=bytes([0xb4,0xc4,1,kind,1,len(data)])
    struct.pack_into('<HII',p,6,ident,tick,seq);p[16:16+len(data)]=data
    struct.pack_into('<I',p,24,flags);struct.pack_into('<H',p,30,binascii.crc_hqx(p[:30],0xffff));return bytes(p)

@lru_cache(maxsize=1)
def fixture():
    rows=[];seq=0;buffers={4:[],6:[]};stream_seq={}
    def add(k,ident,tick,data=b'',flags=0):
        nonlocal seq
        seq+=1
        rows.append({'kind':k,'bus':1,'id':ident,'tick':tick,'data':data.ljust(8,b'\0').hex(),
                     'dlc':len(data),'flags':flags,'seq':seq})
    def model(stream,tick,values,valid=True):
        stream_seq[stream]=stream_seq.get(stream,0)+1
        add(8,stream,tick,struct.pack('<iI',values[-1],d.value_hash(values)),
            2|(int(valid)<<8)|(len(values)<<16))
        add(10,stream,tick,struct.pack('<Q',1577836800000+tick),stream_seq[stream])
    add(7,4,0,b'B4C4'+b'\0'*4);add(9,0,0,b'\0'*8)
    add(3,0,0,b'\x01\x02');add(3,0x100,0,b'\0'*6)
    for tick in range(180000):
        if tick%1000==0:
            add(1,0x482,tick,struct.pack('<II',1577836800+tick//1000,tick))
            add(1,0x682,tick,struct.pack('<II',15,1))
            add(1,0x382,tick,struct.pack('<4H',6000,2000,0,0))
            model(5,tick,[6000]);model(7,tick,[2000]);model(8,tick,[0],False)
            add(5,1,tick,struct.pack('<II',0,0))
            add(5,2,tick,struct.pack('<II',0,1))
            add(5,4,tick,struct.pack('<II',0x08000000,0))
        if tick%500==0:add(1,0x702,tick,b'\x05')
        for stream,ident,step,count in ((4,0x182,4,100),(6,0x282,20,50)):
            if tick%step:continue
            value=(tick//step)%200-100
            add(1,ident,tick,struct.pack('<iI',value,tick));buffers[stream].append(value)
            if len(buffers[stream])==count:model(stream,tick,buffers[stream]);buffers[stream]=[]
    add(6,0,180000,struct.pack('<II',180000,0))
    return rows

class Tests(unittest.TestCase):
    def test_wire_codec_fragmentation_and_prefix(self):
        data=packet(1,0x182,0xffffffff,struct.pack('<iI',-123,0x80000000))
        p=d.Parser();self.assertFalse(p.feed(b'old H3 logs\r\n'+data[:17]))
        rows=p.feed(data[17:]);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['tick'],0xffffffff);self.assertEqual(rows[0]['data'],data[16:24].hex())
    def test_corruption(self):
        p=d.Parser();x=bytearray(packet(1,0x182,0,b'\x00'*8));x[19]^=1
        self.assertFalse(p.feed(x));self.assertEqual(p.crc_errors,1)
    def test_nominal_full_window(self):
        r=d.assess(fixture());self.assertEqual(r['failures'],[])
        self.assertEqual(r['evaluation_counts']['1:bus1:0x182'],22500)
        self.assertEqual(r['evaluation_counts']['1:bus1:0x282'],4500)
        self.assertFalse(r['HR_RR_simultaneous_engineering_pass'])
    def test_sequence_gap(self):
        rows=fixture();r=d.assess(rows[:200]+rows[201:]);self.assertIn('SERIAL_SEQUENCE_GAP',r['failures'])
    def test_second_boot(self):
        r=d.assess(fixture()+[dict(fixture()[0],seq=fixture()[-1]['seq']+1)])
        self.assertIn('SECOND_BOOT_OBSERVED',r['failures'])
    def test_model_values_mismatch(self):
        rows=list(fixture());idx=next(i for i,r in enumerate(rows) if r['kind']==8 and r['id']==4 and 45000<=r['tick']<135000)
        rows[idx]=dict(rows[idx],data=struct.pack('<iI',123456,0).hex())
        self.assertIn('MODEL_VALUE_OR_SAMPLE_TIME_MISMATCH',d.assess(rows)['failures'])
    def test_no_stop_not_pass(self):
        self.assertIn('STOP_NOT_CAPTURED',d.assess(fixture()[:-1])['failures'])
    def test_truncated_negative(self):
        self.assertIn('TRUNCATED_SERIAL_PACKET',d.assess(fixture(),tail_bytes=20)['failures'])
    def test_crc_negative(self):
        self.assertIn('SERIAL_CRC_ERROR',d.assess(fixture(),crc_errors=1)['failures'])
    def test_unknown_input_never_pass(self):self.assertEqual(d.assess([])['status'],'NOT_PASS')
    def test_stop_drop_counter_not_hidden_by_last_diag(self):
        rows=list(fixture());rows[-1]=dict(rows[-1],data=struct.pack('<II',180000,1).hex())
        self.assertIn('CAPTURE_RING_DROP',d.assess(rows)['failures'])
    def test_resync_after_boot_not_ignored(self):
        self.assertIn('SERIAL_RESYNC_AFTER_BOOT',d.assess(fixture(),discarded_after_boot=1)['failures'])
    def test_C_error_counter_in_evaluation(self):
        rows=list(fixture());i=next(i for i,r in enumerate(rows) if r['kind']==5 and r['id']==1 and r['tick']==50000)
        rows[i]=dict(rows[i],data=struct.pack('<II',1<<16,0).hex())
        self.assertIn('C_CAN2_ERROR_COUNTER_IN_EVALUATION',d.assess(rows)['failures'])
if __name__=='__main__':unittest.main(verbosity=2)
