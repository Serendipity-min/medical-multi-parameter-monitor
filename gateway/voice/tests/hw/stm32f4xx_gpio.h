/* Host仅替换引脚边界；不代替实际USART2/CAN中断的ARM构建与真机证据。 */
#ifndef VOICE_FAKE_GPIO_H
#define VOICE_FAKE_GPIO_H
#include <stdint.h>
typedef struct {unsigned GPIO_Pin,GPIO_Mode,GPIO_PuPd;} GPIO_InitTypeDef;
#define GPIOA ((void *)1)
#define GPIO_Pin_0 1
#define GPIO_Mode_IN 0
#define GPIO_PuPd_DOWN 2
void GPIO_StructInit(GPIO_InitTypeDef *);
void GPIO_Init(void *,GPIO_InitTypeDef *);
int GPIO_ReadInputDataBit(void *,unsigned);
#endif
