#ifndef CORE_MQTT_CONFIG_H
#define CORE_MQTT_CONFIG_H
/* 官方 v2.3.1 配置；外层连接/发布总预算仍为 P4 的 5000ms。 */
#define MQTT_SEND_TIMEOUT_MS 5000U
#define MQTT_RECV_POLLING_TIMEOUT_MS 5U
#define MQTT_PINGRESP_TIMEOUT_MS 5000U
#define PACKET_TX_TIMEOUT_MS 30000U
#define PACKET_RX_TIMEOUT_MS 30000U
/* 上游日志默认关闭，避免输出 CONNECT 身份、Topic 或原始载荷。 */
#if defined(MP_B5_EGRESS_FINAL) && defined(__arm__)
/* 表达式文本可由文件/行号重建；保留源位置、全部断言条件及同一停机路径。 */
void __assert_func(const char *,int,const char *,const char *) __attribute__((noreturn));
#undef assert
#define assert(condition) ((condition)?(void)0:__assert_func(__FILE__,__LINE__,__func__,0))
#endif
#endif
