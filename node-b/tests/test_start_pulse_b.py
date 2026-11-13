"""START脉冲范围/失败保护合成验证；不加载真实DLL。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import start_pulse_b as module
from test_install_b import Function


class Fake:
    def __init__(self,fail=False):
        self.dll=type('DLL',(),{'JLINKARM_WriteU32':Function()})()
        self.writes=[];self.high=True;self.fail=fail
    def u32(self,a):return {0x40021800:0x40000000,0x40021814:0x8000 if self.high else 0,0xe000edf0:0,0x40020010:8}[a]
    def read(self,a,n):return b'\1'
    def call(self,name,address,value):
        assert name=='JLINKARM_WriteU32' and address==0x40021818
        self.writes.append((address,value))
        if self.fail:return -1
        self.high=value==0x8000;return 0


class Cases(unittest.TestCase):
    def test_exact_pin_writes_and_failure_stop(self):
        observation={'adc':{'init_errors':0,'irq_count':0}}
        for failure in (False,True):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as folder:
                link=Fake(failure);receipt={'gpio_write_attempts':0}
                with patch.object(module,'sample',return_value=observation),patch.object(module,'assess',return_value={'status':'SYNTHETIC'}),patch.object(module.time,'sleep'):
                    if failure:
                        with self.assertRaisesRegex(RuntimeError,'START_WRITE_FAILED'):module.pulse(link,Path(folder),receipt)
                        self.assertEqual(len(link.writes),1)
                    else:
                        module.pulse(link,Path(folder),receipt)
                        self.assertEqual(link.writes,[(0x40021818,0x80000000),(0x40021818,0x8000)])
                        self.assertEqual(receipt['start_last_command'],'HIGH')


if __name__=='__main__':unittest.main(verbosity=2)
