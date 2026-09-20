#ifndef MP_OD_H
#define MP_OD_H
#define OD_DEFINITION
#include "CANopen.h"

/* 静态有界 OD 元数据；最终采集节点可由此冻结映射导出自己的 OD。 */
typedef struct
{
    OD_t od;
    OD_entry_t entries[64];
    OD_obj_record_t records[240];
    OD_obj_var_t vars[16];
    uint32_t cells[256];
    unsigned nentry, nrecord, nvar, ncell;
    bool failed;
} MpOD;

int mp_od_init(MpOD *od, unsigned node_id, CO_config_t *config);
uint32_t mp_od_read(MpOD *od, uint16_t index, uint8_t sub);
void mp_od_write(MpOD *od, uint16_t index, uint8_t sub, uint32_t value);
uint16_t mp_pdo_id(unsigned node, unsigned pdo);
#endif
