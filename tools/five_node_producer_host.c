/* 仅串口/压力快照及CAN控制器为Host边界，使用实际D/E生产者和协议栈。 */
#include "CANopen.h"
#include "OD.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifdef ROLE_D
#include "b_canopen_app.h"
#include "b_temperature.h"
BTempDiag g_b_temp;
void BTemp_Task(uint32_t now){
    if(now%1000 || (now>=4000 && now<8000))return;
    const uint8_t bytes[12]={0xa4,3,7,7,0x62,0x0c,0xeb,0x0c,0x3f,0x0e,0x20,0x87};
    for(unsigned i=0;i<12;i++)gy641_feed(&g_b_temp.module,bytes[i],now);
}
int BTemp_Get(uint32_t now,uint16_t *value){return gy641_object(&g_b_temp.module,now,value);}
#define NODE 4u
#else
#include "canopen_app.h"
#include "app_bp.h"
volatile uint32_t uwTick;
static bp_last_t bp;
bp_last_t bp_last_get(void){return bp;}
bp_state_t bp_state_get(void){return ST_IDLE;}
#define NODE 5u
#endif
extern void b4_host_now(uint32_t);
extern void b4_host_wire(FILE *);
extern void b4_host_receive(uint32_t,uint8_t,const uint8_t *);
static void time_sync(uint32_t now){
    uint64_t relative=1800000000000ULL+now-441763200000ULL;
    uint32_t ms=relative%86400000u;uint16_t days=relative/86400000u;uint8_t data[6];
    memcpy(data,&ms,4);memcpy(data+4,&days,2);b4_host_receive(0x100,6,data);
}
int main(void){
    FILE *wire=tmpfile();assert(wire);b4_host_wire(wire);
#ifdef ROLE_D
    CanOpen_Init();
#else
    assert(canopen_app_init()==0);bp.valid=1;bp.result_generation=1;bp.sys=120;bp.dia=80;
#endif
    for(uint32_t now=0;now<100000;now++){
        b4_host_now(now);if(now%10000==0)time_sync(now);
        if(now==1000){uint8_t request[8]={0x40,0x17,0x10,0,0,0,0,0};b4_host_receive(0x600+NODE,8,request);}
#ifdef ROLE_D
        CanOpen_Task(now);
#else
        uwTick=now;canopen_app_process();
#endif
    }
#ifndef ROLE_D
    /* 通信重启不能把模块保留的旧完成结果重新标成新测量。 */
    b4_host_now(100000);uwTick=100000;bp.result_generation=2;bp.valid_tick=100000;canopen_app_process();
    assert(OD_RAM.x2130_validity_generation.data_valid_flags&8u);
    uint8_t reset[2]={130,NODE};b4_host_receive(0,2,reset);canopen_app_process();
    time_sync(100000);canopen_app_process();assert(!(OD_RAM.x2130_validity_generation.data_valid_flags&8u));
    bp.result_generation=3;canopen_app_process();assert(OD_RAM.x2130_validity_generation.data_valid_flags&8u);
#endif
    rewind(wire);unsigned tick,id,length,heartbeat=0,scalars=0,invalid=0,valid=0,sdo=0;
    while(fscanf(wire,"%u %u %u",&tick,&id,&length)==3){
        unsigned byte;uint8_t data[8]={0};for(unsigned i=0;i<length;i++){assert(fscanf(wire,"%u",&byte)==1);data[i]=(uint8_t)byte;}
        assert(id!=0x180+NODE && (NODE!=4 || id!=0x280+NODE));
        if(id==0x700+NODE)heartbeat++;
        if(id==0x580+NODE){assert(data[0]==0x4b && data[4]==0xf4 && data[5]==1);sdo++;}
        if(id==0x380+NODE){
            uint16_t values[4];memcpy(values,data,8);assert(values[0]==0 && values[1]==0);scalars++;
        }
        if(id==0x680+NODE){
            uint32_t flags;memcpy(&flags,data,4);
#ifdef ROLE_D
            assert(!(flags&15u));if(flags&16u)valid++;else invalid++;
#else
            assert(!(flags&7u));if(flags&8u)valid++;else if(tick>90000)invalid++;
#endif
        }
    }
    assert(heartbeat>100 && scalars>50 && valid && invalid && sdo);
    assert(OD_PERSIST_COMM.x1014_COB_ID_EMCY==0x80+NODE);
    assert(OD_RAM.x1200_SDOServerParameter.COB_IDClientToServerRx==0x600+NODE);
    fclose(wire);puts("SINGLE_MODULE_PRODUCER_HOST_PASS");return 0;
}
