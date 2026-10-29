import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_g3_joint as j

class SerialCompletion(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.auth=dict(reset_confirmation='SERIAL_DISARMED_AFTER_INTENT',owner_manual_reset_preapproved=True,operator_wait_extra_s=180)
    def confirm(self,now):
        with patch.object(j.g,'maybe',side_effect=lambda p:json.loads(Path(p).read_text()) if Path(p).exists() else None),\
             patch.object(j.g,'save',side_effect=lambda p,v:Path(p).write_text(json.dumps(v))):
            j.confirm_serial_reset(self.root,self.auth,now)
    def test_no_intent_no_automatic_confirmation(self):
        with self.assertRaisesRegex(ValueError,'WITHOUT_APPROVED_INTENT'):self.confirm(101)
    def test_new_banner_after_intent_confirms_without_chat(self):
        (self.root/'RESET_REQUESTED.json').write_text(json.dumps({'monotonic':100}))
        self.confirm(200);r=json.loads((self.root/'C_RESET_OWNER_DONE.json').read_text())
        self.assertEqual(r['monotonic'],200);self.assertFalse(r['owner_chat_ack_required']);self.assertFalse(r['physical_reset_cause_proven'])
    def test_pre_intent_or_out_of_budget_stops(self):
        (self.root/'RESET_REQUESTED.json').write_text(json.dumps({'monotonic':100}))
        for t in (99,401):
            with self.assertRaisesRegex(ValueError,'WITHOUT_APPROVED_INTENT'):self.confirm(t)
    def test_explicit_owner_preapproval_required(self):
        (self.root/'RESET_REQUESTED.json').write_text(json.dumps({'monotonic':100}));self.auth['owner_manual_reset_preapproved']=False
        with self.assertRaisesRegex(ValueError,'WITHOUT_APPROVED_INTENT'):self.confirm(101)
    def test_legacy_mode_still_waits_for_owner_chat(self):
        self.auth={};self.confirm(101);self.assertFalse((self.root/'C_RESET_OWNER_DONE.json').exists())
    def test_thirty_second_start_gate_not_changed(self):
        self.assertEqual(j.g.CRITERIA['manual_reset_ack_max_s'],30)

if __name__=='__main__':unittest.main()
