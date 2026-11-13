#ifndef GATEWAY_CONFIG_H
#define GATEWAY_CONFIG_H
#include <stdint.h>

/* 连接信息由仓库外的二进制配置注入，源码与构建日志不包含真实值。
   实际地址位于sector11；H3同时保护sector7。恢复只限经核验的应用/配置范围，不承诺整片恢复。 */
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

#if defined(MP_H3_PERSISTENT_CONFIG) && defined(MP_H3_VOLATILE_CONFIG)
#error "persistent and volatile configuration are mutually exclusive"
#endif
#ifdef MP_H3_PERSISTENT_CONFIG
/* 仅显式候选启用：sector3记录头24B，实际payload仍为原312B。 */
#define GATEWAY_CONFIG ((const GatewayConfig *)0x0800C018UL)
#elif defined(MP_H3_VOLATILE_CONFIG)
/* H3隔离会话由ROM下载器核验后只注入RAM；链接器保留顶部512B，启动清零不覆盖。
   不写sector7/11，不构成正式持久配置；断电后必须重新注入，缺配置仍拒绝联网。 */
#define GATEWAY_CONFIG ((const GatewayConfig *)0x2001FE00UL)
#else
#define GATEWAY_CONFIG ((const GatewayConfig *)0x080E0000UL)
#endif
#define GATEWAY_CONFIG_MAGIC 0x31435747UL
#endif
