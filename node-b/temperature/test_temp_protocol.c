/* 只替换UART硬件边界；温度解析、B生产者和CANopenNode均为实际代码。 */
#include "CANopen.h"
#include "OD.h"
#include "b_canopen_app.h"
#include "b_temperature.h"
#include "bio_v2.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
extern void b4_host_now(uint32_t now);
extern void b4_host_wire(FILE *f);
extern void b4_host_receive(uint32_t id,uint8_t dlc,const uint8_t *data);
extern uint32_t TimeBase_GetMs(void);
BTempDiag g_b_temp;
static uint32_t last_feed=0xffffffffu;
void BTemp_Init(void){gy641_init(&g_b_temp.module);}
void BTemp_Task(uint32_t now){
    now=TimeBase_GetMs(); /* 替代UART边界以接收时刻入队，而不是任务旧参数。 */
    if(now<3000u && now%1000u==0 && last_feed!=now){
        static const uint8_t f[12]={0xa4,3,7,7,0x62,0x0c,0xeb,0x0c,0x3f,0x0e,0x20,0x87};
        for(unsigned i=0;i<12;i++)gy641_feed(&g_b_temp.module,f[i],now);
        last_feed=now;
    }
}
int BTemp_Get(uint32_t now,uint16_t *value){return gy641_object(&g_b_temp.module,now,value);}
int main(int argc,char **argv){
    assert(argc==2);FILE *wire=fopen(argv[1],"w");assert(wire);b4_host_wire(wire);
    BioV2_Init(0);BTemp_Init();CanOpen_Init();uint32_t seq=0;
    for(uint32_t now=0;now<7000u;now++){
        b4_host_now(now);
        if(now%1000u==0){
            uint64_t utc=1792713600000ULL+now-441763200000ULL;
            uint8_t data[6];CO_setUint32(data,(uint32_t)(utc%86400000u));CO_setUint16(data+4,(uint16_t)(utc/86400000u));
            b4_host_receive(0x100,6,data);
        }
        if(now%4u==0){BioV2_Process(200000,640000,now,++seq,0);BCan_Sample(now,seq,0);}
        /* TIME已以当前时刻锁存，但主循环参数仍可能是前一毫秒。 */
        CanOpen_Task(now && now%1000u==0 ? now-1u : now);
        if(now>=1000u && now<=4500u){assert(OD_RAM.x2120_vitals.TEMP==3307u);assert(OD_RAM.x2130_validity_generation.data_valid_flags&16u);}
        if(now>4500u){assert(OD_RAM.x2120_vitals.TEMP==0);assert(!(OD_RAM.x2130_validity_generation.data_valid_flags&16u));}
    }
    assert(g_bio_v2.samples==1750 && !g_bio_v2.discontinuities && !g_b_can.overflow);
    assert(g_b_temp.module.frames==3);b4_host_wire(NULL);fclose(wire);
    puts("TEMP_REAL_B_PRODUCER_PASS cents_bit4 stale_invalid 250SPS_1750_samples NO_TARGET_IO");return 0;
}
