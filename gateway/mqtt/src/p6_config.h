#ifndef P6_CONFIG_H
#define P6_CONFIG_H
/* P6 默认关闭；启用编译也不绑定引脚，没有已核验 UART 回调时保持 P4 行为。 */
#ifndef GATEWAY_P6_VOICE
#define GATEWAY_P6_VOICE 0
#endif
#define P6_VOICE_TOPIC "mpm/v1/GW-C-001/voice/reply"
#define P6_TEXT_MAX 240U
#define P6_HEADER_SIZE 54U
#endif
