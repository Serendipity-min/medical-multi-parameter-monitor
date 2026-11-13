"""真实GY641解析器→温度显示模块→厂商HMI编码；隔离GPIO/UART，不连接设备。"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class TempScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.out=Path(cls.temp.name)
        root=Path(__file__).resolve().parents[2];screen=root/'node-b/firmware/biov2/实验固件/SCREEN';temp=root/'node-b/temperature'
        for name in ('hmi_driver.c','hmi_driver.h'):shutil.copyfile(screen/name,cls.out/name)
        (cls.out/'hmi_user_uart.h').write_text('typedef unsigned char uchar;typedef unsigned char uint8;typedef unsigned short uint16;typedef unsigned long uint32;typedef short int16;typedef long int32;void SendChar(uchar t);\n')
        (cls.out/'main.c').write_text(r'''
#include "hmi_driver.h"
#include "b_temp_screen.h"
#include "gy641.h"
#include <assert.h>
#include <stdio.h>
static Gy641 sensor;
void SendChar(uchar value){assert(BTempScreen_IsSelected());printf("%02x",value);}
int BTemp_Get(uint32_t now,uint16_t *value){return gy641_object(&sensor,now,value);}
static void feed(unsigned object,unsigned body){
    unsigned char frame[12]={0xa4,3,7,7,100,0,0,9,196,0,0,0};
    frame[5]=object>>8;frame[6]=object;frame[9]=body>>8;frame[10]=body;
    for(unsigned i=0;i<11;i++)frame[11]+=frame[i];
    for(unsigned i=0;i<12;i++)gy641_feed(&sensor,frame[i],900);
}
int main(void){
    gy641_init(&sensor);BTempScreen_Init();assert(!BTempScreen_IsSelected());puts("");
    feed(2476,3650);BTempScreen_Refresh(1000);assert(!BTempScreen_IsSelected());puts("");
    BTempScreen_Refresh(3401);assert(!BTempScreen_IsSelected());puts("");
    feed(10000,3650);BTempScreen_Refresh(1000);puts("");
    feed(10001,3650);BTempScreen_Refresh(1000);puts("");
    return 0;
}
''')
        exe=cls.out/'screen.exe'
        args=['C:/mingw64/bin/gcc.exe','-std=c11','-O2','-ffunction-sections','-fdata-sections','-DB_TEMP_SCREEN_HOST',
              '-I'+str(cls.out),'-I'+str(temp),str(temp/'b_temp_screen.c'),str(temp/'gy641.c'),str(cls.out/'hmi_driver.c'),str(cls.out/'main.c'),'-Wl,--gc-sections','-o',str(exe)]
        result=subprocess.run(args,capture_output=True)
        if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))
        result=subprocess.run([str(exe)],capture_output=True)
        if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))
        cls.frames=[bytes.fromhex(x) for x in result.stdout.decode().splitlines()]

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def text(self,index,control):
        prefix=b'\xee\xb1\x10\x00\x00'+control.to_bytes(2,'big')
        return [x[len(prefix):].rstrip(b'\0') for x in self.frames[index].split(b'\xff\xfc\xff\xff') if x.startswith(prefix)]

    def test_actual_object_value_rounding_not_body_or_default_36_5(self):
        self.assertEqual(self.text(1,10),[b'24.8']);self.assertNotIn(b'36.5',self.frames[1])
        self.assertEqual(self.text(1,12),['物体温度'.encode('gbk')])

    def test_missing_stale_and_invalid_values_clear_existing_number(self):
        self.assertEqual(self.text(0,10),[b'--.-']);self.assertEqual(self.text(2,10),[b'--.-'])
        self.assertEqual(self.text(4,10),[b'--.-']);self.assertEqual(self.text(2,12),['测量无效'.encode('gbk')])

    def test_upper_bound_and_demo_statistics(self):
        self.assertEqual(self.text(3,10),[b'100.0'])
        for control in (22,23,24):self.assertEqual(self.text(0,control),[b'--.-'])


if __name__=='__main__':unittest.main()
