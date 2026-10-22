"""链路判据合成负例；寄存器GPIO输入位允许变化，错误/停计数不能PASS。"""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from precheck_b import decode, assess, BioLink


def observation(at,count):
    diag=[0x324f4942,2,count,count,count*4]+[0]*21+[0.0]*4
    stats=[count,count,count,0,0,0,1,0,0,670000,675000,25000]
    regs=bytes.fromhex('7301e0f04040ec00ffea030f')
    o=decode(struct.pack('<26I4f',*diag),struct.pack('<12I',*stats),regs)
    o['host_mid_s']=at
    return o


class Cases(unittest.TestCase):
    def test_good_and_masked_gpio(self):
        self.assertEqual(assess([observation(0,100),observation(5,1350)])['status'],'OPEN_INPUT_LINK_CHECK_PASS')

    def test_init_failure_no_sampling(self):
        observations=[observation(0,0),observation(5,0)]
        observations[-1]['adc']['init_errors']=1
        result=assess(observations)
        self.assertIn('ADC_INIT_ERRORS',result['errors'])
        self.assertIn('BIO_NOT_ADVANCING',result['errors'])

    def test_register_mismatch(self):
        observations=[observation(0,100),observation(5,1350)]
        observations[0]['registers_hex']='00'*12
        self.assertEqual(assess(observations)['status'],'OPEN_INPUT_LINK_CHECK_FAIL')

    def test_wrong_abi_and_range(self):
        with self.assertRaisesRegex(RuntimeError,'BIO_ABI_MISMATCH'):decode(b'\0'*120,b'\0'*48,b'\0'*12)
        link=BioLink.__new__(BioLink)
        with self.assertRaisesRegex(RuntimeError,'BIO_READ_RANGE_DENIED'):link.read(0x2000020c,48)


if __name__=='__main__':unittest.main(verbosity=2)
