/* 独立离线控制台：仅USART1和SysTick；不编译USART3/ESP/AT/TLS/配置读写。 */
#include "bench.h"
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
static char output[4096];
static unsigned head,tail;
volatile uint32_t g_uptime_ms;
void SysTick_Handler(void) {g_uptime_ms++;}
void console(const char *s) {
    while(*s) {
        unsigned next=(head+1u)%sizeof(output);
        if(next==tail) {bench_stats.uart_dropped++;return;}
        output[head]=*s++;head=next;
    }
}
static void platform_init(void) {
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA,ENABLE);RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1,ENABLE);
    GPIO_InitTypeDef gpio;GPIO_StructInit(&gpio);gpio.GPIO_Pin=GPIO_Pin_9|GPIO_Pin_10;
    gpio.GPIO_Mode=GPIO_Mode_AF;gpio.GPIO_OType=GPIO_OType_PP;gpio.GPIO_PuPd=GPIO_PuPd_UP;gpio.GPIO_Speed=GPIO_Speed_50MHz;
    GPIO_PinAFConfig(GPIOA,GPIO_PinSource9,GPIO_AF_USART1);GPIO_PinAFConfig(GPIOA,GPIO_PinSource10,GPIO_AF_USART1);GPIO_Init(GPIOA,&gpio);
    USART_InitTypeDef uart;USART_StructInit(&uart);uart.USART_BaudRate=115200;
    USART_Init(USART1,&uart);USART_Cmd(USART1,ENABLE);
    if(SysTick_Config(SystemCoreClock/1000u)) while(1) {}
}
int main(void) {
    platform_init();bench_init();
    while(1) {
        /* 串口发送无阻塞，一轮最多8字节，避免诊断反过来阻塞CAN接收。 */
        unsigned budget=8;
        while(tail!=head && (USART1->SR&USART_SR_TXE) && budget--) {
            USART1->DR=(uint8_t)output[tail];tail=(tail+1u)%sizeof(output);
        }
        if(USART1->SR&USART_SR_RXNE) bench_command((int)(USART1->DR&255u));
        bench_step();
    }
}
