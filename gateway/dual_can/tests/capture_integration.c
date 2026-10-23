/* 合成总线输入穿过真实CANopen/网关/Router，再由实际取证编码器输出；不连接设备。 */
#include "b4_bench.h"
#include "b4_capture.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
static B4Bench bench;
static uint32_t tick;
int b4_capture_uart_put(uint8_t byte) { return putchar(byte)!=EOF; }
int b4_bus_transmit(unsigned bus,const MpCanFrame *f) {
    assert(bus==1);
    b4_capture_emit(B4_CAP_TX_QUEUE,bus,f->ident,f->dlc,f->data,tick,0);
    b4_capture_emit(B4_CAP_TX_ACK,bus,f->ident,f->dlc,f->data,tick,2);
    return 1;
}
static void inject(unsigned id,const void *data,unsigned size) {
    MpCanFrame f={0};f.ident=id;f.dlc=size;memcpy(f.data,data,size);
    b4_capture_emit(B4_CAP_RX,1,id,size,f.data,tick,0);
    b4_gateway_receive(&bench.gateway,1,&f,tick);
}
int main(void) {
#ifdef _WIN32
    /* Windows输出同样必须为二进制；该夹具只检验模型/时戳，另有固定带宽压力试验。 */
    _setmode(_fileno(stdout),_O_BINARY);
#endif
    b4_capture_init();uint8_t boot[8]={'B','4','C','4',0,0,0,0};
    b4_capture_emit(B4_CAP_BOOT,1,4,8,boot,0,0);
    uint32_t start[2]={0,0};b4_capture_emit(B4_CAP_START,1,0,8,(const uint8_t *)start,0,0);
    assert(!b4_bench_init(&bench,0));
    for (tick=0;tick<180000;tick++) {
        b4_bench_step(&bench,tick);
        if (!(tick%1000)) {
            uint32_t anchor[2]={B4_BENCH_EPOCH+tick/1000,tick};inject(0x482,anchor,8);
            uint32_t quality[2]={15,1};inject(0x682,quality,8);
            uint16_t vitals[4]={6000,2000,0,0};inject(0x382,vitals,8);
            uint32_t diag[2]={0x08000000,0};
            b4_capture_emit(B4_CAP_DIAG,1,4,8,(const uint8_t *)diag,tick,0);
        }
        if (!(tick%500)) { uint8_t hb=5;inject(0x702,&hb,1); }
        if (!(tick%4)) { int32_t sample[2]={(int32_t)((tick/4)%200)-100,(int32_t)tick};inject(0x182,sample,8); }
        if (!(tick%20)) { int32_t sample[2]={(int32_t)((tick/20)%200)-100,(int32_t)tick};inject(0x282,sample,8); }
        b4_capture_drain(4096);
    }
    b4_bench_step(&bench,tick);assert(bench.diag.stopped && !g_b4_capture.dropped);
    uint32_t stop[2]={180000,g_b4_capture.dropped};
    b4_capture_emit(B4_CAP_STOP,1,0,8,(const uint8_t *)stop,tick,0);b4_capture_drain(4096);
    b4_gateway_close(&bench.gateway);
    return 0;
}
