"""实际诊断解析器的错误拒绝与原始点核对；不访问设备。"""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import field01_can_capture as p


def fixture():
    rows = []
    def add(kind, bus, ident, tick, data=b'', flags=0):
        rows.append(dict(kind=kind, bus=bus, id=ident, tick=tick, dlc=len(data),
            data=data.ljust(8, b'\0').hex(), flags=flags, seq=len(rows)+1, wire_crc_before=0, wire_discarded_before=0))
    add(9, 1, 0, 0, b'\0'*8)
    for tick in range(0, 60000, 500):
        for node, bus in p.NODES.items():
            add(1, bus, 0x700+node, tick, b'\x05')
    for ident, (node, stream, step) in p.WAVES.items():
        values = [100+i for i in range(100 if stream==4 else 50)]
        for i, value in enumerate(values):
            add(1, p.NODES[node], ident, i*step, struct.pack('<iI', value, i*step))
        add(8, p.NODES[node], stream, 1000, struct.pack('<iI', values[-1], p.codec.value_hash(values)), node|256|(len(values)<<16))
        add(10, p.NODES[node], stream, 1000, struct.pack('<Q', 1577836800000+(len(values)-1)*step), 1)
    for ident, a, b in ((0,0,100),(1,0,100),(2,0,2),(4,0x08000000,0),(5,10,0),(8,10,0),(10,0,0),(11,0,0)):
        add(5,1,ident,59000,struct.pack('<II',a,b))
    add(5,1,7,59000,struct.pack('<II',60000,500000),2)
    add(6,1,0,60000,struct.pack('<II',60000,0))
    return rows


class Checks(unittest.TestCase):
    def evaluate(self, rows):
        return p.assess(rows, p.codec.Parser())

    def test_five_source_routes_and_real_point_hashes(self):
        result=self.evaluate(fixture())
        self.assertEqual(result['failures'], [])
        self.assertEqual(result['waveform_model_hash_matches'], 3)
        self.assertTrue(all(v==120 for v in result['source_OP5_heartbeat_counts'].values()))
        self.assertEqual(result['formal_five_CAN_300s'], 'NOT_RUN')

    def test_wrong_bus_or_missing_node_is_rejected(self):
        rows=fixture();rows[1]['bus']=1
        self.assertIn('UNKNOWN_OR_WRONG_BUS_NODE', self.evaluate(rows)['failures'])
        rows=[r for r in fixture() if r['id']!=0x705]
        self.assertIn('SOURCE_HEARTBEAT_COVERAGE', self.evaluate(rows)['failures'])

    def test_both_CAN_error_counters_and_drop_are_rejected(self):
        for ident, a, b, flags in ((0,0x10000,100,0),(1,4,100,0),(2,1,2,0),(8,10,1,0)):
            with self.subTest(ident=ident):
                rows=fixture();row=next(r for r in rows if r['kind']==5 and r['id']==ident)
                row.update(data=struct.pack('<II',a,b).hex(),flags=flags)
                self.assertTrue(self.evaluate(rows)['failures'])

    def test_old_small_image_wrong_stop_and_model_corruption_rejected(self):
        rows=fixture();next(r for r in rows if r['kind']==5 and r['id']==7)['flags']=1
        self.assertIn('C_NOT_FIVE_FULL_60S_IMAGE', self.evaluate(rows)['failures'])
        rows=fixture();rows[-1]['data']=struct.pack('<II',15000,0).hex()
        self.assertIn('STOP_LIMIT_ERROR_OR_CAPTURE_DROP', self.evaluate(rows)['failures'])
        rows=fixture();next(r for r in rows if r['kind']==8)['data']='00'*8
        self.assertIn('WAVE_MODEL_NOT_FOUND_IN_RAW_CAN', self.evaluate(rows)['failures'])

    def test_native_frame_decoder_and_error_source(self):
        row=dict(kind=1,bus=1,id=0x84,dlc=8,data='1081100000000000',flags=0)
        with self.assertRaisesRegex(ValueError,'SOURCE_EMCY'):
            p.check_row(row)

    def test_capture_arms_after_real_RX_counters_then_collects_without_prearm_HB(self):
        import tempfile
        import binascii
        rows=fixture()
        def packet(row):
            raw=bytearray(32);raw[:4]=bytes((0xb4,0xc4,1,row['kind']))
            raw[4:6]=bytes((row['bus'],row['dlc']))
            struct.pack_into('<HII',raw,6,row['id'],row['tick'],row['seq'])
            raw[16:24]=bytes.fromhex(row['data']);struct.pack_into('<I',raw,24,row['flags'])
            struct.pack_into('<H',raw,30,binascii.crc_hqx(raw[:30],0xffff))
            return bytes(raw)
        pre=[dict(r) for r in rows if r['kind']==5]
        for i,r in enumerate(pre):r['seq']=i+1
        body=[dict(r,seq=r['seq']+len(pre)) for r in rows]
        class Port:
            def __init__(self):self.data=[b''.join(map(packet,pre)),b''.join(map(packet,body))];self.writes=[]
            def read(self,n):return self.data.pop(0) if self.data else b''
            def write(self,b):self.writes.append(b);return len(b)
            def flush(self):pass
        with tempfile.TemporaryDirectory() as folder:
            port=Port();result=p.capture(port,Path(folder))
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(port.writes,[b'B4START\n'])


if __name__ == '__main__':
    unittest.main()
