/* H3只读配置提交协议直接复用；损坏记录不允许回退到旧sector7/11。 */
#include "persistent_config.h"
#include "b5_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int b5_network_stopped(void){return 0;}
int main(void){
    H3ConfigRecord r={0};r.magic=H3_CONFIG_RECORD_MAGIC;r.version=1;r.header_bytes=24;
    r.payload_bytes=sizeof(GatewayConfig);r.generation=1;r.committed=H3_CONFIG_COMMITTED;
    r.payload.magic=GATEWAY_CONFIG_MAGIC;r.payload.minimum_epoch=1700000000;
    strcpy(r.payload.ssid,"synthetic-b5-wifi");strcpy(r.payload.host,"mqtt.example.invalid");
    strcpy(r.payload.username,B5_USERNAME);strcpy(r.payload.password,"synthetic-b5-only");strcpy(r.payload.client_id,B5_CLIENT_ID);
    r.crc32=h3_config_crc(&r);assert(h3_config_record_valid(&r) && b5_identity_allowed(r.payload.client_id,r.payload.username));
    r.payload.host[0]^=1;assert(!h3_config_record_valid(&r));
    r.payload.host[0]^=1;r.committed=0;assert(!h3_config_record_valid(&r));
    r.committed=H3_CONFIG_COMMITTED;strcpy(r.payload.client_id,"historical-c");r.crc32=h3_config_crc(&r);
    assert(h3_config_record_valid(&r) && !b5_identity_allowed(r.payload.client_id,r.payload.username));
    puts("CONFIG_PASS layout336 CRC commit marker identity old_config_refused");return 0;
}
