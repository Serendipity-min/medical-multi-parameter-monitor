/* 验证真实 CANopenNode 状态机，断线从驱动入口注入，不伪造核心协议结果。 */
#include "mp_stack.h"
#include <assert.h>
#include <stdio.h>
static MpStack stack;
static void run(unsigned ms){while(ms--)mp_stack_tick(&stack);}
int main(void){
  int rc=mp_stack_init(&stack,1790000000);if(rc){printf("init=%d\n",rc);return 1;}
  run(1100);assert(mp_stack_online(&stack,1));assert(mp_stack_online(&stack,2));
  assert(mp_od_read(&stack.nodes[2].od,0x3120,1)==9700);
  assert(mp_od_read(&stack.nodes[2].od,0x3220,3)==3670);
  mp_stack_nmt(&stack,1,CO_NMT_ENTER_STOPPED);run(600);
  assert(!mp_stack_online(&stack,1)&&mp_stack_online(&stack,2));
  mp_stack_nmt(&stack,1,CO_NMT_ENTER_OPERATIONAL);run(600);assert(mp_stack_online(&stack,1));
  CO_SDOclient_t *cli=stack.nodes[2].co->SDOclient;
  assert(CO_SDOclient_setup(cli,0x601,0x581,1)==CO_SDO_RT_ok_communicationEnd);
  assert(CO_SDOclientUploadInitiate(cli,0x1017,0,1000,false)==CO_SDO_RT_ok_communicationEnd);
  CO_SDO_return_t ret=CO_SDO_RT_waitingResponse;CO_SDO_abortCode_t abort=0;
  for(unsigned i=0;i<1100&&ret>0;i++){ret=CO_SDOclientUpload(cli,1000,false,&abort,NULL,NULL,NULL);run(1);}
  assert(ret==0&&abort==0);uint8_t data[4]={0};assert(CO_SDOclientUploadBufRead(cli,data,4)==2);assert(data[0]==0xf4&&data[1]==1);
  CO_errorReport(stack.nodes[0].co->em,CO_EM_GENERIC_ERROR,CO_EMC_GENERIC,123);run(50);assert(stack.emcy[0]!=0);
  CO_errorReset(stack.nodes[0].co->em,CO_EM_GENERIC_ERROR,0);run(50);assert(stack.emcy[0]==0);
  for(unsigned node=1;node<=2;node++) {mp_stack_enable(&stack,node,false);run(1600);assert(!mp_stack_online(&stack,node));assert(mp_stack_online(&stack,3-node));mp_stack_enable(&stack,node,true);run(600);assert(mp_stack_online(&stack,node));}
  mp_stack_nmt(&stack,2,CO_NMT_RESET_COMMUNICATION);run(600);assert(stack.resets[1]==1&&mp_stack_online(&stack,2));
  assert(mp_stack_restart(&stack,3)==0);run(600);assert(mp_stack_online(&stack,1)&&mp_stack_online(&stack,2));
  mp_bus_set_online(false);run(1700);assert(!mp_stack_online(&stack,1)&&!mp_stack_online(&stack,2));
  mp_bus_set_online(true);run(700);assert(mp_stack_online(&stack,1)&&mp_stack_online(&stack,2));
  printf("{\"protocol\":\"CANopenNode\",\"checks\":12,\"frames\":%u,\"dropped\":%u,\"allocated_cumulative\":%u}\n",mp_bus_frames(),mp_bus_dropped(),stack.allocated);
  mp_stack_close(&stack);return 0;
}
