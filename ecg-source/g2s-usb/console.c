#include "console.h"
#include "source_driver.h"
#include <stdio.h>
#include <string.h>
#ifndef SRC_HOST_TEST
#include "stm32f4xx.h"
#endif

static char input[24],reply[512];
static uint32_t used,discard;
uint32_t g_console_errors;

void Console_Init(void)
{
    used=0;discard=0;g_console_errors=0;
}
void Console_TransportError(void)
{
    /* 无法信任完整命令时撤销动态输出；故障证据独立累计，不改G1的错误位定义。
       不自动重新启动，也不把残留的半条命令接成合法新命令。 */
    g_console_errors++;used=0;discard=1;
    g_source_requested_mode=SRC_OFF;Src_ApplyMode(SRC_OFF);
}
const char *Console_Status(void)
{
    SrcDiagnostic d;
    int length;
#ifndef SRC_HOST_TEST
    uint32_t irq=__get_PRIMASK();__disable_irq();
#endif
    /* DMA完成中断会修改统计。只在复制72字节期间屏蔽中断，格式化及串口发送
       全部在临界区之外；这不会暂停硬件TIM6/DMA，也不声称已独立测得波形。 */
    d=g_source_diag;
#ifndef SRC_HOST_TEST
    __set_PRIMASK(irq);
#endif
    length=snprintf(reply,sizeof(reply),
      "{\"ok\":true,\"fw\":\"ecg-source-usb-1\",\"mode\":%lu,\"state\":%lu,"
      "\"faults\":%lu,\"console_errors\":%lu,\"core_hz\":%lu,\"timer_hz\":%lu,"
      "\"psc\":%lu,\"arr\":%lu,\"table_length\":%lu,\"completed_tables\":%lu,"
      "\"completed_dma_samples\":%lu,\"last_dma_flags\":%lu,\"last_dac_flags\":%lu}",
      (unsigned long)d.mode,(unsigned long)d.state,(unsigned long)d.faults,
      (unsigned long)g_console_errors,(unsigned long)d.core_hz,
      (unsigned long)d.timer_hz,(unsigned long)d.psc,(unsigned long)d.arr,
      (unsigned long)d.table_length,(unsigned long)d.completed_tables,
      (unsigned long)d.completed_dma_samples,(unsigned long)d.last_dma_flags,
      (unsigned long)d.last_dac_flags);
    if(length<0 || (uint32_t)length>=sizeof(reply)) {
        Console_TransportError();
        return "{\"ok\":false,\"error\":\"reply_overflow_outputs_off\"}";
    }
    return reply;
}
const char *Console_Feed(uint8_t byte)
{
    uint32_t mode=SRC_OFF;
    if(byte=='\r')return 0;
    if(byte!='\n') {
        if(discard)return 0;
        if(byte<32 || byte>126 || used>=sizeof(input)-1) {
            Console_TransportError();return 0;
        }
        input[used++]=(char)byte;return 0;
    }
    if(discard) {
        discard=0;used=0;
        return "{\"ok\":false,\"error\":\"bad_frame_outputs_off\"}";
    }
    input[used]=0;used=0;
    if(!strcmp(input,"status") || !strcmp(input,"info"))return Console_Status();
    if(!strcmp(input,"off"))mode=SRC_OFF;
    else if(!strcmp(input,"bias"))mode=SRC_BIAS;
    else if(!strcmp(input,"sine"))mode=SRC_SINE_1HZ;
    else if(!strcmp(input,"ecg60"))mode=SRC_ECG_60;
    else if(!strcmp(input,"ecg90"))mode=SRC_ECG_90;
    else return "{\"ok\":false,\"error\":\"unknown_command\"}";
    /* 只映射G1已测试的五个模式；驱动故障锁存仍由原Src_ApplyMode决定。
       错误不恢复为PASS，OFF也不清除既有flags和计数。 */
    g_source_requested_mode=mode;
    if(!Src_ApplyMode(mode))return "{\"ok\":false,\"error\":\"source_fault_latched\"}";
    return Console_Status();
}
