/* 普通 Host 回归运行原 CANopenNode + OD + 应用，仅 CAN/UART/屏输入替换为内存边界。 */
#include "stm32f4xx.h"
#include "CANopen.h"
#include "OD.h"
#include "canopen_app.h"
#include "app_bp.h"
#include "uno.h"
#include "node_irq.h"
#include "node_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
volatile uint32_t uwTick;
uint32_t host_primask;
uint8_t g_paused;
volatile uint8_t g_last_pr_ok = 1;
measurement_t g_meas;
static bp_last_t bp;
static bp_state_t bp_state;
static CO_CANmodule_t *module;
static unsigned init_count, hb_count, ppg_count, sdo_count, emcy_count;
static unsigned quality_count;
static uint32_t hb_at, last_ppg_tick;
static uint8_t strict_ppg=1;
static uint8_t hb_state;
static uint8_t wire_mode;
static uint8_t sdo_data[8];
static NodeCanIrq irq_state;
static int wave_available;
static uint32_t wave_tick;
/* 与目标端相同的嵌套保存/恢复语义，测试调用前已经屏蔽的 IRQ。 */
void node_can_lock(void) { node_irq_lock(&irq_state); }
void node_can_unlock(void) { node_irq_unlock(&irq_state); }
bp_last_t bp_last_get(void) { return bp; }
bp_state_t bp_state_get(void) { return bp_state; }
uint32_t spo2_rtc_get_epoch(void) { return 1767225600; }
uint16_t UNO_WaveTakeCAN(int32_t *w,uint32_t *t,uint16_t max) {
    if (!max || !wave_available) return 0;
    wave_available=0; *w=(int32_t)(wave_tick % 1000)*100; *t=wave_tick; return 1;
}
uint16_t UNO_WavePendingCAN(void) { return wave_available; }
void UNO_WaveClearCAN(void) { wave_available=0; }
void CO_CANsetConfigurationMode(void *p) { (void)p; }
void CO_CANsetNormalMode(CO_CANmodule_t *m) { m->CANnormal=true; }
void CO_CANmodule_disable(CO_CANmodule_t *m) { m->CANnormal=false; }
CO_ReturnError_t CO_CANmodule_init(CO_CANmodule_t *m,void *p,CO_CANrx_t rx[],uint16_t nr,CO_CANtx_t tx[],uint16_t nt,uint16_t rate) {
    assert(rate==500); memset(m,0,sizeof(*m)); memset(rx,0,nr*sizeof(*rx)); memset(tx,0,nt*sizeof(*tx));
    m->CANptr=p;m->rxArray=rx;m->rxSize=nr;m->txArray=tx;m->txSize=nt;module=m;init_count++;return CO_ERROR_NO;
}
CO_ReturnError_t CO_CANrxBufferInit(CO_CANmodule_t *m,uint16_t i,uint16_t id,uint16_t mask,bool_t rtr,void *o,void (*fn)(void *,void *)) {
    assert(!rtr && i<m->rxSize);m->rxArray[i]=(CO_CANrx_t){id,mask,o,fn};return CO_ERROR_NO;
}
CO_CANtx_t *CO_CANtxBufferInit(CO_CANmodule_t *m,uint16_t i,uint16_t id,bool_t rtr,uint8_t dlc,bool_t sync) {
    assert(!rtr && i<m->txSize);CO_CANtx_t *t=&m->txArray[i];t->ident=id;t->DLC=dlc;t->syncFlag=sync;return t;
}
CO_ReturnError_t CO_CANsend(CO_CANmodule_t *m,CO_CANtx_t *t) {
    (void)m;
    /* 可选导出真实协议栈发送结果供另一进程的 Gateway RPDO 消费；只是 Host 外设边界。 */
    if(wire_mode) {printf("%u %u %u ",uwTick,t->ident,t->DLC);for(unsigned i=0;i<t->DLC;i++) printf("%02X",t->data[i]);puts("");return CO_ERROR_NO;}
    if(t->ident==0x701 && t->data[0]!=0) { if(hb_count && hb_state==t->data[0]) assert(uwTick-hb_at>=499 && uwTick-hb_at<=501); hb_at=uwTick;hb_state=t->data[0];hb_count++; }
    if(t->ident==0x181) { uint32_t tick;memcpy(&tick,t->data+4,4);if(ppg_count && strict_ppg) assert((uint32_t)(tick-last_ppg_tick)==20);last_ppg_tick=tick;ppg_count++; }
    if(t->ident==0x581) { sdo_count++;memcpy(sdo_data,t->data,8); }
    if(t->ident==0x81) emcy_count++;
    if(t->ident==0x681) quality_count++;
    return CO_ERROR_NO;
}
void CO_CANmodule_process(CO_CANmodule_t *m) { (void)m; }
void CO_CANclearPendingSyncPDOs(CO_CANmodule_t *m) { (void)m; }
void CO_CANinterrupt(CO_CANmodule_t *m) { (void)m; }
static void inject(uint16_t id,uint8_t dlc,const uint8_t *data) {
    CO_CANrxMsg_t msg={0};msg.ident=id;msg.DLC=dlc;memcpy(msg.data,data,dlc);
    for(unsigned i=0;i<module->rxSize;i++) { CO_CANrx_t *r=&module->rxArray[i];if(r->CANrx_callback && !((id^r->ident)&r->mask)) {r->CANrx_callback(r->object,&msg);return;} }
    assert(!"unregistered receive ID");
}
static void tick(void) { uwTick++; if(uwTick%8==0) { wave_available=1;wave_tick=uwTick; } g_meas.result_time_ms=uwTick;canopen_app_process(); }
int main(int argc,char **argv) {
    wire_mode=argc>1 && !strcmp(argv[1],"--wire");
    g_meas.spo2=98;g_meas.pulse_rate=72;g_meas.result_valid=1;g_meas.probe_state=1;
    bp.valid=1;bp.sys=118;bp.dia=76;
    assert(canopen_app_init()==0);
    if(wire_mode) {
        uint64_t relative=1800000000000ULL-441763200000ULL;
        uint32_t ms=(uint32_t)(relative%86400000u);uint16_t days=(uint16_t)(relative/86400000u);uint8_t data[6];
        memcpy(data,&ms,4);memcpy(data+4,&days,2);inject(0x100,6,data);
        for(unsigned i=0;i<6500;i++) tick();return 0;
    }
    for(unsigned i=0;i<1600;i++) tick();
    assert(init_count==1); /* 原 CO_RESET_NOT 错误在此复现，不能用桩 PASS 掩盖。 */
    assert(hb_count>=3 && OD_PERSIST_COMM.x1017_producerHeartbeatTime==500);
    assert(OD_PERSIST_COMM.x1014_COB_ID_EMCY==0x81);
    assert(quality_count>=2); /* 第五 TPDO 定时器必须来自标准 0x1804:05。 */
    uint8_t sdo[]={0x40,0x17,0x10,0,0,0,0,0};inject(0x601,8,sdo);tick();
    assert(sdo_count && sdo_data[0]==0x4B && sdo_data[4]==0xF4 && sdo_data[5]==1);
    assert(OD_RAM.x2100_epoch_tick.epoch==0); /* 默认软 RTC 不具备可信 UTC 身份。 */
    assert(ppg_count>50); /* 125Hz 输入必须经过有标签的 50Hz 重采样，禁止改写每点原始间隔。 */
    puts("normal reset / heartbeat / EMCY ID / SDO / untrusted clock / PPG cadence PASS");
    strict_ppg=0; /* 后续负例会主动暂停/复位，不把真实间断伪判为连续 50Hz。 */
    /* 标准 TIME 帧提供毫秒分量；锚点必须与秒边界对应，不能直接拿当前 tick。 */
    uint8_t time_data[6];uint32_t time_ms=123456;uint16_t time_days=16000;
    memcpy(time_data,&time_ms,4);memcpy(time_data+4,&time_days,2);inject(0x100,6,time_data);tick();
    assert(OD_RAM.x2100_epoch_tick.epoch==441763200u+16000u*86400u+123u);
    assert((uint32_t)(uwTick-OD_RAM.x2100_epoch_tick.tick)==457u);
    assert((OD_RAM.x2130_validity_generation.data_valid_flags&0xFu)==0xFu);
    g_paused=1;tick();assert(!(OD_RAM.x2130_validity_generation.data_valid_flags&7u));g_paused=0;
    g_meas.pulse_rate=0;tick();assert(!(OD_RAM.x2130_validity_generation.data_valid_flags&4u));assert(OD_RAM.x2120_vitals.PR==0);g_meas.pulse_rate=72;
    bp_state=ST_MEASURING;tick();assert(!(OD_RAM.x2130_validity_generation.data_valid_flags&8u));bp_state=ST_IDLE;
    bp.valid_tick=uwTick-90001u;tick();assert(!(OD_RAM.x2130_validity_generation.data_valid_flags&8u));bp.valid_tick=uwTick;
    canopen_app_emcy(CO_EMC_GENERIC,CO_EM_GENERIC_ERROR,0);tick();assert(emcy_count);
    NodeClock c={0};uint32_t e,a;node_clock_set(&c,999,time_days,0xFFFFFFF0u);
    node_clock_read(&c,20,&e,&a);assert((uint32_t)(20-a)==35u); /* 999+36 进位 */
    node_clock_read(&c,40000,&e,&a);assert(!e);
    node_clock_set(&c,86400000u,time_days,30);node_clock_read(&c,30,&e,&a);assert(!e);
    node_clock_set(&c,500,time_days,400);node_clock_read(&c,600,&e,&a);assert((uint32_t)(600-a)==700u);
    host_primask=1;node_can_lock();node_can_lock();node_can_unlock();node_can_unlock();assert(host_primask==1);
    host_primask=0;node_can_lock();node_can_lock();node_can_unlock();assert(host_primask==1);node_can_unlock();assert(!host_primask);
    uint8_t nmt[]={0x80,1};inject(0,2,nmt);tick();unsigned old_ppg=ppg_count;
    for(unsigned i=0;i<30;i++) tick();assert(ppg_count==old_ppg);
    nmt[0]=1;inject(0,2,nmt);tick();
    /* 通信复位只重建 CAN；应用复位锁止 CAN，原测量对象保持原值。 */
    nmt[0]=0x82;inject(0,2,nmt);tick();assert(init_count==2);hb_count=0;ppg_count=0;
    assert(OD_RAM.x2130_validity_generation.boot_generation==2 && !OD_RAM.x2100_epoch_tick.epoch);
    nmt[0]=0x81;inject(0,2,nmt);tick();assert(init_count==2 && !module->CANnormal);
    for(unsigned i=0;i<20;i++) tick();assert(init_count==2 && g_meas.spo2==98 && bp.sys==118);
    puts("TIME anchor / wrap / expiry / resync / validity / IRQ nesting / NMT COMM+APP PASS");
    return 0;
}
