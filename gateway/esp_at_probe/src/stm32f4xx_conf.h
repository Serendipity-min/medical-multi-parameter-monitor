#ifndef AI_SERIAL_CONSOLE_STM32F4XX_CONF_H
#define AI_SERIAL_CONSOLE_STM32F4XX_CONF_H

/*
 * 标准外设库通过此宏提供参数检查钩子。本最小固件不启用会引入死循环的断言处理；
 * 所有外设参数均为编译期常量，运行时输入不会直接传递到标准外设库。
 */
#define assert_param(expression) ((void)(expression))

#endif
