/* 固定串口字节预算下的合成压力与CRC/固定START边界，不访问MCU外设。 */
#include "b4_capture.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
static unsigned allowance;
int b4_capture_uart_put(uint8_t value) {
    if (!allowance) return 0;
    allowance--; return putchar(value)!=EOF;
}
int main(int argc,char **argv) {
#ifdef _WIN32
    /* Host字节流必须保留0x0a，Windows文本模式会擅自插入0x0d破坏CRC证据。 */
    _setmode(_fileno(stdout),_O_BINARY);
#endif
    int overflow=argc>1 && !strcmp(argv[1],"overflow");
    assert(b4_capture_crc((const uint8_t *)"123456789",9)==0x29b1);
    b4_capture_init();
    const char *invalid="info\nXXXXB4START\nB4STARTX\n";
    for (unsigned i=0;invalid[i];i++) assert(!b4_capture_arm_byte((uint8_t)invalid[i]));
    const char *start="B4START\n";unsigned accepted=0;
    for (unsigned i=0;start[i];i++) accepted+=(unsigned)b4_capture_arm_byte((uint8_t)start[i]);
    assert(accepted==1);
    for (unsigned i=0;start[i];i++) assert(!b4_capture_arm_byte((uint8_t)start[i]));
    uint8_t data[8]={0,1,2,3,4,5,6,7};
    if (overflow) {
        for (unsigned i=0;i<300;i++) b4_capture_emit(B4_CAP_RX,1,0x182,8,data,i,0);
        assert(g_b4_capture.dropped==44);allowance=20000;b4_capture_drain(20000);
        b4_capture_emit(B4_CAP_RX,1,0x182,8,data,400,0);b4_capture_drain(20000);
        return 0;
    }
    for (uint32_t ms=0;ms<10000;ms++) {
        if (!(ms%4)) assert(b4_capture_emit(B4_CAP_RX,1,0x182,8,data,ms,0));
        if (!(ms%20)) assert(b4_capture_emit(B4_CAP_RX,1,0x282,8,data,ms,0));
        if (!(ms%500)) assert(b4_capture_emit(B4_CAP_RX,1,0x702,1,data,ms,0));
        if (!(ms%1000)) for (unsigned j=0;j<24;j++)
            assert(b4_capture_emit(B4_CAP_DIAG,1,j,8,data,ms,0));
        /* 230400/8N1=23040字节/秒；按每毫秒23或24字节限制，不能让假UART无限吞吐。 */
        allowance=23+(ms%25==0);b4_capture_drain(64);
    }
    allowance=20000;b4_capture_drain(20000);
    assert(!g_b4_capture.dropped && g_b4_capture.enqueued==g_b4_capture.sent);
    fprintf(stderr,"capture pressure PASS: records=%lu high_water=%lu drop=0\n",
            (unsigned long)g_b4_capture.sent,(unsigned long)g_b4_capture.high_water);
    return 0;
}
