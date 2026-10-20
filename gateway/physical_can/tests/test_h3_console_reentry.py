"""编译真实console函数和真实诊断入口，复现TXE等待期间的日志重入。"""
from pathlib import Path
import re
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[3]


def function(source,name):
    start=re.search(r'^(?:static )?(?:void|int) '+name+r'\([^\n]*\)\s*\{',source,re.M)
    assert start
    # 这些短函数没有字符串花括号；按完整函数提取，测试始终执行生产函数体。
    depth=0
    for at in range(source.index('{',start.start()),len(source)):
        if source[at]=='{':depth+=1
        if source[at]=='}':
            depth-=1
            if not depth:return source[start.start():at+1]
    raise AssertionError('function incomplete')


@pytest.mark.parametrize('bug_reference',[False,True])
def test_diagnostic_cannot_split_mqtt_error_line(tmp_path,bug_reference):
    platform=ROOT/'gateway/mqtt/src/platform.c'
    text=platform.read_text(encoding='utf-8')
    busy=function(text,'platform_console_busy')
    if bug_reference:busy='int platform_console_busy(void) {return 0;}'
    main_source=(ROOT/'gateway/physical_can/src/main.c').read_text(encoding='utf-8')
    declarations=main_source[:main_source.index('/* UART输出')]
    generated=tmp_path/'console.c'
    generated.write_text('''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
static unsigned console_depth;
static char output[8192];
static unsigned used;
typedef struct {unsigned SR,DR;} Uart;
static Uart uart;
static Uart *console_uart(void) {
    if(uart.DR) {assert(used<sizeof(output)-1);output[used++]=(char)uart.DR;uart.DR=0;uart.SR=0;}
    return &uart;
}
#define USART1 console_uart()
#define USART_SR_TXE 1u
void platform_poll(void);
''' + busy + '\n' + function(text,'console') + '\n' + declarations + function(main_source,'diagnostics') + '''
volatile uint32_t g_uptime_ms;
PhysicalRxMetrics physical_rx_metrics;
uint32_t physical_rx_overflow,physical_bad_frame;
uint32_t mp_bus_frames(void) {return 0;}
uint32_t mp_bus_dropped(void) {return 0;}
int mp_stack_online(MpStack *s,unsigned n) {(void)s;(void)n;return 0;}
void physical_rx_update_metrics(void) {}
uint32_t platform_uart_errors_total(void) {return 0;}
void platform_io_snapshot(EspIoMetrics *out) {memset(out,0,sizeof(*out));}
void platform_poll(void) {
    static int polling;
    if(!polling) {polling=1;diagnostics();polling=0;}
    uart.SR=USART_SR_TXE;
}
int main(void) {
    const char *error="GW MQTT_ERROR stage=6 status=0 elapsed=5000 ack=0 connected=1\\r\\n";
    g_uptime_ms=5000;
    console(error);console_uart();platform_poll();console_uart();
    if(strncmp(output,error,strlen(error)))return 3;
    assert(strstr(output,"GW DIAG_BEGIN seq=1 lines=4"));
    assert(diagnostic_seq==1);
    puts("PASS actual_console_preserves_error_and_defers_real_diagnostics");return 0;
}
''',encoding='utf-8')
    binary=tmp_path/'console.exe'
    includes=['gateway/physical_can/src','gateway/mqtt/src','gateway/canopen/src','gateway/third_party/CANopenNode']
    command=['gcc','-std=c11','-O1','-DMP_CAN_RX_IRQ','-DCO_MULTIPLE_OD','-ffunction-sections','-fdata-sections',
             *['-I'+str(ROOT/p) for p in includes],str(generated),'-Wl,--gc-sections','-o',str(binary)]
    built=subprocess.run(command,capture_output=True,text=True)
    assert built.returncode==0,built.stderr
    run=subprocess.run([str(binary)],capture_output=True,text=True)
    assert run.returncode==(3 if bug_reference else 0),run.stderr
