#include "CANopen.h"
#include "OD.h"
#include "b_canopen_app.h"
#include "b_temperature.h"
#include "timer.h"
#include "node_policy.h"
#include "stm32f4xx.h"
#include <string.h>

extern void CO_CANinterrupt(CO_CANmodule_t *module);
static CO_t *co;
static NodeClock clock_anchor;
static uint32_t generation,last_tick,last_flags;
static uint8_t running,first;
BCanDiag g_b_can;
static void time_received(void *object){
    CO_TIME_t *t=object;
    node_clock_set(&clock_anchor,CO_getUint32(t->timeStamp),CO_getUint16(t->timeStamp+4),TimeBase_GetMs());
}
static void stack_init(void){
    uint32_t error=0;running=0;first=1;last_flags=0;
    memset(&clock_anchor,0,sizeof(clock_anchor));
    if(!co){g_b_can.error=1;return;}
    CO_CANmodule_disable(co->CANmodule);
    CO_ReturnError_t rc=CO_CANinit(co,CAN1,500);
    if(rc==CO_ERROR_NO)rc=CO_CANopenInit(co,NULL,NULL,OD,OD_ENTRY_H1001,CO_NMT_STARTUP_TO_OPERATIONAL,500,500,500,false,4,&error);
    if(rc==CO_ERROR_NO)rc=CO_CANopenInitPDO(co,co->em,OD,4,&error);
    if(rc!=CO_ERROR_NO){g_b_can.error=(uint32_t)(-(int32_t)rc);return;}
    CO_TIME_initCallbackPre(co->TIME,co->TIME,time_received);
    OD_RAM.x2130_validity_generation.boot_generation=++generation;
    OD_RAM.x2130_validity_generation.data_valid_flags=0;OD_RAM.x2100_epoch_tick.epoch=0;
    running=1;CO_CANsetNormalMode(co->CANmodule);
}
void CanOpen_Init(void){
    OD_PERSIST_COMM.x1014_COB_ID_EMCY=0x84;
    OD_PERSIST_COMM.x1018_identity.productCode=0x4d504d44;
    OD_PERSIST_COMM.x1800_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x80000184u;
    OD_PERSIST_COMM.x1801_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x80000284u;
    OD_PERSIST_COMM.x1802_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x384;
    OD_PERSIST_COMM.x1803_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x484;
    OD_PERSIST_COMM.x1804_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x684;
    OD_RAM.x1200_SDOServerParameter.COB_IDClientToServerRx=0x604;
    OD_RAM.x1200_SDOServerParameter.COB_IDServerToClientTx=0x584;
    co=CO_new(NULL,NULL);stack_init();
}
void CanOpen_Task(uint32_t now){
    BTemp_Task(now);if(!running)return;
    uint32_t elapsed=first?0u:now-last_tick;first=0;last_tick=now;
    uint32_t diff=elapsed>1000?1000000:elapsed*1000;
    CO_NMT_reset_cmd_t reset=CO_process(co,false,diff,NULL);
    if(reset==CO_RESET_COMM){g_b_can.comm_reset++;stack_init();return;}
    if(reset!=CO_RESET_NOT){g_b_can.app_reset_rejected++;running=0;CO_CANmodule_disable(co->CANmodule);return;}
    NodeClock time;uint32_t epoch,anchor;
    node_can_lock();time=clock_anchor;now=TimeBase_GetMs();node_can_unlock();
    node_clock_read(&time,now,&epoch,&anchor);
    uint16_t centi=0;uint8_t valid=epoch && BTemp_Get(now,&centi);
    OD_RAM.x2100_epoch_tick.epoch=epoch;OD_RAM.x2100_epoch_tick.tick=anchor;
    OD_RAM.x2120_vitals.HR=OD_RAM.x2120_vitals.RR=0;
    OD_RAM.x2120_vitals.TEMP=valid?centi:0;
    OD_RAM.x2120_vitals.reserved=valid?(uint16_t)(now-g_b_temp.module.last_ms):65535u;
    uint32_t flags=valid?1u<<4:0;
    OD_RAM.x2130_validity_generation.data_valid_flags=flags;
    if(flags!=last_flags){last_flags=flags;CO_TPDOsendRequest(&co->TPDO[4]);}
    bool_t sync=CO_process_SYNC(co,diff,NULL);
    CO_process_RPDO(co,sync,diff,NULL);CO_process_TPDO(co,sync,diff,NULL);
}
void BCan_Interrupt(void){if(running)CO_CANinterrupt(co->CANmodule);}
void CAN1_RX0_IRQHandler(void){BCan_Interrupt();}
void CAN1_TX_IRQHandler(void){BCan_Interrupt();}
void CAN1_SCE_IRQHandler(void){BCan_Interrupt();}
