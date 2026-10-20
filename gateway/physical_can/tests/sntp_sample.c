#include <assert.h>
#include <stdio.h>
#include "sntp_sample.h"
int main(void) {
    char server[65];
    assert(sntp_first_server("+CIPSNTPCFG:1,0,\"ntp.example.invalid\"\r\nOK\r\n",server));
    assert(!strcmp(server,"ntp.example.invalid"));
    assert(!sntp_first_server("+CIPSNTPCFG:1,0,\"bad\\server\"",server));
    assert(!sntp_first_server("OK",server));
    unsigned char request[48]={0x23},reply[48]={0x24,2};uint64_t sample=0;
    sntp_put32(request+40,4008988800u);sntp_put32(request+44,1234u);
    memcpy(reply+24,request+40,8);sntp_put32(reply+32,4008988800u);sntp_put32(reply+40,4008988800u);
    sntp_put32(reply+36,0x80000000u);sntp_put32(reply+44,0x80000000u);
    assert(sntp_sample(reply,48,request,100,1790000000u,&sample));assert(sample==1800000000550ULL);
    /* 旧包/错误nonce、未同步服务器、KoD、异常延迟及过期epoch全部不能授时。 */
    reply[24]^=1;assert(!sntp_sample(reply,48,request,100,1790000000u,&sample));reply[24]^=1;
    reply[0]=0xe4;assert(!sntp_sample(reply,48,request,100,1790000000u,&sample));reply[0]=0x24;
    reply[1]=0;assert(!sntp_sample(reply,48,request,100,1790000000u,&sample));reply[1]=2;
    assert(!sntp_sample(reply,48,request,1001,1790000000u,&sample));
    assert(!sntp_sample(reply,47,request,100,1790000000u,&sample));
    assert(!sntp_sample(reply,48,request,100,1900000000u,&sample));
    sntp_put32(reply+32,4008988801u);assert(!sntp_sample(reply,48,request,100,1790000000u,&sample));
    puts("SNTP originate / mode / LI / stratum / RTT / fraction / epoch / boundary PASS");return 0;
}
