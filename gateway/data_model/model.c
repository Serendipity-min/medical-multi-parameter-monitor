/* 统一帧只存固定点整数；MQTT 边界统一缩放，避免不同入口重复拼装业务字段。 */
#include "model.h"
#include <stdio.h>
#include <stdarg.h>
static const char *names[]={"ppg","spo2","pr","nibp","ecg","hr","resp","rr","temp","status","fault","status"};
static const char *units[]={"relative","%","bpm","mmHg","mV","bpm","relative","breaths/min","degC","state","code","state"};
static const int scales[]={1000000,100,100,10,1000,100,1000000,100,100,1,1,1};
__attribute__((weak)) void mp_model_poll(void) { }
const char *mp_stream_name(MpStream stream){return stream<MP_STREAMS?names[stream]:"invalid";}
static int append(char **out,size_t *left,const char *fmt,...){
  va_list ap;va_start(ap,fmt);int n=vsnprintf(*out,*left,fmt,ap);va_end(ap);
  if(n<0||(size_t)n>=*left)return 0;
  *out+=n;*left-=(size_t)n;return 1;
}
static int number(char **out,size_t *left,int32_t value,int scale){
  /* 放大到 int64 后取绝对值，正确处理 INT32_MIN；不依赖 nano printf 浮点扩展。 */
  uint32_t mag=value<0?(uint32_t)(-(int64_t)value):(uint32_t)value;
  unsigned decimals=scale==1000000?6:scale==1000?3:scale==100?2:1;
  return append(out,left,"%s%lu.%0*lu",value<0?"-":"",(unsigned long)(mag/scale),decimals,(unsigned long)(mag%scale));
}
int mp_json(const MpFrame *f,char *out,size_t size){
  if(!f||f->stream>=MP_STREAMS||f->count>250||!size)return 0;
  char *p=out;size_t left=size;unsigned k=f->stream;
  const char *valid=f->valid?"VALID":(k==MP_NODE_STATUS||k==MP_GATEWAY_STATUS)?"OFFLINE":"INVALID";
  if(!append(&p,&left,"{\"timestamp\":%lu%03lu,\"seq\":%lu,\"session_id\":\"can-%lu-%lu\",\"validity\":\"%s\",\"source\":\"%s\",\"synthetic\":%s,\"unit\":\"%s\",\"value\":",
    (unsigned long)(f->timestamp/1000),(unsigned long)(f->timestamp%1000),(unsigned long)f->seq,(unsigned long)f->epoch,(unsigned long)f->boot,valid,f->replay?"REPLAY":f->synthetic?"MOCK":"LIVE",f->synthetic?"true":"false",units[k]))return 0;
  if(k==MP_NODE_STATUS||k==MP_GATEWAY_STATUS){if(!append(&p,&left,"\"%s\"",f->valid?"ONLINE":"OFFLINE"))return 0;}
  else if(k==MP_FAULT){if(!append(&p,&left,"\"EMCY-%04lX\"",(unsigned long)(uint32_t)f->values[0]))return 0;}
  else if(f->rate){
    if(!append(&p,&left,"null,\"sample_rate\":%u,\"samples\":[",f->rate))return 0;
    for(unsigned i=0;i<f->count;i++){
      /* 大批次格式化也需让出时间给 CAN，不能等到串口发送时才处理 RPDO。 */
      mp_model_poll();
      if(i&&!append(&p,&left,","))return 0;
      if(!number(&p,&left,f->values[i],scales[k]))return 0;
    }
    if(!append(&p,&left,"]"))return 0;
  }else if(!f->valid){if(!append(&p,&left,"null"))return 0;}
  else if(k==MP_NIBP){if(!append(&p,&left,"[")||!number(&p,&left,f->values[0],10)||!append(&p,&left,",")||!number(&p,&left,f->values[1],10)||!append(&p,&left,"]"))return 0;}
  else if(!number(&p,&left,f->values[0],scales[k]))return 0;
  return append(&p,&left,"}")?(int)(p-out):0;
}
int mp_topic(const MpFrame *f,char *out,size_t size){
  int n;
  if(f->stream==MP_GATEWAY_STATUS)n=snprintf(out,size,"mpm/v1/GW-C-001/status");
  else if(f->stream==MP_NODE_STATUS||(f->stream==MP_FAULT&&!f->replay))n=snprintf(out,size,"mpm/v1/GW-C-001/NODE-%c/%s",f->node==1?'A':'B',f->stream==MP_FAULT?"event":"status");
  else n=snprintf(out,size,"mpm/v1/GW-C-001/NODE-%c/%s/%s",f->node==1?'A':'B',f->replay?"replay":"telemetry",names[f->stream]);
  return n>0&&(size_t)n<size?n:0;
}
