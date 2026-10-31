"""血压源证据必须绑定实际完成代次，不能用旧值或本地generation替代boot。"""
import copy
import unittest

from abc_two_group_review import nibp_source_match


class SourceProof(unittest.TestCase):
    def setUp(self):
        self.message={'node_id':'NODE-A','stream':'NIBP','validity':'VALID','value':[120.0,80.0],
                      'seq':1,'session_id':'can-12345-2'}
        self.state={'completion':10000,'emitted_tick':10000,'emitted':1,'flags':(1<<3)|(1<<9),
                    'packed':1200|(800<<16),'nibp_seq':1,'boot':2,'gen':9}

    def test_actual_seq_and_observed_boot(self):
        self.assertTrue(nibp_source_match(self.message,self.state))

    def test_old_completion_invalid_flags_or_wrong_packed_value_rejected(self):
        for changes in ({'completion':0},{'emitted_tick':9999},{'flags':1<<3},{'packed':1200|(810<<16)}):
            state={**self.state,**changes};self.assertFalse(nibp_source_match(self.message,state))

    def test_new_same_value_needs_matching_new_seq_boot_and_completion(self):
        for changes in ({'nibp_seq':2},{'boot':9}):
            self.assertFalse(nibp_source_match(self.message,{**self.state,**changes}))
        message=copy.deepcopy(self.message);message.update(seq=2,session_id='can-67890-3')
        state={**self.state,'nibp_seq':2,'boot':3,'completion':20000,'emitted_tick':20000}
        self.assertTrue(nibp_source_match(message,state))


if __name__=='__main__':unittest.main()
