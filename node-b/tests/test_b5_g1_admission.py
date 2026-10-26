"""G1新增云事务的本地权限/范围负例；不调用SSH、服务或真实Broker。"""
import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'node-b/tools'))
import b5_g1_cloud as g
import b5_g1_supervisor as s


class G1AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.p={'tx':'g1a-1234567890','HUP_limit':1,'smoke_limit_s':120,'negative_namespace':g.DENY}
        self.raw=g.encode(self.p)
        self.a={'enabled':True,'owner_approved':True,'scope':g.SCOPE,'tx':self.p['tx'],
                'package_sha256':g.sha(self.raw),'tool_sha256':g.sha(Path(g.__file__).read_bytes()),
                'supervisor_sha256':g.sha(Path(s.__file__).read_bytes()),'expires_unix':time.time()+120,'rollback_enabled':False}

    def test_exact_offline_binding(self):self.assertTrue(g.authorize(self.a,self.p,self.raw))

    def test_disabled_owner_and_other_scope_denied(self):
        for field,value in [('enabled',False),('owner_approved',False),('scope','B5_G2_APPLICATION')]:
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'OWNER_AUTH'):
                g.authorize({**self.a,field:value},self.p,self.raw)

    def test_package_tool_and_transaction_drift_denied(self):
        for field,value in [('package_sha256','0'*64),('tx','another'),('tool_sha256','0'*64)]:
            with self.subTest(field=field),self.assertRaises(ValueError):g.authorize({**self.a,field:value},self.p,self.raw)

    def test_expired_and_unbounded_auth_denied(self):
        for stamp in [time.time()-1,time.time()+7200]:
            with self.assertRaisesRegex(ValueError,'EXPIRED'):g.authorize({**self.a,'expires_unix':stamp},self.p,self.raw)

    def test_more_HUP_or_other_negative_target_denied(self):
        for field,value in [('HUP_limit',2),('smoke_limit_s',121),('negative_namespace','mpm/v1/GW-C-001/status')]:
            p={**self.p,field:value};raw=g.encode(p)
            with self.assertRaisesRegex(ValueError,'SCOPE_LIMITS'):g.authorize({**self.a,'package_sha256':g.sha(raw)},p,raw)

    def test_rollback_not_implicitly_authorized(self):
        with self.assertRaisesRegex(ValueError,'ROLLBACK_NOT_AUTHORIZED'):g.authorize({**self.a,'rollback_enabled':True},self.p,self.raw)

    def test_supervisor_repeat_and_drift_denied_before_worker(self):
        with tempfile.TemporaryDirectory(prefix='b5-g1-test-',dir=ROOT/'node-b/build') as folder:
            p=Path(folder);(p/'deployment-package-private.json').write_bytes(self.raw)
            with patch.object(s,'protected',side_effect=lambda path,_:Path(path)):
                self.assertEqual(s.check(self.a,p)['tx'],self.p['tx'])
                with self.assertRaisesRegex(ValueError,'SUPERVISOR_BINDING'):s.check({**self.a,'supervisor_sha256':'0'*64},p)
                (p/'G1-apply-supervisor-started-private.json').write_bytes(b'{}')
                with self.assertRaisesRegex(ValueError,'ALREADY_ATTEMPTED'):s.check(self.a,p)

    def test_supervisor_smoke_binding_and_unapproved_phase(self):
        with tempfile.TemporaryDirectory(prefix='b5-g1-test-',dir=ROOT/'node-b/build') as folder:
            p=Path(folder);(p/'deployment-package-private.json').write_bytes(self.raw)
            with patch.object(s,'protected',side_effect=lambda path,_:Path(path)):
                with self.assertRaisesRegex(ValueError,'PHASE_DENIED'):s.check(self.a,p,'rollback')
                with self.assertRaisesRegex(ValueError,'SMOKE_TOOL_BINDING'):s.check(self.a,p,'smoke')

    def test_payload_isolated_gateway_loopback_and_no_restart(self):
        snapshot={'backend':{'host':'broker.invalid'},'cert_path':'/synthetic/cert.pem','key_path':'/synthetic/key.pem','python':'/synthetic/python'}
        base,origin,files=g.payload_files(snapshot,self.p['tx'],'synthetic-publisher','synthetic-observer','synthetic-view-token')
        self.assertEqual(origin,'https://broker.invalid:18775')
        self.assertIn(b'listen 127.0.0.1:18775 ssl;',files['nginx.conf'])
        self.assertIn(b'MONITOR_GATEWAY_IDS=GW-B5-001\n',files['backend.env'])
        self.assertNotIn(b'GW-C-001',b''.join(files.values()))
        self.assertIn(b'Restart=no',files['backend.service']);self.assertIn(b'RuntimeMaxSec=21600',files['backend.service'])
        self.assertIn(b'/medical-monitor/ai { return 404;',files['nginx.conf'])
        for name in ['client_body_temp_path','proxy_temp_path','fastcgi_temp_path','uwsgi_temp_path','scgi_temp_path']:
            self.assertIn((name+' '+base+'/nginx/').encode(),files['nginx.conf'])
        self.assertIn(('lock_file '+base+'/run/nginx.lock;').encode(),files['nginx.conf'])
        self.assertEqual(json.loads(files['backend.json'])['client_id'],'b5-backend-isolated')


if __name__=='__main__':unittest.main()
