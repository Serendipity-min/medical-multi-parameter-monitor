"""查询字节与实际大彩驱动比对；仅替换UART发送边界，不打开串口。"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import hmi_read_controls as read


class HMIQuery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.out=Path(cls.temp.name)
        source=Path(__file__).resolve().parents[1]/'firmware/biov2/实验固件/SCREEN'
        for name in ('hmi_driver.c','hmi_driver.h'):shutil.copyfile(source/name,cls.out/name)
        (cls.out/'hmi_user_uart.h').write_text('typedef unsigned char uchar; typedef unsigned char uint8; typedef unsigned short uint16; typedef unsigned long uint32; typedef short int16; typedef long int32; void SendChar(uchar t);\n')
        (cls.out/'main.c').write_text('#include "hmi_driver.h"\n#include <stdio.h>\n#include <stdlib.h>\nvoid SendChar(uchar t){printf("%02x",t);}\nint main(int n,char **v){(void)n;GetControlValue((uint16)strtoul(v[1],0,10),(uint16)strtoul(v[2],0,10));return 0;}\n')
        cls.exe=cls.out/'query.exe'
        p=subprocess.run(['C:/mingw64/bin/gcc.exe','-std=c11','-O2','-ffunction-sections','-fdata-sections',str(cls.out/'hmi_driver.c'),str(cls.out/'main.c'),'-Wl,--gc-sections','-o',str(cls.exe)],capture_output=True)
        if p.returncode:raise AssertionError(p.stderr.decode(errors='replace'))

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_queries_match_real_vendor_encoder(self):
        for screen,control in ((0,10),(0,99),(65535,65535)):
            p=subprocess.run([str(self.exe),str(screen),str(control)],capture_output=True)
            self.assertEqual(p.returncode,0);self.assertEqual(read.request(screen,control).hex(),p.stdout.decode())

    def test_control_reply_retains_id_type_and_text(self):
        rows=read.responses(b'noise\xee\xb1\x11\x00\x00\x00\x1d\x1136.5\xff\xfc\xff\xff')
        self.assertEqual((rows[0]['screen'],rows[0]['control'],rows[0]['type'],rows[0]['text']),(0,29,17,'36.5'))

    def test_partial_or_unrelated_frames_do_not_produce_control_identity(self):
        self.assertEqual(read.responses(b'\xee\xb1\x11\x00\x00'),[])
        self.assertEqual(read.responses(b'\xee\xb1\x01\x00\x00\xff\xfc\xff\xff'),[])


if __name__=='__main__':unittest.main()
