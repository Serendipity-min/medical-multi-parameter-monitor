#include "main.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include "pf6_diag.h"
#include <stdio.h>

extern volatile uint32_t g_uptime_ms;
enum { ESP_EMPTY=-2, ESP_ERROR=-1 };

static int esp_read(void){
    uint32_t sr=USART3->SR;
    uint32_t bad=USART_SR_ORE|USART_SR_NE|USART_SR_FE;
    if(!(sr&(USART_SR_RXNE|bad)))return ESP_EMPTY;
    unsigned byte=USART3->DR&0xffu;
    return (sr&bad)?ESP_ERROR:(int)byte;
}

static void platform_poll(void){(void)esp_read();}
#include "../../mqtt/src/esp_pf6_reset.inc"

static void setup_uart(void){
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA|RCC_AHB1Periph_GPIOB|RCC_AHB1Periph_GPIOC,ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3,ENABLE);
    GPIO_InitTypeDef gpio={0};
    gpio.GPIO_Pin=GPIO_Pin_0;gpio.GPIO_Mode=GPIO_Mode_IN;gpio.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_Init(GPIOC,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_9|GPIO_Pin_10;gpio.GPIO_Mode=GPIO_Mode_AF;gpio.GPIO_Speed=GPIO_Speed_50MHz;
    GPIO_PinAFConfig(GPIOA,GPIO_PinSource9,GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA,GPIO_PinSource10,GPIO_AF_USART1);
    GPIO_Init(GPIOA,&gpio);
    gpio.GPIO_Pin=GPIO_Pin_10|GPIO_Pin_11;
    GPIO_PinAFConfig(GPIOB,GPIO_PinSource10,GPIO_AF_USART3);
    GPIO_PinAFConfig(GPIOB,GPIO_PinSource11,GPIO_AF_USART3);
    GPIO_Init(GPIOB,&gpio);
    USART_InitTypeDef uart;
    USART_StructInit(&uart);
    uart.USART_BaudRate=115200u;
    USART_Init(USART1,&uart);USART_Init(USART3,&uart);
    USART_Cmd(USART1,ENABLE);USART_Cmd(USART3,ENABLE);
}

static void console_write(const char *line){
    while(*line){
        while(!(USART1->SR&USART_SR_TXE)){}
        USART1->DR=(uint8_t)*line++;
    }
}

static bool wait_line(const char *line,unsigned size,uint32_t from,uint32_t timeout){
    Pf6Reply reply={0};
    while((uint32_t)(g_uptime_ms-from)<timeout){
        int byte=esp_read();
        if(byte!=ESP_EMPTY && pf6_reply_byte(&reply,byte,line,size))return true;
    }
    return false;
}

static bool confirm_at(void){
    static const char at[]="AT\r\n";
    uint32_t start=g_uptime_ms;
    for(unsigned i=0;i<sizeof at-1;i++){
        while(!(USART3->SR&USART_SR_TXE)){
            if((uint32_t)(g_uptime_ms-start)>=100u)return false;
            (void)esp_read();
        }
        USART3->DR=(uint8_t)at[i];
    }
    return wait_line("OK\r\n",4u,start,500u);
}

static void run_once(void){
    unsigned pc0=GPIO_ReadInputDataBit(GPIOC,GPIO_Pin_0);
    int pulse=platform_esp_hard_reset();
    uint32_t released=g_uptime_ms;
    bool ready=pulse>0 && wait_line("ready\r\n",7u,released,3000u);
    uint32_t ready_ms=ready?g_uptime_ms-released:0u;
    if(ready)(void)esp_read();
    bool at=ready && confirm_at();
    char line[118];
    (void)snprintf(line,sizeof line,"PF6 DIAG pc0_pre=%u pc0_end=%u pulse=%d ready=%u ready_ms=%lu at=%u\r\n",
        pc0,(unsigned)GPIO_ReadInputDataBit(GPIOC,GPIO_Pin_0),pulse,
        (unsigned)ready,(unsigned long)ready_ms,(unsigned)at);
    console_write(line);
}

int main(void){
    SCB->VTOR=0x08000000u;
    __DSB();__ISB();
    setup_uart();
    if(SysTick_Config(SystemCoreClock/1000u))for(;;){}
    console_write("PF6 DIAG READY C_ONLY SEND PF6 ONCE\r\n");
    Pf6Command command={.valid=true};
    for(;;){
        (void)esp_read();
        uint32_t sr=USART1->SR;
        if(sr&(USART_SR_RXNE|USART_SR_ORE|USART_SR_FE|USART_SR_NE)){
            unsigned byte=USART1->DR&0xffu;
            if(sr&(USART_SR_ORE|USART_SR_FE|USART_SR_NE))command.valid=false;
            else if(pf6_command_byte(&command,(int)byte))run_once();
        }
    }
}
