#ifndef MP_HOST_GPIO_H
#define MP_HOST_GPIO_H
#include "stm32f4xx.h"
/* Host无GPIO副作用；真实引脚配置仍由ARM构建与现场复测验证。 */
typedef struct {unsigned GPIO_Pin,GPIO_Mode,GPIO_OType,GPIO_Speed,GPIO_PuPd;} GPIO_InitTypeDef;
#define GPIOA 0
#define GPIO_Pin_11 (1u<<11)
#define GPIO_Pin_12 (1u<<12)
#define GPIO_PinSource11 11
#define GPIO_PinSource12 12
#define GPIO_Mode_AF 2
#define GPIO_OType_PP 0
#define GPIO_Speed_50MHz 2
#define GPIO_PuPd_UP 1
#define GPIO_AF_CAN1 9
static inline void GPIO_StructInit(GPIO_InitTypeDef *g) {(void)g;}
static inline void GPIO_PinAFConfig(int p,int pin,int af) {(void)p;(void)pin;(void)af;}
static inline void GPIO_Init(int p,GPIO_InitTypeDef *g) {(void)p;(void)g;}
#endif
