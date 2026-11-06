/* 离线诊断：真实Gateway/Router/栈，仅CAN输入为人工边界样本。 */
#define main original_simulator_main
#include "../dual_can/tests/simulator.c"
#undef main
static unsigned points,valid_points,expected_value,mode_now;
static void take_all(unsigned now){
 MpFrame f;while(mp_router_take(&gateway.router,&f,now)){
  if(f.stream==MP_PPG){
   for(unsigned k=0;k<f.count;k++){
    if(mode_now==1 && expected_value==25)expected_value++;
    assert(f.values[k]==(int32_t)expected_value);
    unsigned sample_tick=1000+20*expected_value++;
    assert(f.timestamp-(f.count-1-k)*20u==1792713600000ULL+sample_tick);
   }
   points+=f.count;if(f.valid)valid_points+=f.count;
  }
  mp_router_ack(&gateway.router,&f,true);
 }
}
static void quality(unsigned flags){uint32_t q[2]={flags,1};inject(0,mp_pdo_id(1,4),8,(uint8_t*)q);}
static void run_case(unsigned mode){
 memset(&gateway,0,sizeof gateway);points=valid_points=expected_value=0;mode_now=mode;assert(!b4_gateway_init(&gateway));mp_router_online(&gateway.router,true);
 unsigned input=0;
 for(unsigned now=0;now<3150;now++){
  g_uptime_ms=now;if(now%1000==0)b4_gateway_sync(&gateway,1792713600u+now/1000,now);
  b4_gateway_tick(&gateway,now);
  if(now%500==0){uint8_t hb=5;inject(0,0x701,1,&hb);}
  if(now%1000==0){uint32_t anchor[2]={1792713600u+now/1000,now};inject(0,mp_pdo_id(1,3),8,(uint8_t*)anchor);quality(7);}
  if(now>=1000 && now<3000 && now%20==0){
   unsigned n=(now-1000)/20;
   if(mode==2 && n==25)quality(6);
   if(mode==2 && n==50)quality(7);
   if(!(mode==1 && n==25)){int32_t sample[2]={(int32_t)n,(int32_t)now};inject(0,mp_pdo_id(1,0),8,(uint8_t*)sample);input++;}
  }
  b4_bus_poll();take_all(now);
 }
 unsigned discarded=gateway.flow_discarded[0][0],tail=gateway.segments[0].wave[0].count;
 assert(input==points+discarded+tail);
 if(mode==0)assert(input==100 && points==100 && discarded==0 && tail==0);
 if(mode==1)assert(input==99 && points==99 && valid_points==99 && discarded==0 && tail==0 && gateway.flow_gaps[0][0]==1);
 if(mode==2)assert(input==100 && points==100 && valid_points==75 && discarded==0 && tail==0 && gateway.flow_quality[0][0]==2);
 printf("{\"mode\":%u,\"input_samples\":%u,\"published_samples\":%u,\"discarded_samples\":%u,\"tail_samples\":%u,\"gap_events\":%u,\"quality_events\":%u,\"hardware\":false}\n",mode,input,points,discarded,tail,gateway.flow_gaps[0][0],gateway.flow_quality[0][0]);
 b4_gateway_close(&gateway);
}
int main(void){for(unsigned i=0;i<3;i++)run_case(i);return 0;}
