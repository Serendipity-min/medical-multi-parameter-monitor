/* 只在Host读取离线记录，直接复用候选固件校验函数，不输出配置字段。 */
#include "persistent_config.h"
#include "b5_policy.h"
#include <stdio.h>
#include <stdlib.h>

int b5_network_stopped(void) { return 1; }
int main(int argc, char **argv) {
    H3ConfigRecord record;
    if (argc != 4) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (!file) return 3;
    size_t count = fread(&record, 1, sizeof(record), file);
    int extra = fgetc(file);
    fclose(file);
    if (count != sizeof(record) || extra != EOF) return 4;
    int valid = h3_config_record_valid(&record);
    int identity = valid && b5_identity_allowed(record.payload.client_id, record.payload.username);
    printf("{\"bytes\":%u,\"record_valid\":%d,\"B5_identity\":%d}\n",
           (unsigned)sizeof(record), valid, identity);
    return valid == atoi(argv[2]) && identity == atoi(argv[3]) ? 0 : 1;
}
