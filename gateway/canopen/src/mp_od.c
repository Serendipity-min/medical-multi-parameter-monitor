/* 应用 OD 与 PDO 映射冻结；不是另造 CANopen 协议，序列化/状态机仍由 CANopenNode 完成。 */
#include "mp_od.h"
#include <stdlib.h>
#include <string.h>

/* OD 描述和实际数值均来自固定容量池；失败标志由初始化末尾统一检查。 */
static void var(MpOD *o, uint16_t index, unsigned size, uint32_t value)
{
    if (o->nvar >= 16 || o->ncell >= 256 || o->nentry >= 64)
    {
        o->failed = true;
        return;
    }
    unsigned n = o->nvar++, c = o->ncell++;
    o->cells[c] = value;
    o->vars[n] = (OD_obj_var_t){&o->cells[c], ODA_SDO_RW | ODA_MB, size};
    o->entries[o->nentry++] = (OD_entry_t){index, 1, ODT_VAR, &o->vars[n], NULL};
}

static void rec(MpOD *o, uint16_t index, unsigned count, const unsigned *sizes,
                const uint32_t *values, OD_attr_t attr)
{
    /* 新增映射时先检查容量，不能在越界写入之后才报告 OD 过大。 */
    if (count > 240 - o->nrecord || count > 256 - o->ncell || o->nentry >= 64)
    {
        o->failed = true;
        return;
    }
    unsigned start = o->nrecord;
    for (unsigned i = 0; i < count; i++)
    {
        unsigned c = o->ncell++;
        o->cells[c] = values[i];
        o->records[o->nrecord++] = (OD_obj_record_t){&o->cells[c], (uint8_t)i, attr, sizes[i]};
    }
    o->entries[o->nentry++] =
        (OD_entry_t){index, (uint8_t)count, ODT_REC, &o->records[start], NULL};
}

static int compare(const void *a, const void *b)
{
    return ((const OD_entry_t *)a)->index - ((const OD_entry_t *)b)->index;
}

/* 第五路使用冻结的 0x680 基址，避开 SDO；调用者仅传入已配置的 PDO 下标 0～4。 */
uint16_t mp_pdo_id(unsigned node, unsigned pdo)
{
    const uint16_t base[5] = {0x180, 0x280, 0x380, 0x480, 0x680};
    return base[pdo] + node;
}

/* 同一应用对象布局用于生产者和 Gateway 镜像，base 不同但各相对偏移保持一致。 */
static void application(MpOD *o, unsigned base)
{
    unsigned sizes3[] = {1, 4, 4}, sizes5[] = {1, 2, 2, 2, 2};
    uint32_t values3[] = {2, 0, 0}, values5[] = {4, 0, 0, 0, 0};
    OD_attr_t attr = ODA_SDO_R | ODA_TPDO | ODA_RPDO | ODA_MB;
    rec(o, base, 3, sizes3, values3, attr);
    rec(o, base + 0x10, 3, sizes3, values3, attr);
    rec(o, base + 0x11, 3, sizes3, values3, attr);
    rec(o, base + 0x20, 5, sizes5, values5, attr);
    rec(o, base + 0x30, 3, sizes3, values3, attr);
}

/* 先建立标准通信对象与 PDO 映射，再绑定 CANopenNode 配置；node=3 为 Gateway。 */
int mp_od_init(MpOD *o, unsigned node, CO_config_t *cfg)
{
    memset(o, 0, sizeof(*o));
    memset(cfg, 0, sizeof(*cfg));
    var(o, 0x1000, 4, 0);
    var(o, 0x1001, 1, 0);
    var(o, 0x1014, 4, 0x80 + node);
    var(o, 0x1015, 2, 100);
    var(o, 0x1017, 2, 500);
    unsigned s3[] = {1, 4, 4}, s4[] = {1, 4, 4, 1}, s5[] = {1, 4, 4, 4, 4};
    uint32_t h[] = {2, (1U << 16) | 1500, (2U << 16) | 1500};
    rec(o, 0x1016, 3, s3, h, ODA_SDO_RW | ODA_MB);
    uint32_t ident[] = {4, 0, 1, 1, node};
    rec(o, 0x1018, 5, s5, ident, ODA_SDO_R | ODA_MB);
    uint32_t server[] = {2, 0x600 + node, 0x580 + node};
    rec(o, 0x1200, 3, s3, server, ODA_SDO_R | ODA_MB);
    uint32_t client[] = {3, 0x601, 0x581, 1};
    rec(o, 0x1280, 4, s4, client, ODA_SDO_RW | ODA_MB);

    /* A/B 各生产五路 TPDO，Gateway 分别配置十路 RPDO，映射到两个独立镜像区。 */
    unsigned n = node == 3 ? 10 : 5;
    for (unsigned i = 0; i < n; i++)
    {
        unsigned remote = node == 3 ? (i / 5 + 1) : node, pdo = i % 5;
        unsigned comm = node == 3 ? 0x1400 : 0x1800, map = node == 3 ? 0x1600 : 0x1A00,
                 base = node == 3 ? 0x3000 + remote * 0x100 : 0x2100;
        unsigned cs[] = {1, 4, 1, 2, 1, 2, 1};
        uint32_t cv[] = {6, mp_pdo_id(remote, pdo), 255, 0, 0, 0, 0};
        rec(o, comm + i, 7, cs, cv, ODA_SDO_RW | ODA_MB);
        unsigned offsets[] = {0x10, 0x11, 0x20, 0, 0x30};
        unsigned index = base + offsets[pdo];
        unsigned ms[] = {1, 4, 4, 4, 4};
        uint32_t mv[5] = {pdo == 2 ? 4 : 2, 0, 0, 0, 0};
        /* CANopen 映射项：高16位 Index、中8位 Sub-index、低8位数据位宽。 */
        for (unsigned j = 1; j <= mv[0]; j++)
            mv[j] = (index << 16) | (j << 8) | (pdo == 2 ? 16 : 32);
        rec(o, map + i, mv[0] + 1, ms, mv, ODA_SDO_RW | ODA_MB);
    }
    if (node == 3)
    {
        application(o, 0x3100);
        application(o, 0x3200);
    }
    else
        application(o, 0x2100);
    if (o->failed)
        return -1;

    /* 上游 OD_find 按索引查找，建立引用之前先保证字典条目有序。 */
    qsort(o->entries, o->nentry, sizeof(o->entries[0]), compare);
    o->od = (OD_t){o->nentry, o->entries};
    cfg->CNT_NMT = 1;
    cfg->ENTRY_H1017 = OD_find(&o->od, 0x1017);
    cfg->CNT_EM = 1;
    cfg->CNT_ARR_1003 = 8;
    cfg->ENTRY_H1001 = OD_find(&o->od, 0x1001);
    cfg->ENTRY_H1014 = OD_find(&o->od, 0x1014);
    cfg->ENTRY_H1015 = OD_find(&o->od, 0x1015);
    cfg->CNT_SDO_SRV = 1;
    cfg->ENTRY_H1200 = OD_find(&o->od, 0x1200);
    if (node == 3)
    {
        cfg->CNT_HB_CONS = 1;
        cfg->CNT_ARR_1016 = 2;
        cfg->ENTRY_H1016 = OD_find(&o->od, 0x1016);
        cfg->CNT_SDO_CLI = 1;
        cfg->ENTRY_H1280 = OD_find(&o->od, 0x1280);
        cfg->CNT_RPDO = 10;
        cfg->ENTRY_H1400 = OD_find(&o->od, 0x1400);
        cfg->ENTRY_H1600 = OD_find(&o->od, 0x1600);
    }
    else
    {
        cfg->CNT_TPDO = 5;
        cfg->ENTRY_H1800 = OD_find(&o->od, 0x1800);
        cfg->ENTRY_H1A00 = OD_find(&o->od, 0x1A00);
    }
    return 0;
}

/* 不足四字节的对象先零扩展；缺失返回 0，业务有效性仍必须由质量位单独判断。 */
uint32_t mp_od_read(MpOD *o, uint16_t index, uint8_t sub)
{
    OD_IO_t io;
    uint32_t value = 0;
    if (OD_getSub(OD_find(&o->od, index), sub, &io, true) == ODR_OK && io.stream.dataLength <= 4)
        memcpy(&value, io.stream.dataOrig, io.stream.dataLength);
    return value;
}

void mp_od_write(MpOD *o, uint16_t index, uint8_t sub, uint32_t value)
{
    OD_IO_t io;
    /* 本机采集更新直接写原始 OD 存储；SDO 仍受各对象只读属性约束。 */
    if (OD_getSub(OD_find(&o->od, index), sub, &io, true) == ODR_OK && io.stream.dataLength <= 4)
        memcpy(io.stream.dataOrig, &value, io.stream.dataLength);
}
