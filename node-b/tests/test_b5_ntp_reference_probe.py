import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_ntp_reference_probe as n


class Tests(unittest.TestCase):
    def reply(self):
        b=bytearray(48);b[0]=0x24;b[1]=2;b[24:32]=b'12345678';struct.pack_into('!II',b,40,1793080000+2208988800,0);return b
    def test_quoted_and_plain_documentation_addresses_parse(self):
        for text in (b'+CIPDOMAIN:"192.0.2.1"',b'+CIPDOMAIN:192.0.2.1'):
            self.assertEqual(n.address_from_reply(b'\r\n'+text+b'\r\n\r\nOK\r\n'),'192.0.2.1')
    def test_no_reply_or_unsafe_address_rejected(self):
        for raw in (b'ERROR\r\n',b'\r\n+CIPDOMAIN:0.0.0.0\r\n\r\nOK\r\n'):
            with self.assertRaises(ValueError):n.address_from_reply(raw)
    def test_fresh_matching_reply_validates(self):
        self.assertTrue(n.packet_check(self.reply(),b'12345678',.05)['valid'])
    def test_stale_nonce_wrong_mode_KOD_length_and_slow_rejected(self):
        self.assertFalse(n.packet_check(self.reply(),b'badnonce',.05)['valid'])
        for index,value in ((0,0xe4),(0,0x23),(1,0)):
            b=self.reply();b[index]=value;self.assertFalse(n.packet_check(b,b'12345678',.05)['valid'])
        self.assertFalse(n.packet_check(bytes(47),b'12345678',.05)['valid'])
        self.assertFalse(n.packet_check(self.reply(),b'12345678',2)['valid'])


if __name__=='__main__':unittest.main()
