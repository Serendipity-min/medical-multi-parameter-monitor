"""三板观察适配：双节点会话、来源和C候选识别；无设备/网络。"""
import copy
import unittest

import abc_two_group as abc


class ABCReadiness(unittest.TestCase):
    def snapshot(self,profile='ECG60'):
        streams=[]
        for node,names in (('NODE-A',('SpO2','PR')),('NODE-B',('HR','RR','TEMP','ECG','RESP'))):
            for name in names:
                streams.append({'node_id':node,'stream':name,'session_id':'can-123456-1',
                    'validity':'INVALID' if node=='NODE-A' else 'VALID','source':'MOCK','synthetic':True,
                    'value':None if node=='NODE-A' else {'HR':60,'RR':18,'TEMP':26}.get(name),
                    'samples':[1,2] if name in ('ECG','RESP') else []})
        return {'gateway_id':'GW-B5-001','gateway_state':'ONLINE','nodes':{'NODE-A':'ONLINE','NODE-B':'ONLINE'},'streams':streams}

    def test_both_nodes_required_but_NIBP_arrives_after_manual_measurement(self):
        s=self.snapshot();abc.validate_snapshot(s)
        self.assertEqual(abc.current_sessions(s,'can-123456-1','ECG60'),'can-123456-1')
        s['nodes']['NODE-A']='OFFLINE';self.assertIsNone(abc.current_sessions(s,'can-123456-1','ECG60'))

    def test_RR18_does_not_require_or_force_valid_HR(self):
        s=self.snapshot()
        for x in s['streams']:
            if x['stream']=='HR':x.update(validity='INVALID',value=None)
        self.assertEqual(abc.current_sessions(s,'can-123456-1','RR18'),'can-123456-1')
        self.assertIsNone(next(x for x in s['streams'] if x['stream']=='HR')['value'])

    def test_prior_stale_NIBP_does_not_deadlock_manual_new_measurement_after_T0(self):
        s=self.snapshot();s['streams'].append({'node_id':'NODE-A','stream':'NIBP','session_id':'can-OLD-1',
            'validity':'STALE','value':None,'samples':[],'source':'MOCK','synthetic':True})
        self.assertEqual(abc.current_sessions(s,'can-123456-1','ECG60'),'can-123456-1')
        s['streams'][-1].update(validity='VALID',value=[120,80])
        self.assertIsNone(abc.current_sessions(s,'can-123456-1','ECG60'))

    def test_old_session_wrong_rate_or_stale_TEMP_cannot_establish_T0(self):
        for channel,changes in (('PR',{'session_id':'can-OLD-1'}),('HR',{'value':90}),('TEMP',{'validity':'STALE','value':None})):
            s=self.snapshot();next(x for x in s['streams'] if x['stream']==channel).update(changes)
            self.assertIsNone(abc.current_sessions(s,'can-123456-1','ECG60'))

    def test_invalid_payload_or_false_LIVE_source_rejected(self):
        for changes in ({'source':'LIVE'},{'synthetic':False},{'value':98}):
            s=self.snapshot();s['streams'][0].update(changes)
            with self.assertRaises(ValueError):abc.validate_snapshot(s)

    def test_actual_ABC_banner_and_A_transport_errors(self):
        gate=abc.SerialGate();gate.consume(abc.BANNER);self.assertEqual(gate.banner,1)
        gate.consume('ABC A_CAN rx=1 txack=1 txfail=0 overflow=0 esr=0',True)
        with self.assertRaises(ValueError):gate.consume('ABC A_CAN rx=1 txack=1 txfail=1 overflow=0 esr=0',True)
        with self.assertRaises(ValueError):abc.SerialGate().consume('B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE')


if __name__=='__main__':unittest.main()
