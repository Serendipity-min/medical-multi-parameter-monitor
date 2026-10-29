import io,json,tempfile,unittest
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_g3_contract as g
import b5_g3_joint as j

class StopSource(unittest.TestCase):
    line='B5 STOP_STATE tick=420100 armed_at=100 reason=1 phase=7 required=100 written=100 unsynced=0 pending=0 live=0 cache=0'
    def test_exact_deadline_and_wrap(self):
        self.assertEqual(g.parse_stop_state(self.line)['business_elapsed_ms'],420000)
        self.assertEqual(g.parse_stop_state(self.line.replace('tick=420100 armed_at=100','tick=419900 armed_at=4294967196'))['business_elapsed_ms'],420000)
    def test_missing_or_extra_fields_rejected(self):
        for line in (self.line.replace(' cache=0',''),self.line+' unknown=0'):
            with self.assertRaisesRegex(ValueError,'STOP_SOURCE_SCHEMA'):g.parse_stop_state(line)
    def test_same_block_error_cannot_hide_stop(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(g,'save',side_effect=lambda p,d:Path(p).write_text(json.dumps(d))):
            stream=io.StringIO();root=Path(tmp)
            data=('GW WRITE_SEND_FAIL\r\nB5 STOPPED NO_AUTOREARM\r\n'+self.line+'\r\n').encode()
            pending,lines,at=j.record_lines(data,stream,root,True,None)
            self.assertEqual(pending,b'');self.assertEqual(len(stream.getvalue().splitlines()),3)
            self.assertTrue((root/'C_STOP_BANNER.json').exists());self.assertTrue((root/'C_STOP_SOURCE_STATE.json').exists())
    def test_malformed_source_still_preserves_all_raw_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream=io.StringIO()
            with self.assertRaises(ValueError):j.record_lines(b'B5 STOP_STATE bad=1\nfollowing line\n',stream,Path(tmp),True,None)
            self.assertIn('following line',stream.getvalue())

if __name__=='__main__':unittest.main()
