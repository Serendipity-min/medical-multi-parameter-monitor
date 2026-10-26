"""B5 C跨32KiB需独立授权；只用已有NOR/SDK替身，不接触真实DLL。"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import test_b4_swd_install as fixtures
w=fixtures.w


class B5ScopeTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.InstallTests('test_B_restore_exact_full_original');self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.m,self.payload=self.f.make('B');self.m['board_role']='C'
        self.a={'enabled':True,'owner_approved':True,'scope':w.B5_SCOPE,'nonhuman_mock':True,
                'tools_sha256':w.bindings(),'DLL_sha256':w.raw.DLL_SHA,'expires_unix':w.time.time()+30,
                'phase':'install','board':'C','package':str(self.f.out),'manifest_sha256':'0'*64,
                'candidate_sha256':self.m['candidate_sha256'],
                'installed_full_sha256':self.m['files']['expected-full-private.bin']['sha256'],
                'site':{'P4_RX_PB12_TX_PB13':True,'B_P6_CAN1':True,'ESP_isolated':True,
                        'A_bus_disconnected':True,'termination_ohms':60.8,'no_human':True,
                        'target_power_ready':True,'power_sources':{'B':'OFF','C':'J5'}}}

    def authorize(self):
        with patch.object(w.package,'load_package',return_value=(self.m,self.payload)):
            return w.authorize(self.a)

    def test_new_C012_scope_and_unchanged_config(self):
        self.assertEqual(self.authorize()[0]['sectors'],[0,1,2])
        self.assertEqual(self.payload['expected-full-private.bin'][49152:],self.f.original[49152:])

    def test_old_C_scope_does_not_expand(self):
        self.a['scope']=w.SCOPE
        with self.assertRaisesRegex(ValueError,'INSTALL_SECTOR_SCOPE'):self.authorize()

    def test_DISABLED_and_non_mock_refused(self):
        self.a['enabled']=False
        with self.assertRaises(ValueError):self.authorize()
        self.a['enabled']=True;self.a['nonhuman_mock']=False
        with self.assertRaisesRegex(ValueError,'B5_INSTALL_ROLE_AND_SOURCE'):self.authorize()

    def test_sector3_and_config_write_never_authorized(self):
        self.m['sectors']=[0,1,2,3]
        with self.assertRaisesRegex(ValueError,'INSTALL_SECTOR_SCOPE'):self.authorize()


if __name__=='__main__':unittest.main()
