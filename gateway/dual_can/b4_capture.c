/* 主循环生产完整包、UART中断消费字节；ISR不格式化、不分配堆内存。 */
#include "b4_capture.h"
#include <string.h>
#define CAP_SLOTS 256u
static uint8_t packets[CAP_SLOTS][B4_CAPTURE_BYTES];
static volatile unsigned head, tail;
static unsigned offset;
static unsigned arm_length, arm_used, arm_discard;
static uint8_t arm_line[7];
volatile B4CaptureDiag g_b4_capture;
/* Host维持可控消费者；ARM使用真实内存屏障发布SPSC所有权，不能用共享count加减。 */
static void publish_barrier(void) {
#if defined(__arm__) || defined(__thumb__)
    __asm volatile ("dmb" ::: "memory");
#else
    __asm volatile ("" ::: "memory");
#endif
}
__attribute__((weak)) void b4_capture_uart_wake(void) { }
int b4_capture_pending(void) { return head!=tail; }
static void u16(uint8_t *p, uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
static void u32(uint8_t *p, uint32_t v) {
    for (unsigned i=0;i<4;i++) p[i]=(uint8_t)(v>>(8*i));
}
uint16_t b4_capture_crc(const uint8_t *data, unsigned n) {
    uint16_t crc=0xffffu;
    for (unsigned i=0;i<n;i++) {
        crc ^= (uint16_t)data[i]<<8;
        for (unsigned bit=0;bit<8;bit++) crc=(uint16_t)((crc<<1)^((crc&0x8000u)?0x1021u:0));
    }
    return crc;
}
void b4_capture_init(void) {
    head=tail=offset=0; arm_length=arm_used=arm_discard=0;
    memset((void *)&g_b4_capture,0,sizeof(g_b4_capture));
}
int b4_capture_arm_byte(uint8_t byte) {
    if (arm_used) return 0;
    if (byte=='\n') {
        int accepted=!arm_discard && arm_length==7 && !memcmp(arm_line,"B4START",7);
        arm_length=arm_discard=0;
        if (accepted) arm_used=1;
        return accepted;
    }
    /* 超长行整体作废，不能通过后缀或命令碎片误触发台架。 */
    if (arm_length==sizeof(arm_line)) { arm_discard=1; return 0; }
    arm_line[arm_length++]=byte; return 0;
}
int b4_capture_emit(unsigned kind,unsigned bus,unsigned id,unsigned dlc,
                    const uint8_t *data,uint32_t tick,uint32_t flags) {
    uint32_t seq=++g_b4_capture.sequence;
    if (kind<1 || kind>10 || bus>1 || dlc>8 || id>0xffffu) return 0;
    /* 满队列也消耗序号并累计丢弃，接收端不能把缺记录当完整原始总线。 */
    if ((unsigned)(head-tail)==CAP_SLOTS) { g_b4_capture.dropped++; return 0; }
    uint8_t *p=packets[head%CAP_SLOTS]; memset(p,0,B4_CAPTURE_BYTES);
    p[0]=0xb4; p[1]=0xc4; p[2]=1; p[3]=(uint8_t)kind;
    p[4]=(uint8_t)bus; p[5]=(uint8_t)dlc; u16(p+6,(uint16_t)id);
    u32(p+8,tick); u32(p+12,seq);
    if (data && dlc) memcpy(p+16,data,dlc);
    u32(p+24,flags); u16(p+30,b4_capture_crc(p,30));
    publish_barrier(); head++; g_b4_capture.enqueued++;
    unsigned count=head-tail;
    if (count>g_b4_capture.high_water) g_b4_capture.high_water=count;
    b4_capture_uart_wake();
    return 1;
}
void b4_capture_drain(unsigned budget) {
    /* UART每字节仅探测一次TXE；忙则立刻把CPU让回CAN/协议处理。 */
    while (head!=tail && budget--) {
        publish_barrier();
        if (!b4_capture_uart_put(packets[tail%CAP_SLOTS][offset])) return;
        offset++; g_b4_capture.bytes++;
        if (offset==B4_CAPTURE_BYTES) {
            offset=0; publish_barrier(); tail++; g_b4_capture.sent++;
        }
    }
}
