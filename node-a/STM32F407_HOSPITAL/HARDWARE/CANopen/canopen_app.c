/* Node-A CANopen 适配：只读取原双屏/传感器状态，不更改 UART、测量或屏任务。 */
#include "CANopen.h"
#include "canopen_app.h"
#include "OD.h"
#include "app_bp.h"
#include "uno.h"
#include "app_bloodoxygen.h"
#include "sys.h"
#include "stm32f4xx.h"
#include "stm32f4xx_can.h"
#include "node_policy.h"
#include <string.h>

extern void CO_CANinterrupt(CO_CANmodule_t *module);
static CO_t *g_CO;
static NodeClock clock_anchor;
static NodeResampler wave;
static uint32_t boot_generation,last_tick,last_wave_tick,last_flags;
static uint8_t running,first_tick,have_wave,wave_request;
/* 测量中止/过期后保持无效，只有新完成代次能解除；避免旧结果因状态回IDLE或tick回绕复活。 */
static uint32_t bp_generation;
static uint8_t bp_blocked;
/* 诊断计数仅 RAM 保存；UART/屏接收环原有溢出计数不被清零。 */
volatile uint32_t node_a_can_comm_resets,node_a_can_app_reset_requests,node_a_can_error,node_a_can_wave_expired;

/* TIME 接收回调在 CAN ISR 中，原栈已校验 DLC=6。仅保存时间锚，不操作屏 RTC。 */
static void time_received(void *object) {
    CO_TIME_t *time=(CO_TIME_t *)object;
    uint32_t ms=CO_getUint32(time->timeStamp);
    uint16_t days=CO_getUint16(time->timeStamp+4);
    node_clock_set(&clock_anchor,ms,days,uwTick);
}

static uint8_t stack_init(void) {
    uint32_t error=0;
    CO_ReturnError_t rc;
    running=0;first_tick=1;have_wave=0;wave_request=0;
    memset(&wave,0,sizeof(wave));memset(&clock_anchor,0,sizeof(clock_anchor));
    if (!g_CO) return 1;
    CO_CANmodule_disable(g_CO->CANmodule);
    rc=CO_CANinit(g_CO,CAN1,CANOPEN_BITRATE);
    if (rc==CO_ERROR_NO)
        rc=CO_CANopenInit(g_CO,NULL,NULL,OD,OD_ENTRY_H1001,CO_NMT_STARTUP_TO_OPERATIONAL,500,500,500,false,CANOPEN_NODE_ID,&error);
    if (rc==CO_ERROR_NO) rc=CO_CANopenInitPDO(g_CO,g_CO->em,OD,CANOPEN_NODE_ID,&error);
    if (rc!=CO_ERROR_NO) {
        node_a_can_error=(uint32_t)(-(int32_t)rc);CO_CANmodule_disable(g_CO->CANmodule);return 1;
    }
    CO_TIME_initCallbackPre(g_CO->TIME,g_CO->TIME,time_received);
    OD_RAM.x2130_validity_generation.boot_generation=++boot_generation;
    OD_RAM.x2130_validity_generation.data_valid_flags=0;
    OD_RAM.x2100_epoch_tick.epoch=0;
    last_flags=0;running=1;node_a_can_error=0;
    CO_CANsetNormalMode(g_CO->CANmodule);
    return 0;
}

uint8_t canopen_app_init(void) {
    /* CO_USE_GLOBALS 返回同一静态对象；不申请堆，也不复位传感器或显示状态。 */
#ifdef MP_FIVE_NODE_A
    OD_PERSIST_COMM.x1801_TPDOCommunicationParameter.COB_IDUsedByTPDO=0x80000281u;
#endif
    g_CO=CO_new(NULL,NULL);
    return stack_init();
}

void canopen_app_produce(void) {
    measurement_t measurement;
    NodeClock time;
    uint32_t epoch,anchor,flags=0,now=uwTick;
    bp_last_t bp=bp_last_get();
    bp_state_t state=bp_state_get();
    if (!running) return;
    /* ISR 写 UNO 快照/TIME；短临界段取得一致副本，并恢复原始 IRQ 状态。 */
    node_can_lock();measurement=g_meas;time=clock_anchor;node_can_unlock();
    node_clock_read(&time,now,&epoch,&anchor);
    OD_RAM.x2100_epoch_tick.epoch=epoch;OD_RAM.x2100_epoch_tick.tick=anchor;
    uint8_t fresh=(!g_paused && measurement.probe_state && measurement.result_valid
                    && (uint32_t)(now-measurement.result_time_ms)<=4000u);
    uint8_t spo2_ok=fresh && measurement.spo2>0 && measurement.spo2<=100;
    /* PR 采用屏任务已做峰检/保持超时处理后的共享值，不依赖 DEBUG_PPG 诊断变量。 */
    uint8_t pr_ok=fresh && measurement.pulse_rate>0 && measurement.pulse_rate<=350;
    /* 只收紧 CAN 时效至 90s，原屏仍显示历史测量结果；不改血压测量状态机。 */
    if(bp.valid && bp.result_generation && bp.result_generation!=bp_generation) {
        bp_generation=bp.result_generation;bp_blocked=0;
    }
    if(state!=ST_IDLE || (bp.valid && (uint32_t)(now-bp.valid_tick)>90000u))bp_blocked=1;
    uint8_t bp_ok=bp.valid && bp.result_generation && !bp_blocked && state==ST_IDLE && (uint32_t)(now-bp.valid_tick)<=90000u
        && bp.sys>0 && bp.sys<=400 && bp.dia>0 && bp.dia<=400;
#ifdef MP_FIVE_NODE_A
    bp_ok=0;
#endif
    OD_RAM.x2120_vitals.SpO2=spo2_ok?(uint16_t)(measurement.spo2*100):0;
    OD_RAM.x2120_vitals.PR=pr_ok?(uint16_t)(measurement.pulse_rate*100):0;
    OD_RAM.x2120_vitals.NIBP_SYS=bp_ok?(uint16_t)(bp.sys*10):0;
    OD_RAM.x2120_vitals.NIBP_DIA=bp_ok?(uint16_t)(bp.dia*10):0;
    /* 保留四个既有PDO，使用原保留0x281传递完成tick+同值身份镜像，均为1Hz。 */
    OD_RAM.x2111_nibp_result.completion_tick=bp.valid?bp.valid_tick:0;
    OD_RAM.x2111_nibp_result.sys_dia=(uint32_t)OD_RAM.x2120_vitals.NIBP_SYS|
        ((uint32_t)OD_RAM.x2120_vitals.NIBP_DIA<<16);
    flags|=1u<<9; /* 完成时间扩展版本1；不是新的有效位，也不改变synthetic身份。 */

    if (!fresh) { memset(&wave,0,sizeof(wave));have_wave=0;UNO_WaveClearCAN(); }
    else {
        int32_t value;uint32_t tick;
        /* 最多消费 32 个原始点且每轮只提交一个输出，不在一次 TPDO 处理前覆盖多点。 */
        for(unsigned budget=0;budget<32u;budget++) {
            if(node_wave_output(&wave,&value,&tick)) {
                if((uint32_t)(now-tick)<=250u) {
                    OD_RAM.x2110_ppg_waveform.ir_wave=(int32_t)((int64_t)value*1000000/4194304);
                    OD_RAM.x2110_ppg_waveform.sample_tick=tick;
                    CO_TPDOsendRequest(&g_CO->TPDO[0]);wave_request=1;have_wave=1;last_wave_tick=tick;
                } else node_a_can_wave_expired++;
                break;
            }
            if(!UNO_WaveTakeCAN(&value,&tick,1)) break;
            if((uint32_t)(now-tick)>250u) { node_a_can_wave_expired++;wave.have=0;continue; }
            node_wave_input(&wave,value,tick);
        }
    }
    /* 未同步 UTC 不宣称有效 LIVE；bit8 明确当前 PPG 为接收时基的线性重采样。 */
    if(epoch) {
        if(fresh && have_wave && (uint32_t)(now-last_wave_tick)<=100u) flags|=1u|(1u<<7)|(1u<<8);
        if(spo2_ok) flags|=1u<<1;
        if(pr_ok) flags|=1u<<2;
        if(bp_ok) flags|=1u<<3;
    }
    if(measurement.probe_state) flags|=1u<<4;
    if(state==ST_MEASURING) flags|=1u<<5;
    if(state==ST_STOPPING) flags|=1u<<6;
    OD_RAM.x2130_validity_generation.data_valid_flags=flags;
    /* 有效性变化立即通告，周期回执仍每秒发送；不设置 synthetic 位冒充原始/合成身份。 */
    if(flags!=last_flags) { last_flags=flags;CO_TPDOsendRequest(&g_CO->TPDO[4]); }
}

void canopen_app_process(void) {
    if(!running || !g_CO) return;
    uint32_t now=uwTick,elapsed=first_tick?0u:(uint32_t)(now-last_tick),next=1000000u;
    first_tick=0;last_tick=now;
    /* 防止主循环长期停顿后 us 乘法溢出；上限只影响协议追赶，不刷新测量时效。 */
    uint32_t diff=elapsed>1000u?1000000u:elapsed*1000u;
    CO_NMT_reset_cmd_t reset=CO_process(g_CO,false,diff,&next);
    if(reset==CO_RESET_COMM) { node_a_can_comm_resets++;(void)stack_init();return; }
    if(reset==CO_RESET_APP) {
        /* CAN NMT 不得远程重启双屏/采集；锁止通信并等待显式本地重初始化。 */
        node_a_can_app_reset_requests++;running=0;clock_anchor.valid=0;
        OD_RAM.x2100_epoch_tick.epoch=0;OD_RAM.x2130_validity_generation.data_valid_flags=0;
        CO_CANmodule_disable(g_CO->CANmodule);return;
    }
    /* CO_RESET_NOT 是正常路径，持续驱动心跳、SDO 与 TPDO，不能重建协议栈。 */
    canopen_app_produce();
    bool_t sync=CO_process_SYNC(g_CO,diff,&next);
    CO_process_RPDO(g_CO,sync,diff,&next);
    /* 栈在启动/非 OP 时会自动置 sendRequest；没有新样本时暂不处理 PPG，
     * 防止启动零点或旧点重发。结束后恢复 SDO 配置的 valid，不能绕过用户禁用 PDO。 */
    bool_t configured=g_CO->TPDO[0].PDO_common.valid;
    if(!wave_request) g_CO->TPDO[0].PDO_common.valid=false;
    CO_process_TPDO(g_CO,sync,diff,&next);
    g_CO->TPDO[0].PDO_common.valid=configured;wave_request=0;
}
void canopen_app_CAN_interrupt(void) { if(running && g_CO) CO_CANinterrupt(g_CO->CANmodule); }
void canopen_app_emcy(uint16_t code,uint8_t bit,uint8_t info) {
    if(running && g_CO) CO_errorReport(g_CO->em,bit,code,info);
}
