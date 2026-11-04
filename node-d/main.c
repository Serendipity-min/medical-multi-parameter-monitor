/* D 不链接 ECG/DSP；采样、屏和 PDO 共用 BTemp_Get 的读数与有效期。 */
#include "stm32f4xx.h"
#include "timer.h"
#include "b_temperature.h"
#include "b_temp_screen.h"
#include "b_canopen_app.h"

void SendChar(unsigned char byte) {
    while(USART_GetFlagStatus(USART3,USART_FLAG_TXE)==RESET) {}
    USART_SendData(USART3,byte);
}
int main(void) {
    uint32_t last=0;
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    TimeBase_Init();BTemp_Init();BTempScreen_Init();CanOpen_Init();
    for(;;) {
        uint32_t now=TimeBase_GetMs();CanOpen_Task(now);
        if((uint32_t)(now-last)>=1000u){last=now;BTempScreen_Refresh(now);}
    }
}
