#ifndef NODE_TEST_STM32_H
#define NODE_TEST_STM32_H
#include <stdint.h>
#define CAN1 ((void *)1)
/* Host 只模拟 IRQ 状态，绝不访问外设地址。 */
extern uint32_t host_primask;
#define __get_PRIMASK() host_primask
#define __disable_irq() (host_primask = 1)
#define __set_PRIMASK(x) (host_primask = (x))
#define __enable_irq() (host_primask = 0)
#define __nop() ((void)0)
#define __DMB() ((void)0)
#endif
