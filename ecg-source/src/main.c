#include "stm32f4xx.h"
#include "source_driver.h"
int main(void)
{
    uint32_t last_request=SRC_OFF;
    Src_Init();
    while(1) {
        uint32_t request=g_source_requested_mode;
        /* 只处理一次明确的模式变更，不在故障后按同一请求不断复位/重启。
           本轮只编译；未来G2才可在源板窗口通过调试器设置该对齐32位请求。 */
        if(request!=last_request) {
            last_request=request;Src_ApplyMode(request);
        }
        /* OFF/静态模式没有周期中断，不能WFI等待导致调试器的新请求永远不被消费。
           这里只轮询命令；所有波形时间都由TIM6/DMA决定，与主循环速度无关。 */
        __NOP();
    }
}
void HardFault_Handler(void)
{
    /* 完成外设初始化后异常撤销动态输出；早期异常时DAC尚未由本程序使能。 */
    if(g_source_diag.tag==0x31524353u)Src_Fault(SRC_FAULT_EXCEPTION);
    for(;;) {}
}
void MemManage_Handler(void) {HardFault_Handler();}
void BusFault_Handler(void) {HardFault_Handler();}
void UsageFault_Handler(void) {HardFault_Handler();}
