#include "stm32f4xx.h"
#include "source_driver.h"
#include "console.h"

static uint8_t uart_init(void)
{
    /* 仅S板USART1 PA9/PA10 AF7，经板载CH340C。保持PA4/PA5的G1驱动不变。
       名义APB2为84MHz；若时钟与冻结配置不符，不猜测串口波特率。 */
    if(SystemCoreClock!=168000000u || ((RCC->CFGR>>13)&7u)!=4u)return 0;
    RCC->AHB1ENR|=1u;RCC->APB2ENR|=1u<<4;
    __DSB();
    GPIOA->MODER=(GPIOA->MODER&~((3u<<18)|(3u<<20)))|(2u<<18)|(2u<<20);
    GPIOA->OTYPER&=~((1u<<9)|(1u<<10));
    GPIOA->PUPDR=(GPIOA->PUPDR&~((3u<<18)|(3u<<20)))|(1u<<20);
    GPIOA->OSPEEDR=(GPIOA->OSPEEDR&~((3u<<18)|(3u<<20)))|(2u<<18)|(2u<<20);
    GPIOA->AFR[1]=(GPIOA->AFR[1]&~((15u<<4)|(15u<<8)))|(7u<<4)|(7u<<8);
    USART1->CR1=0;USART1->CR2=0;USART1->CR3=0;
    USART1->BRR=(uint16_t)((84000000u+57600u)/115200u);
    USART1->CR1=(1u<<13)|(1u<<3)|(1u<<2);
    return 1;
}
static uint8_t transmit(const char *text)
{
    uint32_t count;
    /* 仅按明确请求回一行，不周期刷日志；等待有界，中断始终开启。
       PC按“一问一答”发送，避免回包期间堆叠RX。硬件串口错误会撤销输出。 */
    while(*text) {
        count=0;
        while(!(USART1->SR&(1u<<7)) && count<1000000u)count++;
        if(!(USART1->SR&(1u<<7)))return 0;
        USART1->DR=(uint16_t)(uint8_t)*text++;
    }
    return 1;
}
int main(void)
{
    const char *reply;
    uint32_t flags;
    uint8_t byte;
    Src_Init();Console_Init();
    if(!uart_init()) {
        Src_ApplyMode(SRC_OFF);
        for(;;) {} /* 无可靠串口时保留OFF；不自动进入任何工程波形。 */
    }
    while(1) {
        flags=USART1->SR;
        if(flags&15u) {
            /* F4清串口错误须按SR→DR顺序；被污染字节丢弃，不拼接为命令。 */
            byte=(uint8_t)USART1->DR;(void)byte;
            Console_TransportError();continue;
        }
        if(flags&(1u<<5)) {
            byte=(uint8_t)USART1->DR;reply=Console_Feed(byte);
            if(reply && (!transmit(reply) || !transmit("\r\n")))Console_TransportError();
        }
    }
}
void HardFault_Handler(void)
{
    if(g_source_diag.tag==0x31524353u)Src_Fault(SRC_FAULT_EXCEPTION);
    for(;;) {} /* 保留G1异常处置，禁止自动重启掩盖失败。 */
}
void MemManage_Handler(void) {HardFault_Handler();}
void BusFault_Handler(void) {HardFault_Handler();}
void UsageFault_Handler(void) {HardFault_Handler();}
