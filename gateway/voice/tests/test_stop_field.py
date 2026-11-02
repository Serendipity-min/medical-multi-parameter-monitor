import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('stop_field',Path(__file__).resolve().parents[1]/'stop_field.py')
field=importlib.util.module_from_spec(spec);spec.loader.exec_module(field)


class StopProofTests(unittest.TestCase):
    def setUp(self):
        self.events=[{'kind':'TX','byte':v,'ms':i} for i,v in enumerate((0xfd,0,1,2))]
        self.events += [{'kind':'RX','byte':0x41,'ms':5}]
        self.events += [{'kind':'TX','byte':v,'ms':i+6} for i,v in enumerate((0xfd,0,1,0x21))]
        self.events += [{'kind':'RX','byte':0x4f,'ms':11}]
        self.state={'state':0,'enabled':0,'stopping':0,'stop_sent':1,'stop_ack':1,'query_sent':1,
                    'stop_idle':1,'stop_failed':0,'uart_errors':0,'uart_overflow':0}

    def test_actual_transcript_sequence_and_state_required(self):
        self.assertEqual(field.stop_proof(self.events,self.state)['TTS_TX_bytes'],8)

    def test_missing_or_incomplete_query_rejected(self):
        with self.assertRaisesRegex(ValueError,'TX_SEQUENCE'):field.stop_proof(self.events[:5],self.state)

    def test_query_ack_cannot_replace_stop_ack(self):
        self.events[4],self.events[8]=self.events[8],self.events[4]
        with self.assertRaises(ValueError):field.stop_proof(self.events,self.state)

    def test_old_idle_cannot_replace_query_result(self):
        self.events.insert(0,self.events.pop())
        with self.assertRaisesRegex(ValueError,'IDLE_ORDER'):field.stop_proof(self.events,self.state)

    def test_failed_stop_or_uart_error_cannot_pass(self):
        for key in ('stop_failed','uart_errors','uart_overflow'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'FINAL_STATE'):
                field.stop_proof(self.events,{**self.state,key:1})

    def test_native_error_not_hidden_by_final_success_flags(self):
        self.events.append({'kind':'RX','byte':0x45,'ms':12})
        with self.assertRaisesRegex(ValueError,'COMMAND_REJECTED'):field.stop_proof(self.events,self.state)

    def test_error_state_not_accepted_as_normal_owner_stop(self):
        with self.assertRaisesRegex(ValueError,'FINAL_STATE'):
            field.stop_proof(self.events,{**self.state,'state':6})


if __name__=='__main__':unittest.main()
