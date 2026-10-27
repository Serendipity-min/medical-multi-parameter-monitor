"""新resume-only入口定向验证；全程合成数据，无SSH或服务操作。"""
import copy
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'node-b/tools'))
import b5_g1_resume as r

class Connection:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def sendall(self,request):self.request=request
    def recv(self,n):
        if getattr(self,'sent',False):return b''
        self.sent=True
        return b'HTTP/1.0 200 OK\r\n\r\n{"status":"ok","mqtt_connected":true}'

class Tests(unittest.TestCase):
    def inputs(self):return {'own_units':{'backend':'medical-monitor-b5-SYNTH-backend.service',
        'tls':'medical-monitor-b5-SYNTH-tls.service'},'server_name':'example.invalid','mode_references':[]}
    def state(self,started=False):return {
        'formal_services_active':True,'formal_service_PIDs_match_last_G1':True,
        'config_sha256':{'TEST':{'matches_last_approved_G1':True}},
        'test_identity_ACL_residual':{'publisher':True,'observer':True},
        'listeners':{'18775':started,'8884':False},
        'both_test_units_stopped_with_RuntimeMax_timeout':not started,
        'own_units':{n:{'ActiveState':'active' if started else 'failed','MainPID':'9' if started else '0',
        'Restart':'no','RuntimeMaxUSec':'6h'} for n in ('backend','tls')}}
    def run_remote(self,before=None,codes=(0,0),inputs=None,tls_failure=False):
        context=types.SimpleNamespace(wrap_socket=lambda raw,server_hostname: Connection())
        with patch.dict(sys.modules,{'pwd':types.SimpleNamespace(getpwuid=lambda uid:types.SimpleNamespace(pw_name='root'))}), \
             patch.object(r,'remote_lifecycle',side_effect=[before or self.state(),self.state(True)]), \
             patch('subprocess.run',side_effect=[types.SimpleNamespace(returncode=c) for c in codes]) as process, \
             patch('socket.create_connection',side_effect=OSError('SYNTHETIC_TLS') if tls_failure else None,
                   return_value=Connection()),patch('ssl.create_default_context',return_value=context) as sslctx, \
             patch('time.sleep'),patch('time.monotonic',side_effect=iter(range(0,1000,15)) if tls_failure else None,
                                       return_value=1):
            result=r.remote_resume(inputs or self.inputs())
            return result,process.call_args_list,sslctx.call_count
    def test_only_two_existing_units_started_on_success(self):
        result,calls,tls=self.run_remote()
        self.assertEqual(result['exit_code'],0);self.assertEqual(len(calls),2)
        self.assertEqual([c.args[0] for c in calls],[['systemctl','start',self.inputs()['own_units'][n]] for n in ('backend','tls')])
        self.assertGreater(tls,0);self.assertEqual(result['B5START'],0)
    def test_formal_drift_prevents_all_starts(self):
        s=self.state();s['formal_service_PIDs_match_last_G1']=False
        result,calls,_=self.run_remote(before=s)
        self.assertEqual(result['exit_code'],1);self.assertEqual(calls,[])
    def test_occupied_port_prevents_all_starts(self):
        s=self.state();s['listeners']['18775']=True
        result,calls,_=self.run_remote(before=s)
        self.assertEqual(result['exit_code'],1);self.assertEqual(calls,[])
    def test_config_or_ACL_drift_prevents_all_starts(self):
        for key in ('config','acl'):
            s=self.state()
            if key=='config':s['config_sha256']['TEST']['matches_last_approved_G1']=False
            else:s['test_identity_ACL_residual']['publisher']=False
            result,calls,_=self.run_remote(before=s)
            self.assertEqual(result['exit_code'],1);self.assertEqual(calls,[])
    def test_formal_unit_substitution_prevents_all_starts(self):
        i=self.inputs();i['own_units']['backend']='medical-monitor.service'
        result,calls,_=self.run_remote(inputs=i)
        self.assertEqual(result['exit_code'],1);self.assertEqual(calls,[])
    def test_bad_private_file_permissions_prevent_all_starts(self):
        i=self.inputs();i['mode_references']=[{'path':'SYNTHETIC_ONLY','mode':0o600,'owner':'root'}]
        with patch('pathlib.Path.stat',return_value=types.SimpleNamespace(st_mode=0o100777,st_uid=0,st_gid=0)):
            result,calls,_=self.run_remote(inputs=i)
        self.assertEqual(result['exit_code'],1);self.assertEqual(calls,[])
        self.assertEqual(result['reason'],'RESUME_FILE_PERMISSION')
    def test_failed_start_is_not_retried_and_no_rollback(self):
        result,calls,_=self.run_remote(codes=(1,))
        self.assertEqual(result['exit_code'],1);self.assertEqual(len(calls),1)
        self.assertFalse(result['automatic_retry_or_rollback'])
    def test_tls_failure_stops_without_extra_start_or_certificate_bypass(self):
        result,calls,_=self.run_remote(tls_failure=True)
        self.assertEqual(result['exit_code'],1);self.assertEqual(len(calls),2)
        self.assertEqual(result['reason'],'RESUME_TLS_BACKEND_HEALTH_NOT_READY')
    def test_default_has_no_execute_and_old_G1_scope_denied(self):
        with patch.object(sys,'argv',['resume']),patch('sys.stdout',io.StringIO()),patch.object(r,'execute') as execute:
            self.assertEqual(r.main(),0);execute.assert_not_called()
        with self.assertRaisesRegex(ValueError,'OWNER_SCOPE'):
            r.authorize({'enabled':True,'owner_approved':True,'scope':'B5_G1_A'})

if __name__=='__main__':unittest.main()
