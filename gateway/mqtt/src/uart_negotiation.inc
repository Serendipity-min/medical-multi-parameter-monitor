#include "preflight_baud.h"

typedef struct {uint32_t baud,data,stop,parity,flow;} PreUart;

/* 只接受行首的独立回复，忽略命令回显和其它字段。 */
static const char *pre_reply_field(const char *tag) {
    const char *start=at_response(),*found=start;
    size_t size=strlen(tag);
    while((found=strstr(found,tag))!=NULL){
        if(found==start || found[-1]=='\n')return found+size;
        found+=size;
    }
    return NULL;
}

static int pre_number(const char **cursor,uint32_t max,uint32_t *value) {
    const char *p=*cursor;
    uint32_t result=0;
    unsigned digits=0;
    while(*p>='0' && *p<='9'){
        if(++digits>7)return 0;
        result=result*10u+(uint32_t)(*p++-'0');
        if(result>max)return 0;
    }
    if(!digits)return 0;
    *cursor=p;
    *value=result;
    return 1;
}

static int pre_eol(const char *p) {return *p=='\n' || (*p=='\r' && p[1]=='\n');}

static int pre_uart_parse(PreUart *out) {
    const char *p=pre_reply_field("+UART_CUR:");
    PreUart v;
    if(!p || !pre_number(&p,4500000u,&v.baud) || v.baud<80u || *p++!=',' ||
       !pre_number(&p,8,&v.data) || v.data<5u || *p++!=',' ||
       !pre_number(&p,3,&v.stop) || !v.stop || *p++!=',' ||
       !pre_number(&p,2,&v.parity) || *p++!=',' ||
       !pre_number(&p,3,&v.flow) || !pre_eol(p))return 0;
    *out=v;
    return 1;
}

static int pre_uart_matches(const PreUart *uart,uint32_t target) {
    return uart->data==8 && uart->stop==1 && !uart->parity && uart->flow<=1 &&
           preflight_baud_matches(target,uart->baud);
}

static int pre_uart_set(uint32_t ms,uint32_t baud,uint32_t flow,char *buffer,size_t size) {
    (void)snprintf(buffer,size,"AT+UART_CUR=%lu,8,1,0,%lu",(unsigned long)baud,(unsigned long)flow);
    return at_command(buffer,ms);
}
