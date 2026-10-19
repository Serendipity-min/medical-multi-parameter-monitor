#ifndef GATEWAY_AT_VERSION_H
#define GATEWAY_AT_VERSION_H
#include <stddef.h>
#include <string.h>
/* AT+GMR可能包含厂商扩展字段，只输出有界数字版本，不转存原始回复。 */
static inline int gateway_at_version(const char *response,char out[32]) {
    const char *value=strstr(response,"AT version:");
    if(!value)return 0;
    value+=11;
    size_t used=0;
    while(used<31 && ((value[used]>='0' && value[used]<='9') || value[used]=='.')) {
        out[used]=value[used];used++;
    }
    if(!used || out[0]=='.' || (value[used]>='0' && value[used]<='9') || value[used]=='.')return 0;
    out[used]=0;return 1;
}
#endif
