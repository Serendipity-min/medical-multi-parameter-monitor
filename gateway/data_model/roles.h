#ifndef MP_ROLES_H
#define MP_ROLES_H
#include "model.h"

/* 编译时选择三板复现或五板迁移，节点3始终是网关。 */
static inline unsigned mp_role_node(MpStream stream) {
    if (stream == MP_PPG || stream == MP_SPO2 || stream == MP_PR) return 1;
#ifdef MP_FIVE_NODE
    if (stream == MP_TEMP) return 4;
    if (stream == MP_NIBP) return 5;
#else
    if (stream == MP_TEMP) return 2;
    if (stream == MP_NIBP) return 1;
#endif
    return 2;
}
static inline char mp_node_letter(unsigned node) {
    return node == 1 ? 'A' : node == 2 ? 'B' : node == 4 ? 'D' : node == 5 ? 'E' : 0;
}
#endif
