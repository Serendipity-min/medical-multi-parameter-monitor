/* 第二阶段：CANopen Adapter → Canonical Model → Router → MQTT/离线缓存。 */
#include "gateway_transport.h"
#include "mp_adapter.h"
#include <stdio.h>
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static uint32_t serviced,diagnostic_at;
static int disconnect_requested;
extern int mp_bxcan_init(void);
static void service(void){
  mp_bus_poll();
  /* CAN 栈在主线程运行，UART 中断只入环形缓冲；限制单次追赶，避免网络饥饿。 */
  unsigned budget=8;
  while(serviced!=g_uptime_ms&&budget--){serviced++;mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router);}
  int c=console_char();
  if(c=='D')disconnect_requested=1;
  if(c=='A'||c=='B'){
    unsigned node=c=='A'?1:2;mp_stack_enable(&stack,node,!stack.nodes[node-1].port.enabled);
    console(stack.nodes[node-1].port.enabled?"GW NODE_TEST_ENABLED\r\n":"GW NODE_TEST_DISABLED\r\n");
  }
  if(c=='C'){static bool online=true;online=!online;mp_bus_set_online(online);console(online?"GW CAN_TEST_RECOVERED\r\n":"GW CAN_TEST_DISCONNECTED\r\n");}
  if(c=='R'){(void)mp_stack_restart(&stack,2);console("GW NODE_TEST_RESTARTED\r\n");}
  if(c=='G'){(void)mp_stack_restart(&stack,3);console("GW GATEWAY_TEST_RESTARTED\r\n");}
  if(c=='E'){
    static bool fault;fault=!fault;
    if(fault)CO_errorReport(stack.nodes[0].co->em,CO_EM_GENERIC_ERROR,CO_EMC_GENERIC,0);
    else CO_errorReset(stack.nodes[0].co->em,CO_EM_GENERIC_ERROR,0);
    console("GW EMCY_TEST_CHANGED\r\n");
  }
}
int main(void){
  platform_init();console("GW BOOT CANOPENNODE BXCAN_LOOPBACK SYNTHETIC\r\n");
  if(!gateway_config_valid()){console("GW CONFIG_REQUIRED\r\n");while(1){}}
  int rc=mp_stack_init(&stack,0);
  int hardware=rc?0:mp_bxcan_init();
  if(rc||!hardware){char line[80];(void)snprintf(line,sizeof(line),"GW CAN_INIT_FAIL code=%d hardware=%d\r\n",rc,hardware);console(line);while(1){}}
  serviced=g_uptime_ms;mp_adapter_init(&adapter);mp_router_init(&router);platform_set_poll(service);
  while(1){
    mp_router_online(&router,false);
    if(!gateway_network_open()){delay_ms(3000);continue;}
    if(!stack.epoch)stack.epoch=gateway_epoch()-stack.milliseconds/1000;
    MpFrame will={0};will.node=3;will.stream=MP_GATEWAY_STATUS;will.timestamp=(uint64_t)gateway_epoch()*1000;
    will.seq=0xffffffffU;will.epoch=stack.epoch;will.boot=stack.nodes[2].boot<<16;will.synthetic=true;
    if(!gateway_mqtt_open(&will)){delay_ms(3000);continue;}
    mp_router_online(&router,true);
    adapter.status_tick=stack.milliseconds-5000U; /* 重连立即生成当前状态，再允许历史补传。 */
    while(1){
      platform_poll();
      if(disconnect_requested){disconnect_requested=0;mp_router_online(&router,false);(void)at_command("AT+CWQAP",3000);console("GW WIFI_TEST_DISCONNECTED\r\n");delay_ms(30000);break;}
      MpFrame f;
      if(mp_router_take(&router,&f,g_uptime_ms)){
        bool ok=gateway_mqtt_publish(&f);mp_router_ack(&router,&f,ok);if(!ok)break;
      }else if(!gateway_mqtt_yield())break;
      if(g_uptime_ms-diagnostic_at>=5000){
        char line[160];diagnostic_at=g_uptime_ms;
        (void)snprintf(line,sizeof(line),"GW METRICS can=%lu drop=%lu cache=%u lost=%lu replay=%lu nodes=%d%d\r\n",(unsigned long)mp_bus_frames(),(unsigned long)mp_bus_dropped(),router.cn,(unsigned long)router.dropped,(unsigned long)router.replayed,mp_stack_online(&stack,1),mp_stack_online(&stack,2));console(line);
      }
    }
    mp_router_online(&router,false);console("GW RECONNECT\r\n");gateway_network_close();delay_ms(2000);
  }
}
