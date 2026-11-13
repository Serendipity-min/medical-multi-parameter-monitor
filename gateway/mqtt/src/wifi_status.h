#ifndef GATEWAY_WIFI_STATUS_H
#define GATEWAY_WIFI_STATUS_H
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

static inline char gateway_wifi_join_code(const char *response)
{
    const char *tag=response;
    while ((tag=strstr(tag,"+CWJAP:"))!=NULL) {
        const char *code=tag+7;
        if ((tag==response || tag[-1]=='\n') && code[0]>='1' && code[0]<='4' &&
            (code[1]=='\r' || code[1]=='\n'))return code[0];
        tag=code;
    }
    return '\0';
}

/* 原始查询含SSID/BSSID，仅提取固定范围数字，不复制或输出关联身份。 */
static inline int gateway_sleep_mode(const char *response)
{
    const char *start=strstr(response,"+SLEEP:");
    if(!start)return -1;
    char *end;long value=strtol(start+7,&end,10);
    return end!=start+7 && (*end=='\r' || *end=='\n') && value>=0 && value<=3?(int)value:-1;
}

static inline bool gateway_wifi_signal(const char *response,int *channel,int *rssi)
{
    const char *start=strstr(response,"+CWJAP:");
    const char *end_quote=start?strrchr(start,'"'):NULL;
    if(!end_quote || end_quote[1]!=',')return false;
    char *end;long ch=strtol(end_quote+2,&end,10);
    if(end==end_quote+2 || *end!=',')return false;
    const char *signal=end+1;long dbm=strtol(signal,&end,10);
    if(end==signal || (*end!=',' && *end!='\r' && *end!='\n') || ch<1 || ch>14 || dbm< -127 || dbm>0)return false;
    *channel=(int)ch;*rssi=(int)dbm;return true;
}
#endif
