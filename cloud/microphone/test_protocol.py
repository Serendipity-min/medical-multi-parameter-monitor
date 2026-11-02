import pathlib
import struct
import unittest
import zlib
from protocol import AudioAssembler,HEADER,reply_packet


def packets():
    pcm=bytes(range(256))*250;whole=zlib.crc32(pcm)
    return [HEADER.pack(b'MC01',7,n,125,16000,64000,whole,zlib.crc32(pcm[n*512:(n+1)*512]),512,
                        (1 if n==0 else 0)|(2 if n==124 else 0),1)+pcm[n*512:(n+1)*512] for n in range(125)]


class ProtocolChecks(unittest.TestCase):
    def test_exact_complete_and_duplicate(self):
        a=AudioAssembler();p=packets();self.assertIsNone(a.feed('C',p[0],0));self.assertIsNone(a.feed('C',p[0],1))
        for packet in p[1:]:result=a.feed('C',packet,2)
        self.assertEqual(result['pcm'],bytes(range(256))*250);self.assertEqual(result['chunks'],125)
        with self.assertRaises(ValueError):a.feed('C',p[0],3)

    def test_missing_reordered_expired_changed_duplicate(self):
        for mode in ('missing','reordered','expired','changed','session'):
            a=AudioAssembler();p=packets();a.feed('C',p[0],0)
            if mode=='missing':bad=p[2];at=1
            elif mode=='reordered':bad=p[124];at=1
            elif mode=='expired':bad=p[1];at=90
            elif mode=='changed':
                bad=bytearray(p[0]);bad[32]^=1;struct.pack_into('<I',bad,24,zlib.crc32(bad[32:]));at=1
            else:bad=bytearray(p[1]);struct.pack_into('<I',bad,4,8);at=1
            with self.assertRaises(ValueError):a.feed('C',bad,at)

    def test_bounds_header_and_whole_crc(self):
        p=packets()
        for offset in (0,10,12,16,24,28,30,31,33):
            bad=bytearray(p[0]);bad[offset]^=0xff
            with self.assertRaises(ValueError):AudioAssembler().feed('C',bad,0)
        bad=bytearray(p[0]);struct.pack_into('<I',bad,4,0)
        with self.assertRaises(ValueError):AudioAssembler().feed('C',bad,0)
        for size in (0,31,543,545):
            with self.assertRaises(ValueError):AudioAssembler().feed('C',p[0][:size] if size<544 else p[0]+b'0',0)
        a=AudioAssembler()
        for n,packet in enumerate(p):
            bad=bytearray(packet);struct.pack_into('<I',bad,20,123)
            if n==124:
                with self.assertRaises(ValueError):a.feed('C',bad,1)
            else:a.feed('C',bad,1)

    def test_host_separate_and_reply(self):
        a=AudioAssembler();p=packets();a.feed('HOST',p[0],0)
        with self.assertRaises(ValueError):a.feed('C',p[1],1)
        self.assertEqual(reply_packet(7,8,'hello')[:4],b'MR01')
        for text in ('','x'*61,'[v9]','hidden\u200b','bad\x00'):
            with self.assertRaises(ValueError):reply_packet(7,8,text)


if __name__=='__main__':unittest.main()
