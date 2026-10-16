#ifndef MPM_SOURCE_USB_CONSOLE_H
#define MPM_SOURCE_USB_CONSOLE_H
#include <stdint.h>
/* 串口仅控制源板既有模式，不提供地址读写、Flash命令或任意寄存器入口。 */
void Console_Init(void);
const char *Console_Feed(uint8_t byte);
const char *Console_Status(void);
void Console_TransportError(void);
extern uint32_t g_console_errors;
#endif
