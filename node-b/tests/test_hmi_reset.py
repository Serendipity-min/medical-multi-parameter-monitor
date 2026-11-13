"""编译真实切帧/协议代码，验证屏启动报告不再成为 MCU 复位请求。"""
from pathlib import Path
import shutil
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]/'firmware/biov2/实验固件'
HARNESS = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#define _HMI_DRIVER_
#define _USER_UART__
#define __STM32F4xx_H
#define CRC16_ENABLE 0
#define QUEUE_MAX_SIZE 512
typedef uint8_t uint8;
typedef uint16_t uint16;
typedef uint32_t uint32;
volatile uint32 timer_tick_count;
#include "cmd_process.c"
/* 保留厂家原队列的聚合初始化写法，只抑制该旧代码的花括号告警。 */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-braces"
#include "cmd_queue.c"
#pragma GCC diagnostic pop
static unsigned resets, screens;
void HrPage_OnScreenReset(void) { ++resets; }
void HrPage_NotifyScreen(uint16_t scr) { screens = scr; }
void HrPage_OnButton(uint16_t a,uint16_t b,uint8_t c) {(void)a;(void)b;(void)c;}
void HrPage_OnText(uint16_t a,uint16_t b,uint8_t *c) {(void)a;(void)b;(void)c;}
void HrPage_OnRtcTime(uint8_t a,uint8_t b,uint8_t c,uint8_t d,uint8_t e,uint8_t f,uint32_t g)
{(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;}
static void push(const uint8 *bytes,unsigned n)
{ unsigned i;for(i=0;i<n;++i)queue_push(bytes[i]); }
int main(void)
{
    uint8 buf[64] = {0};
    const uint8 report[] = {0xee,0x07,0xff,0xfc,0xff,0xff};
    const uint8 command[] = {0xee,0x07,0x35,0x5a,0x53,0xa5,0xff,0xfc,0xff,0xff};
    const uint8 page[] = {0xee,0xb1,0x01,0x00,0x02,0xff,0xfc,0xff,0xff};
    unsigned n;
    /* 分片接收必须只在完整报告形成后触发一次界面恢复。 */
    queue_reset();push(report,3);assert(queue_find_cmd(buf,sizeof(buf))==0);
    push(report+3,3);n=queue_find_cmd(buf,sizeof(buf));assert(n==6);
    timer_tick_count=123;
    ProcessMessage((PCTRL_MSG)buf,n);assert(resets==1);
    assert(g_hmi_reset_report_count==1 && g_hmi_last_reset_report_ms==1230);
    ProcessMessage(0,6);ProcessMessage((PCTRL_MSG)buf,5);assert(resets==1);
    buf[3]=0;ProcessMessage((PCTRL_MSG)buf,6);assert(resets==1);
    /* 主机发给屏的复位命令不能混同为屏上报，坏帧也不能触发重建。 */
    push(command,sizeof(command));n=queue_find_cmd(buf,sizeof(buf));
    ProcessMessage((PCTRL_MSG)buf,n);assert(resets==1);
    /* 真实非07消息仍走原分发，不因修复而丢失画面通知。 */
    push(page,sizeof(page));n=queue_find_cmd(buf,sizeof(buf));
    ProcessMessage((PCTRL_MSG)buf,n);assert(screens==2 && resets==1);
    push(report,sizeof(report));push(report,sizeof(report));
    n=queue_find_cmd(buf,sizeof(buf));ProcessMessage((PCTRL_MSG)buf,n);
    n=queue_find_cmd(buf,sizeof(buf));ProcessMessage((PCTRL_MSG)buf,n);
    assert(resets==3);
    assert(g_hmi_reset_report_count==3);
    return 0;
}
'''


class HmiResetTests(unittest.TestCase):
    def test_actual_render_reset_body_preserves_run_limits_and_sampling(self):
        source = (ROOT/'HARDWARE/hr_page.c').read_text('utf-8')
        body = re.search(r'void HrPage_OnScreenReset\(void\)\s*\{.*?\n\}', source, re.S).group(0)
        # 仅把真实函数体接到可观察的显示桩，整文件集成另由 ARM 构建验证。
        code = r'''
#include <assert.h>
#include <stdint.h>
typedef unsigned char uchar;
#include "hr_page.h"
static uint8_t s_run, s_sound=0;
static uint32_t s_now_ms=123456, samples=30000;
static unsigned limits=0x78501e08, page, sound, refreshed;
static const uint8_t STR_RUN[]={1}, STR_PAUSE[]={2}, STR_CAP[]={3};
static const uint8_t *pause_text;
static void SetScreen(unsigned p) { page=p; }
void HrPage_NotifyScreen(uint16_t p) { page=p; }
static void WriteSetupTexts(void) { }
static void SetButtonValue(unsigned p,unsigned c,uchar v) {(void)p;(void)c;sound=v;}
static void TxtGB(unsigned p,unsigned c,const uint8_t *v)
{ if(p==HP_SCR_PAUSE && c==HP_TXT_PAUSE)pause_text=v; }
static void ValueRefresh(uint32_t ms) { assert(ms==s_now_ms);++refreshed; }
''' + body + r'''
int main(void)
{
    unsigned running;
    for(running=0;running<2;++running) {
        s_run=(uint8_t)running;
        HrPage_OnScreenReset();
        assert(s_run==running && limits==0x78501e08 && samples==30000);
        assert(page==HP_SCR_HOME && sound==s_sound);
        assert(pause_text==(running?STR_RUN:STR_PAUSE));
    }
    assert(refreshed==2);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            shutil.copyfile(ROOT/'HARDWARE/hr_page.h', folder/'hr_page.h')
            (folder/'test.c').write_text(code, encoding='utf-8')
            build = subprocess.run(['C:/mingw64/bin/gcc.exe', '-std=c99', '-Wall', '-Wextra', '-Werror',
                                    str(folder/'test.c'), '-o', str(folder/'test.exe')],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(folder/'test.exe')], capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_real_parser_fragmentation_reset_report_and_normal_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            # 复制原源码与原头文件，只隔离 MCU 硬件定义；不重写待测协议实现。
            for area, names in [('SCREEN', ('cmd_process.c', 'cmd_process.h', 'cmd_queue.c',
                                           'cmd_queue.h', 'hmi_driver.h', 'ulitity.h', 'hmi_user_uart.h')),
                                ('HARDWARE', ('hr_page.h',)), ('USER', ('stm32f4xx.h',))]:
                for name in names:
                    shutil.copyfile(ROOT/area/name, folder/name)
            (folder/'test.c').write_text(HARNESS, encoding='utf-8')
            build = subprocess.run(['C:/mingw64/bin/gcc.exe', '-std=c99', '-Wall', '-Wextra', '-Werror',
                                    str(folder/'test.c'), '-o', str(folder/'test.exe')],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(folder/'test.exe')], capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == '__main__':
    unittest.main()
