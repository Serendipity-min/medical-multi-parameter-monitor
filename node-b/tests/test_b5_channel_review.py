import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_channel_review as r

class UartEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);(self.folder/'B').mkdir()
        self.clock={(1700000000,1000,1000,1)}
    def capture(self,corrupt=False):
        frame=bytearray.fromhex('a4030707620ceb0c3f0e2087')
        if corrupt:frame[-1]^=1
        data=bytes(frame)*10;blob=bytearray(1088)
        for n,byte in enumerate(data):struct.pack_into('<IB',blob,n*8,1000+(n//12)*200,byte)
        struct.pack_into('<I',blob,1024,len(data))
        (self.folder/'B/UART4-ring-private.bin').write_bytes(blob*2)
        rows=[{'data':{'offset':i*1088,'sha256':r.g.sha(blob)}} for i in range(2)]
        (self.folder/'B/UART4-ring-private.jsonl').write_text('\n'.join(map(json.dumps,rows)))
    def test_stable_raw_bytes_yield_real_frames(self):
        self.capture();frames,meta=r.uart_frames(self.folder,self.clock)
        self.assertEqual(len(frames),8);self.assertEqual(meta['stable_bytes'],104)
        self.assertEqual(frames[0]['object_centi'],3307);self.assertEqual(frames[0]['UTC_candidates'],[1700000000000])
    def test_checksum_bad_never_source(self):
        self.capture(True);frames,_=r.uart_frames(self.folder,self.clock);self.assertEqual(frames,[])
    def test_container_SHA_drift_rejected(self):
        self.capture();path=self.folder/'B/UART4-ring-private.bin';b=bytearray(path.read_bytes());b[0]^=1;path.write_bytes(b)
        with self.assertRaisesRegex(ValueError,'UART_BLOCK'):r.uart_frames(self.folder,self.clock)
    def test_value_and_report_second_interval(self):
        self.capture();frames,_=r.uart_frames(self.folder,self.clock)
        m={'value':33.07,'timestamp':1700000001000}
        self.assertTrue(r.match_temperature(m,frames))
        self.assertFalse(r.match_temperature(dict(m,value=36.5),frames))
        self.assertFalse(r.match_temperature(dict(m,timestamp=1700000020000),frames))
    def test_no_valid_time_no_matching_source(self):
        self.capture();frames,_=r.uart_frames(self.folder,{(1700000000,1000,1000,0)})
        self.assertFalse(r.match_temperature({'value':33.07,'timestamp':1700000001000},frames))
    def test_single_observation_not_qualified(self):
        self.capture();p=self.folder/'B/UART4-ring-private.bin';p.write_bytes(p.read_bytes()[:1088])
        p=self.folder/'B/UART4-ring-private.jsonl';p.write_text(p.read_text().splitlines()[0])
        frames,_=r.uart_frames(self.folder,self.clock);self.assertFalse(frames)

if __name__=='__main__':unittest.main()
