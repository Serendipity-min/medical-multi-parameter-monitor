#ifndef MP_H3_PERSISTENT_CONFIG_H
#define MP_H3_PERSISTENT_CONFIG_H
#include "gateway_config.h"
#include <stddef.h>
#include <string.h>

/* 仅用于待审台架候选：独立sector3，校验不等于加密或签名；运行固件没有Flash写入口。 */
#define H3_CONFIG_ADDRESS 0x0800C000UL
#define H3_CONFIG_RECORD_MAGIC 0x32433348UL
#define H3_CONFIG_COMMITTED 0x54494D43UL
typedef struct {
    uint32_t magic;
    uint16_t version,header_bytes;
    uint32_t payload_bytes,generation,crc32,committed;
    GatewayConfig payload;
} H3ConfigRecord;
_Static_assert(offsetof(H3ConfigRecord,payload)==24 && sizeof(H3ConfigRecord)==336,"persistent record layout");

static inline uint32_t h3_config_crc(const H3ConfigRecord *record) {
    const unsigned char *bytes=(const unsigned char *)record;
    uint32_t crc=0xFFFFFFFFu;
    /* CRC覆盖布局/代次和payload，跳过CRC自身及最后编程的提交标记。 */
    for(size_t at=0;at<sizeof(*record);at++) {
        if(at>=16 && at<24)continue;
        crc^=bytes[at];
        for(unsigned bit=0;bit<8;bit++)crc=(crc>>1)^((0u-(crc&1u))&0xEDB88320u);
    }
    return ~crc;
}

static inline int h3_config_record_valid(const H3ConfigRecord *record) {
    if(record->magic!=H3_CONFIG_RECORD_MAGIC || record->version!=1 || record->header_bytes!=24 ||
       record->payload_bytes!=sizeof(GatewayConfig) || !record->generation ||
       record->committed!=H3_CONFIG_COMMITTED || record->crc32!=h3_config_crc(record))return 0;
    const GatewayConfig *p=&record->payload;
    /* 固定数组必须有界终止，必填身份不能为空；不在错误分支打印内容。 */
    if(p->magic!=GATEWAY_CONFIG_MAGIC || p->minimum_epoch<1700000000u ||
       !p->ssid[0] || !p->host[0] || !p->username[0] || !p->password[0] || !p->client_id[0])return 0;
    const char *fields[]={p->ssid,p->wifi_password,p->host,p->username,p->password,p->client_id};
    const size_t sizes[]={33,65,65,33,65,41};
    for(unsigned i=0;i<6;i++) {
        if(!memchr(fields[i],0,sizes[i]))return 0;
        /* AT双引号命令无法安全接受引号/反斜杠/控制字符，保持provision字段约束。 */
        for(size_t j=0;fields[i][j];j++)
            if((unsigned char)fields[i][j]<32 || fields[i][j]=='"' || fields[i][j]=='\\')return 0;
    }
    return 1;
}
#endif
