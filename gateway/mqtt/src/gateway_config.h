#ifndef GATEWAY_CONFIG_H
#define GATEWAY_CONFIG_H
#include <stdint.h>

/* 连接信息由仓库外的二进制配置注入，源码与构建日志不包含真实值。
   sector 7 专门保留给配置；本阶段测试完成后须恢复原始整片 Flash。 */
typedef struct
{
    uint32_t magic;
    uint32_t minimum_epoch;
    char ssid[33];
    char wifi_password[65];
    char host[65];
    char username[33];
    char password[65];
    char client_id[41];
} GatewayConfig;

#define GATEWAY_CONFIG ((const GatewayConfig *)0x080E0000UL)
#define GATEWAY_CONFIG_MAGIC 0x31435747UL
#endif
