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

    def test_new_start_replaces_interrupted_session_before_and_after_expiry(self):
        for start in (10,100):
            a=AudioAssembler();old=packets()
            for p in old[:9]:a.feed('C',p,0)
            result=None
            for p in old:
                fresh=bytearray(p);struct.pack_into('<I',fresh,4,8)
                result=a.feed('C',fresh,start)
            self.assertEqual(result['session'],8)
            self.assertEqual(result['pcm'],bytes(range(256))*250)

    def test_duplicate_does_not_renew_expiry_and_old_start_is_rejected(self):
        p=packets();a=AudioAssembler();a.feed('C',p[0],0);a.feed('C',p[0],80)
        with self.assertRaises(ValueError):a.feed('C',p[1],90)
        a=AudioAssembler();fresh=bytearray(p[0]);struct.pack_into('<I',fresh,4,8)
        a.feed('C',fresh,0)
        with self.assertRaises(ValueError):a.feed('C',p[0],1)

    def test_completed_replay_stays_rejected_after_partial_is_replaced(self):
        a=AudioAssembler();old=packets()
        for p in old:a.feed('C',p,0)
        fresh=bytearray(old[0]);struct.pack_into('<I',fresh,4,8);a.feed('C',fresh,1)
        newer=bytearray(old[0]);struct.pack_into('<I',newer,4,9);a.feed('C',newer,1)
        with self.assertRaises(ValueError):a.feed('C',old[0],2)
        self.assertEqual(a.active['C']['session'],9)

    def test_m0_180_seconds_stays_bounded_without_duplicate_renewal(self):
        p=packets();a=AudioAssembler(timeout_s=180)
        for n,packet in enumerate(p):result=a.feed('C',packet,n*100/124)
        self.assertEqual(result['chunks'],125)
        self.assertEqual(result['pcm'],bytes(range(256))*250)
        a=AudioAssembler(timeout_s=180);a.feed('C',p[0],0);a.feed('C',p[0],179)
        with self.assertRaises(ValueError):a.feed('C',p[1],180)

    def test_m0_240_seconds_accepts_slow_upload_but_duplicates_do_not_renew(self):
        p=packets();a=AudioAssembler(timeout_s=240)
        for n,packet in enumerate(p):result=a.feed('C',packet,n*193/124)
        self.assertEqual(result['chunks'],125)
        self.assertEqual(result['pcm'],bytes(range(256))*250)
        a=AudioAssembler(timeout_s=240);a.feed('C',p[0],0);a.feed('C',p[0],239)
        with self.assertRaises(ValueError):a.feed('C',p[1],240)

    def test_host_separate_and_reply(self):
        a=AudioAssembler();p=packets();a.feed('HOST',p[0],0)
        with self.assertRaises(ValueError):a.feed('C',p[1],1)
        self.assertEqual(reply_packet(7,8,'hello')[:4],b'MR01')
        for text in ('','x'*61,'[v9]','hidden\u200b','bad\x00'):
            with self.assertRaises(ValueError):reply_packet(7,8,text)


if __name__=='__main__':unittest.main()
