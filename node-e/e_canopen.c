/* 复用 A 的血压完成时间和同值身份协议，E 不产生任何血氧有效位。 */
#include "canopen_app.h"
#include "OD.h"
#include "app_bp.h"
#include "sys.h"
#include "node_policy.h"
#include <string.h>

extern void CO_CANinterrupt(CO_CANmodule_t *module);
static CO_t *co;
static NodeClock clock_anchor;
static uint32_t generation,last_tick,bp_generation,last_flags;
static uint8_t running,first,bp_blocked;

static void time_received(void *object) {
    CO_TIME_t *t=object;
    node_clock_set(&clock_anchor,CO_getUint32(t->timeStamp),CO_getUint16(t->timeStamp+4),uwTick);
}
static uint8_t stack_init(void) {
    uint32_t error=0;
    running=0;first=1;last_flags=0;
    memset(&clock_anchor,0,sizeof(clock_anchor));
    bp_generation=bp_last_get().result_generation;bp_blocked=1;
    if(!co)return 1;
    CO_CANmodule_disable(co->CANmodule);
    CO_ReturnError_t rc=CO_CANinit(co,CAN1,500);
    if(rc==CO_ERROR_NO)rc=CO_CANopenInit(co,NULL,NULL,OD,OD_ENTRY_H1001,CO_NMT_STARTUP_TO_OPERATIONAL,500,500,500,false,5,&error);
    if(rc==CO_ERROR_NO)rc=CO_CANopenInitPDO(co,co->em,OD,5,&error);
    if(rc!=CO_ERROR_NO)return 1;
    CO_TIME_initCallbackPre(co->TIME,co->TIME,time_received);
    OD_RAM.x2130_validity_generation.boot_generation=++generation;
    OD_RAM.x2130_validity_generation.data_valid_flags=0;
    OD_RAM.x2100_epoch_tick.epoch=0;
    running=1;CO_CANsetNormalMode(co->CANmodule);return 0;
}
uint8_t canopen_app_init(void) {
    OD_PERSIST_COMM.x1014_COB_ID_EMCY=0x85;
    OD_PERSIST_COMM.x1018_identity.productCode=0x4d504d45;
    OD_PERSIST_COMM.x1800_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x80000185u;
    OD_PERSIST_COMM.x1801_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x285;
    OD_PERSIST_COMM.x1802_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x385;
    OD_PERSIST_COMM.x1803_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x485;
    OD_PERSIST_COMM.x1804_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x685;
    OD_RAM.x1200_SDOServerParameter.COB_IDClientToServerRx=0x605;
    OD_RAM.x1200_SDOServerParameter.COB_IDServerToClientTx=0x585;
    co=CO_new(NULL,NULL);return stack_init();
}
void canopen_app_produce(void) {
    NodeClock time;uint32_t epoch,anchor,now=uwTick;
    bp_last_t bp=bp_last_get();bp_state_t state=bp_state_get();
    node_can_lock();time=clock_anchor;node_can_unlock();node_clock_read(&time,now,&epoch,&anchor);
    if(bp.valid && bp.result_generation && bp.result_generation!=bp_generation){bp_generation=bp.result_generation;bp_blocked=0;}
    if(state!=ST_IDLE || (bp.valid && (uint32_t)(now-bp.valid_tick)>90000u))bp_blocked=1;
    uint8_t valid=epoch && bp.valid && bp.result_generation && !bp_blocked && state==ST_IDLE &&
        (uint32_t)(now-bp.valid_tick)<=90000u && bp.sys>0 && bp.sys<=400 && bp.dia>0 && bp.dia<=400;
    OD_RAM.x2100_epoch_tick.epoch=epoch;OD_RAM.x2100_epoch_tick.tick=anchor;
    OD_RAM.x2120_vitals.SpO2=OD_RAM.x2120_vitals.PR=0;
    OD_RAM.x2120_vitals.NIBP_SYS=valid?(uint16_t)(bp.sys*10u):0;
    OD_RAM.x2120_vitals.NIBP_DIA=valid?(uint16_t)(bp.dia*10u):0;
    OD_RAM.x2111_nibp_result.completion_tick=bp.valid?bp.valid_tick:0;
    OD_RAM.x2111_nibp_result.sys_dia=OD_RAM.x2120_vitals.NIBP_SYS|((uint32_t)OD_RAM.x2120_vitals.NIBP_DIA<<16);
    uint32_t flags=(1u<<9)|(valid?1u<<3:0)|(state==ST_MEASURING?1u<<5:0)|(state==ST_STOPPING?1u<<6:0);
    OD_RAM.x2130_validity_generation.data_valid_flags=flags;
    if(flags!=last_flags){last_flags=flags;CO_TPDOsendRequest(&co->TPDO[4]);}
}
void canopen_app_process(void) {
    if(!running)return;
    uint32_t now=uwTick,elapsed=first?0u:now-last_tick;first=0;last_tick=now;
    uint32_t diff=elapsed>1000?1000000:elapsed*1000;
    CO_NMT_reset_cmd_t reset=CO_process(co,false,diff,NULL);
    if(reset==CO_RESET_COMM){(void)stack_init();return;}
    if(reset!=CO_RESET_NOT){running=0;CO_CANmodule_disable(co->CANmodule);return;}
    canopen_app_produce();bool_t sync=CO_process_SYNC(co,diff,NULL);
    CO_process_RPDO(co,sync,diff,NULL);CO_process_TPDO(co,sync,diff,NULL);
}
void canopen_app_CAN_interrupt(void){if(running)CO_CANinterrupt(co->CANmodule);}
void canopen_app_emcy(uint16_t code,uint8_t bit,uint8_t info){if(running)CO_errorReport(co->em,bit,code,info);}
