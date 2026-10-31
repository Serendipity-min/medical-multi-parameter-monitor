/* 复用旧独立温度屏：USART3 PB10输出，主页0/10；显示与CAN一致的未标定物体温度。 */
#include "b_temp_screen.h"
#include "b_temperature.h"
#include "hmi_driver.h"
#include <stdio.h>
#ifndef B_TEMP_SCREEN_HOST
#include "stm32f4xx.h"
#endif

static uint8_t selected;
/* GBK：物体温度 / 测量无效。 */
static const unsigned char object_label[]={0xce,0xef,0xcc,0xe5,0xce,0xc2,0xb6,0xc8,0};
static const unsigned char invalid_label[]={0xb2,0xe2,0xc1,0xbf,0xce,0xde,0xd0,0xa7,0};

int BTempScreen_IsSelected(void){return selected!=0;}

void BTempScreen_Init(void){
#ifndef B_TEMP_SCREEN_HOST
    GPIO_InitTypeDef gpio;USART_InitTypeDef uart;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOB,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3,ENABLE);
    GPIO_StructInit(&gpio);gpio.GPIO_Pin=GPIO_Pin_10;gpio.GPIO_Mode=GPIO_Mode_AF;
    gpio.GPIO_Speed=GPIO_Speed_50MHz;gpio.GPIO_OType=GPIO_OType_PP;gpio.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_Init(GPIOB,&gpio);GPIO_PinAFConfig(GPIOB,GPIO_PinSource10,GPIO_AF_USART3);
    USART_DeInit(USART3);USART_StructInit(&uart);uart.USART_BaudRate=115200;uart.USART_Mode=USART_Mode_Tx;
    USART_Init(USART3,&uart);USART_Cmd(USART3,ENABLE);
#endif
    selected=1;
    SetTextValue(0,10,(uchar *)"--.-");
    /* 没有实现的统计不保留示例数值或示例曲线。 */
    SetTextValue(0,22,(uchar *)"--.-");SetTextValue(0,23,(uchar *)"--.-");SetTextValue(0,24,(uchar *)"--.-");
    SetControlVisiable(0,19,0);
    selected=0;
}

/* 由既有1Hz刷新调用；接收解析、采样和有效期均复用BTemp_Get。 */
void BTempScreen_Refresh(uint32_t now){
    uint16_t centi=0;char text[8];int valid=BTemp_Get(now,&centi);
    if(valid){unsigned tenth=(centi+5u)/10u;(void)sprintf(text,"%u.%u",tenth/10u,tenth%10u);}
    else{(void)sprintf(text,"--.-");}
    selected=1;SetTextValue(0,10,(uchar *)text);
    SetTextValue(0,12,(uchar *)(valid?object_label:invalid_label));selected=0;
}
