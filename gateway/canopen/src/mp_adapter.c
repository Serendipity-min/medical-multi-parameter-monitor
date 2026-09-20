/* Adapter 不拼 MQTT JSON：只从 Gateway RPDO 映射区读取并产出统一帧。 */
#include "mp_adapter.h"
#include <string.h>
void mp_adapter_init(MpAdapter *a){memset(a,0,sizeof(*a));a->quality[0]=a->quality[1]=0x80000000U;}
static MpFrame frame(MpAdapter *a,MpStack *s,unsigned node,MpStream stream,uint64_t timestamp){
  MpFrame f={0};f.node=node;f.stream=stream;f.timestamp=timestamp;f.epoch=s->epoch;
  f.boot=(s->nodes[2].boot<<16)|(node<=2?(a->boot[node-1]&65535U):0);f.seq=++a->seq[node-1][stream];
  f.synthetic=node==3?true:(a->quality[node-1]&0x80000000U)!=0;return f;
}
static uint64_t capture(MpOD *od,unsigned base,uint32_t tick){
  uint32_t epoch=mp_od_read(od,base,1),anchor=mp_od_read(od,base,2);
  return (uint64_t)epoch*1000+(uint32_t)(tick-anchor);
}
static void wave(MpAdapter *a,MpStack *s,MpRouter *r,unsigned node,unsigned channel){
  MpOD *od=&s->nodes[2].od;unsigned base=0x3000+node*0x100,index=base+0x10+channel;
  uint32_t tick=mp_od_read(od,index,2);if(!tick||tick==a->tick[node-1][channel])return;
  MpFrame *f=&a->waves[node==1?0:channel+1];unsigned rate=node==2&&channel==0?250:50;
  MpStream stream=node==1?MP_PPG:channel==0?MP_ECG:MP_RESP;
  bool valid=(a->quality[node-1]&(1U<<channel))!=0;
  /* 采样时钟不连续、有效性变化或节点重启时丢弃未完成的小批次，不能拼接伪连续波形。 */
  if((uint32_t)(tick-a->tick[node-1][channel])!=1000/rate||f->valid!=valid)f->count=0;
  a->tick[node-1][channel]=tick;
  if(!f->count){*f=frame(a,s,node,stream,capture(od,base,tick));f->rate=rate;f->valid=valid;}
  f->values[f->count++]=(int32_t)mp_od_read(od,index,1);
  if(f->count==rate){
    /* 云端既有波形轴以批次末样本为 timestamp，按采样率向前还原每一点。 */
    f->timestamp=capture(od,base,tick);mp_router_put(r,f);f->count=0;
  }
}
void mp_adapter_poll(MpAdapter *a,MpStack *s,MpRouter *r){
  if(!s->epoch)return; /* 未获得可信时间前不向云端伪造时间戳。 */
  uint64_t now=(uint64_t)s->epoch*1000+s->milliseconds;MpOD *od=&s->nodes[2].od;
  for(unsigned node=1;node<=2;node++){
    unsigned base=0x3000+node*0x100;uint32_t boot=mp_od_read(od,base+0x30,2);
    bool online=mp_stack_online(s,node);
    /* Gateway 通信复位会清空镜像；未重新收到质量PDO时保留已知来源，不能把零值误报为LIVE。 */
    if(boot)a->quality[node-1]=mp_od_read(od,base+0x30,1);
    else a->quality[node-1]&=0x80000000U;
    if(boot!=a->boot[node-1]){
      a->boot[node-1]=boot;memset(a->seq[node-1],0,sizeof(a->seq[0]));a->anchor[node-1]=0;
      a->tick[node-1][0]=a->tick[node-1][1]=0;
      a->waves[node==1?0:1].count=0;if(node==2)a->waves[2].count=0;
    }
    if(online!=a->online[node-1] || s->milliseconds-a->status_tick>=5000){
      MpFrame f=frame(a,s,node,MP_NODE_STATUS,now);f.valid=online;mp_router_put(r,&f);a->online[node-1]=online;
    }
    if(s->emcy[node-1]!=a->fault[node-1]){
      a->fault[node-1]=s->emcy[node-1];MpFrame f=frame(a,s,node,MP_FAULT,now);f.valid=true;f.values[0]=(int32_t)s->emcy[node-1];mp_router_put(r,&f);
    }
    if(!online||!boot||!mp_od_read(od,base,1))continue;
    wave(a,s,r,node,0);if(node==2)wave(a,s,r,node,1);
    uint32_t anchor=mp_od_read(od,base,2);
    if(anchor==a->anchor[node-1])continue;
    a->anchor[node-1]=anchor;
    /* CAN 标量仍为 1Hz；云端按 2 秒合并发送，为实时波形和补传留出串口带宽。 */
    if(s->milliseconds%2000>=1000)continue;
    const MpStream streams[2][3]={{MP_SPO2,MP_PR,MP_NIBP},{MP_HR,MP_RR,MP_TEMP}};
    for(unsigned j=0;j<3;j++){
      MpFrame f=frame(a,s,node,streams[node-1][j],capture(od,base,anchor));
      unsigned bit=node==1?j+1:(j==0?2:j==1?3:4);
      f.valid=(a->quality[node-1]&(1U<<bit))!=0;f.count=j==2&&node==1?2:1;
      f.values[0]=(int32_t)mp_od_read(od,base+0x20,j+1);
      if(f.stream==MP_TEMP)f.values[0]=(int16_t)f.values[0];
      if(f.count==2)f.values[1]=(int32_t)mp_od_read(od,base+0x20,4);
      mp_router_put(r,&f);
    }
  }
  if(s->milliseconds-a->status_tick>=5000){MpFrame f=frame(a,s,3,MP_GATEWAY_STATUS,now);f.valid=true;mp_router_put(r,&f);a->status_tick=s->milliseconds;}
}
