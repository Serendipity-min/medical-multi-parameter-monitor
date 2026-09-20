/* 两个测试生产者和一个 Gateway 使用独立 OD/协议状态；仅共享有界 CAN 驱动。 */
#include "mp_stack.h"
#include <string.h>
static MpStack *active;
static void emergency(uint16_t id,uint16_t code,uint8_t reg,uint8_t bit,uint32_t info) {
  (void)reg;(void)bit;(void)info;
  if (active && id>=0x81 && id<=0x82) active->emcy[id-0x81]=code;
}
static int init_node(MpStack *s,unsigned number) {
  MpNode *n=&s->nodes[number-1];uint32_t used=0,err=0;
  n->port=(MpCanPort){number,true,NULL};n->tick=0;n->boot++;
  if (mp_od_init(&n->od,number,&n->config)) return -1;
  n->co=CO_new(&n->config,&used);s->allocated+=used;
  if (!n->co || CO_CANinit(n->co,&n->port,500)!=CO_ERROR_NO) return -2;
  /* 测试节点先进入 PRE-OP；只有 Gateway 启动后才广播 NMT START。 */
  uint16_t control=number==3?CO_NMT_STARTUP_TO_OPERATIONAL:0;
  if (CO_CANopenInit(n->co,NULL,NULL,&n->od.od,NULL,control,100,1000,1000,false,number,&err)!=CO_ERROR_NO) return -(int)(100+err);
  if (CO_CANopenInitPDO(n->co,n->co->em,&n->od.od,number,&err)!=CO_ERROR_NO) return -(int)(10000+err);
  if (number==3) CO_EM_initCallbackRx(n->co->em,emergency);
  CO_CANsetNormalMode(n->co->CANmodule);return 0;
}
int mp_stack_init(MpStack *s,uint32_t epoch) {
  memset(s,0,sizeof(*s));s->epoch=epoch;active=s;mp_bus_reset();
  for (unsigned i=1;i<=3;i++) { int rc=init_node(s,i);if(rc) {mp_stack_close(s);return rc;} }
  mp_stack_nmt(s,0,CO_NMT_ENTER_OPERATIONAL);return 0;
}
void mp_stack_close(MpStack *s) {
  for(unsigned i=0;i<3;i++) if(s->nodes[i].co) {CO_delete(s->nodes[i].co);s->nodes[i].co=NULL;}
  if(active==s)active=NULL;
  mp_bus_reset();
}
void mp_stack_nmt(MpStack *s,unsigned node,CO_NMT_command_t command) { CO_NMT_sendCommand(s->nodes[2].co->NMT,command,node); }
int mp_stack_restart(MpStack *s,unsigned node) {
  if(node<1||node>3)return -1;
  CO_delete(s->nodes[node-1].co);s->nodes[node-1].co=NULL;s->resets[node-1]++;
  int rc=init_node(s,node);if(!rc)mp_stack_nmt(s,node==3?0:node,CO_NMT_ENTER_OPERATIONAL);return rc;
}
void mp_stack_enable(MpStack *s,unsigned node,bool enabled) { if(node>=1&&node<=3)s->nodes[node-1].port.enabled=enabled; }
int mp_stack_online(MpStack *s,unsigned node) {
  if(node<1||node>2)return 0;
  CO_NMT_internalState_t state;
  CO_HBconsumer_t *hb=s->nodes[2].co->HBcons;
  return CO_HBconsumer_getState(hb,node-1)==CO_HBconsumer_ACTIVE && CO_HBconsumer_getNmtState(hb,node-1,&state)==0 && state==CO_NMT_OPERATIONAL;
}
static void request(MpNode *n,unsigned pdo) { CO_TPDOsendRequest(&n->co->TPDO[pdo]); }
static void sample(MpStack *s,MpNode *n,unsigned id) {
  n->tick++;
  /* 固定整数锯齿仅用于验证映射，质量位 bit31 永久标识合成来源。RR 无算法输入，保持无效。 */
  if(n->tick==1 || n->tick%1000==0) {
    mp_od_write(&n->od,0x2100,1,s->epoch?s->epoch+s->milliseconds/1000:0);
    /* anchor 对应整秒边界，即使节点在秒中间重启也不引入一秒的时间偏移。 */
    mp_od_write(&n->od,0x2100,2,n->tick-s->milliseconds%1000);request(n,3);
    mp_od_write(&n->od,0x2130,1,0x80000000U|(id==1?0x0FU:0x17U));
    mp_od_write(&n->od,0x2130,2,n->boot);request(n,4);
    const uint16_t a[4]={9700,7300,1160,740},b[4]={7300,0,3670,0};
    for(unsigned j=0;j<4;j++)mp_od_write(&n->od,0x2120,j+1,id==1?a[j]:b[j]);
    request(n,2);
  }
  if(n->tick%(id==1?20:4)==0) {
    mp_od_write(&n->od,0x2110,1,id==1?(n->tick%1000)*1000:(uint32_t)((int)(n->tick%1000)-500));
    mp_od_write(&n->od,0x2110,2,n->tick);request(n,0);
  }
  if(id==2 && n->tick%20==0) {
    mp_od_write(&n->od,0x2111,1,(uint32_t)((int)(n->tick%4000)*500-1000000));
    mp_od_write(&n->od,0x2111,2,n->tick);request(n,1);
  }
}
void mp_stack_tick(MpStack *s) {
  s->milliseconds++;
  for(unsigned i=0;i<2;i++)if(s->nodes[i].port.enabled)sample(s,&s->nodes[i],i+1);
  mp_bus_poll();
  for(unsigned i=0;i<3;i++) {
    MpNode *n=&s->nodes[i];if(!n->port.enabled)continue;
    CO_NMT_reset_cmd_t reset=CO_process(n->co,false,1000,NULL);
    if(reset!=CO_RESET_NOT) { (void)mp_stack_restart(s,i+1);continue; }
    CO_process_RPDO(n->co,false,1000,NULL);CO_process_TPDO(n->co,false,1000,NULL);
  }
  mp_bus_poll();
}
