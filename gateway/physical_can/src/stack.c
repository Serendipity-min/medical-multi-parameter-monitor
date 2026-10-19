/* A/B 没有 CO_new、采样器或 TPDO；此文件替换模拟 mp_stack.c，仅用于独立物理 target。 */
#include "physical.h"
#include <string.h>
PhysicalNode physical_nodes[2];
bool physical_link_ready;
uint32_t physical_malformed;
static MpStack *active;
static uint32_t time_sent;
static uint64_t elapsed_wrap;
/* CAN/缓存时效仍使用原32位差值；绝对 UTC 单独扩展回绕，避免49.7天后倒退。 */
uint64_t physical_now(const MpStack *s) {return (uint64_t)s->epoch*1000u+elapsed_wrap+s->milliseconds;}

void physical_invalidate(void) {
    memset(physical_nodes,0,sizeof(physical_nodes));physical_link_ready=false;
    if(active) mp_bus_set_online(false);
}
bool physical_fresh(unsigned node,unsigned pdo,uint32_t now) {
    return node>=1 && node<=2 && pdo<5 && physical_nodes[node-1].seen[pdo]
        && (uint32_t)(now-physical_nodes[node-1].at[pdo])<=1500u;
}
void physical_receive(MpCanFrame *f) {
    if(!active || !physical_link_ready || f->ident>0x7FF || f->dlc>8) return;
    for(unsigned node=1;node<=2;node++) {
        if(f->ident==0x700u+node && (f->dlc!=1 || (f->data[0]!=0 && f->data[0]!=4 && f->data[0]!=5 && f->data[0]!=127))) {physical_malformed++;return;}
        PhysicalNode *n=&physical_nodes[node-1];
        /* Boot-up 表示对端通信重启；旧 PDO 镜像不可凭仍存活的字节恢复有效。 */
        if(f->ident==0x700u+node && f->data[0]==0) {
            /* 对端掉电后 RAM generation 可能又是1；独立观察代次避免复用旧会话。 */
            uint32_t session=n->session_generation+1u;memset(n,0,sizeof(*n));n->session_generation=session;
        }
        for(unsigned pdo=0;pdo<5;pdo++) if(f->ident==mp_pdo_id(node,pdo)) {
            if(f->dlc!=8) {physical_malformed++;return;}
            if(pdo==4) {
                uint32_t generation;memcpy(&generation,f->data+4,4);
                if(!generation) {physical_malformed++;return;}
                if(generation!=n->generation) {uint32_t session=n->session_generation+1u;memset(n,0,sizeof(*n));n->generation=generation;n->session_generation=session;}
            }
            n->seen[pdo]=true;n->at[pdo]=active->milliseconds;
        }
    }
    mp_bus_receive(f);
}
static void emergency(uint16_t id,uint16_t code,uint8_t reg,uint8_t bit,uint32_t info) {
    (void)reg;(void)bit;(void)info;
    if(active && id>=0x81 && id<=0x82) active->emcy[id-0x81]=code;
}
static int gateway_init(MpStack *s) {
    MpNode *g=&s->nodes[2];uint32_t used=0,error=0;
    g->port=(MpCanPort){3,false,NULL};g->boot++;
    if(mp_od_init(&g->od,3,&g->config)) return -1;
    g->co=CO_new(&g->config,&used);s->allocated+=used;
    if(!g->co || CO_CANinit(g->co,&g->port,500)!=CO_ERROR_NO) return -2;
    if(CO_CANopenInit(g->co,NULL,NULL,&g->od.od,NULL,CO_NMT_STARTUP_TO_OPERATIONAL,100,1000,1000,false,3,&error)!=CO_ERROR_NO) return -3;
    if(CO_CANopenInitPDO(g->co,g->co->em,&g->od.od,3,&error)!=CO_ERROR_NO) return -4;
    CO_EM_initCallbackRx(g->co->em,emergency);g->port.enabled=true;CO_CANsetNormalMode(g->co->CANmodule);
    /* 此处物理 CAN 尚未就绪；START 由 lifecycle 在硬件清队列之后提交。 */
    return 0;
}
int mp_stack_init(MpStack *s,uint32_t epoch) {
    memset(s,0,sizeof(*s));s->epoch=epoch;active=s;elapsed_wrap=0;mp_bus_reset();
    memset(physical_nodes,0,sizeof(physical_nodes));physical_link_ready=false;physical_malformed=0;time_sent=0u-10000u;
    int rc=gateway_init(s);if(rc) mp_stack_close(s);return rc;
}
void mp_stack_close(MpStack *s) {
    MpNode *g=&s->nodes[2];g->port.enabled=false;
    if(g->co) CO_delete(g->co);
    g->co=NULL;g->port.module=NULL;
    for(unsigned i=0;i<g->od.nentry;i++) g->od.entries[i].extension=NULL;
    if(active==s) active=NULL;
    physical_invalidate();mp_bus_reset();
}
int mp_stack_restart(MpStack *s,unsigned node) {
    if(node!=3) return -1; /* 无本地 A/B 实例可重建。 */
    mp_stack_close(s);active=s;mp_bus_reset();s->resets[2]++;
    int rc=gateway_init(s);if(rc) mp_stack_close(s);return rc;
}
void mp_stack_enable(MpStack *s,unsigned node,bool enabled) { (void)s;(void)node;(void)enabled; }
void mp_stack_nmt(MpStack *s,unsigned node,CO_NMT_command_t command) {
    if(s->nodes[2].co) CO_NMT_sendCommand(s->nodes[2].co->NMT,command,node);
}
int mp_stack_online(MpStack *s,unsigned node) {
    if(node<1 || node>2 || !physical_link_ready || !s->nodes[2].co) return 0;
    CO_NMT_internalState_t state;CO_HBconsumer_t *hb=s->nodes[2].co->HBcons;
    return hb && CO_HBconsumer_getState(hb,node-1)==CO_HBconsumer_ACTIVE
        && CO_HBconsumer_getNmtState(hb,node-1,&state)==0 && state==CO_NMT_OPERATIONAL;
}
void mp_stack_tick(MpStack *s) {
    s->milliseconds++;
    if(!s->milliseconds) elapsed_wrap+=0x100000000ULL;
    mp_bus_poll();MpNode *g=&s->nodes[2];
    if(!g->co || !g->port.enabled) return;
    CO_NMT_reset_cmd_t reset=CO_process(g->co,false,1000,NULL);
    if(reset!=CO_RESET_NOT) { physical_invalidate();g->port.enabled=false;return; }
    CO_process_RPDO(g->co,false,1000,NULL);CO_process_TPDO(g->co,false,1000,NULL);
    /* 标准 TIME 仅在上层已获得可信 SNTP epoch 后发出；不是默认日期或测试生产者。 */
    if(physical_link_ready && s->epoch && (uint32_t)(s->milliseconds-time_sent)>=10000u) {
        uint64_t unix_ms=physical_now(s);
        uint64_t relative=unix_ms-441763200000ULL;
        uint32_t ms=(uint32_t)(relative%86400000u);uint16_t days=(uint16_t)(relative/86400000u);
        CO_CANtx_t tx={0};tx.ident=0x100;tx.DLC=6;memcpy(tx.data,&ms,4);memcpy(tx.data+4,&days,2);
        if(CO_CANsend(g->co->CANmodule,&tx)==CO_ERROR_NO) time_sent=s->milliseconds;
    }
    mp_bus_poll();
}
