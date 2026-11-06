/* 调用实际Router/出口推进器；传输替身只控制发送机会及在途状态。 */
#ifndef P1_EGRESS_HEADER
#define P1_EGRESS_HEADER "egress.h"
#endif
#include P1_EGRESS_HEADER
#include "../data_model/roles.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

volatile uint32_t g_uptime_ms;
static const uint64_t epoch=1800000000000ULL;
static unsigned full,admissible=1,starts;
static MpFrame last;
int b5_network_stopped(void){return 0;}
uint64_t gateway_epoch_milliseconds(void){return epoch+g_uptime_ms;}
int gateway_mqtt_progress(void){return GW_COMPLETE;}
int gateway_mqtt_admit(void){return admissible?GW_COMPLETE:GW_DEFERRED;}
int gateway_mqtt_slots_full(void){return full;}
int gateway_mqtt_ticket_result(uint16_t id){(void)id;return GW_PENDING;}
uint16_t gateway_mqtt_ticket(void){return 9;}
bool unified_audio_send_due(void){return false;}
void unified_audio_step(bool allowed){(void)allowed;}
int gateway_audio_pending(void){return 0;}
int gateway_mqtt_begin(const MpFrame *f){last=*f;starts++;return f->rate&&!f->replay?GW_COMPLETE:GW_PENDING;}

static MpFrame frame(unsigned stream,unsigned seq,uint32_t at){
    MpFrame f={0};f.node=mp_role_node((MpStream)stream);f.stream=stream;
    f.timestamp=epoch+at;f.seq=seq;f.epoch=123;f.boot=456;
    f.rate=stream==MP_ECG?250:stream==MP_RESP||stream==MP_PPG?50:0;
    f.count=f.rate?50:1;f.valid=seq%2!=0;f.synthetic=true;
    for(unsigned i=0;i<f.count;i++)f.values[i]=(int32_t)(seq*1000+i)-2500;
    return f;
}
static void history(MpRouter *r){
    MpFrame f=frame(MP_PPG,500,0);mp_router_put(r,&f);mp_router_online(r,true);
    r->ready_for_replay=true;r->live_credit=8;
}
int main(int argc,char **argv){
    assert(argc==2);MpRouter r;mp_router_init(&r);MpFrame out;
    g_uptime_ms=10000;
    if(!strcmp(argv[1],"fifo")){
        mp_router_online(&r,true);
        const unsigned streams[]={MP_ECG,MP_RESP,MP_PPG};
        for(unsigned k=0;k<3;k++)for(unsigned i=1;i<=4;i++){
            MpFrame f=frame(streams[k],i,9000+i);mp_router_put(&r,&f);
        }
        assert(r.ln==12 && r.cn==0 && r.live_replaced==0);
        for(unsigned k=0;k<3;k++)for(unsigned i=1;i<=4;i++){
            assert(mp_router_take_egress(&r,&out,10000,epoch+10000,false));
            MpFrame expected=frame(streams[k],i,9000+i);
            assert(!memcmp(&out,&expected,sizeof(out)));
        }
        puts("ALL_THREE_WAVE_FIFO_VALUES_SEQUENCE_TIME_QUALITY_UNCHANGED");
    }else if(!strcmp(argv[1],"history")){
        history(&r);unsigned replay=0;
        for(unsigned i=0;i<25;i++){
            g_uptime_ms=10000+i*100;MpFrame f=frame(MP_ECG,i+1,g_uptime_ms);mp_router_put(&r,&f);
            assert(mp_router_take_egress(&r,&out,g_uptime_ms,epoch+g_uptime_ms,false));
            if(out.replay){MpFrame expected=frame(MP_PPG,500,0);expected.replay=true;assert(!memcmp(&out,&expected,sizeof(out)));replay++;}
            mp_router_ack(&r,&out,true);
        }
        assert(replay==1 && r.replayed==1 && !r.live_overflow && !r.expired);
        puts("HISTORY_SERVICED_DURING_CONTINUOUS_LIVE_LOAD");
    }else if(!strcmp(argv[1],"deadline")){
        const uint32_t ages[]={2499,2500,4999,5001};
        for(unsigned k=0;k<4;k++){
            mp_router_init(&r);history(&r);MpFrame f=frame(MP_ECG,1,10000-ages[k]);mp_router_put(&r,&f);
            assert(mp_router_take_egress(&r,&out,10000,epoch+10000,false));
            assert(out.replay==(ages[k]<2500));
            if(out.replay){
                /* 取实板MQTT发送最大159ms的延迟，原实时帧仍须保持原样且不过期。 */
                assert(mp_router_take_egress(&r,&out,10159,epoch+10159,true));
                assert(!out.replay && out.timestamp==f.timestamp && !r.expired && !r.live_overflow);
            }
        }
        mp_router_init(&r);history(&r);
        for(unsigned i=0;i<MP_LIVE_CAPACITY-2;i++){MpFrame f=frame(MP_ECG,i+1,10000);mp_router_put(&r,&f);}
        assert(mp_router_take_egress(&r,&out,10000,epoch+10000,false) && !out.replay);
        mp_router_init(&r);history(&r);MpFrame f=frame(MP_ECG,1,10000);mp_router_put(&r,&f);
        assert(mp_router_take_egress(&r,&out,10000,epoch+10000,true) && !out.replay);
        puts("AGE_CAPACITY_AND_QOS1_BACKPRESSURE_BLOCK_HISTORY");
    }else if(!strcmp(argv[1],"publisher")){
        B5Publisher s={0};history(&r);MpFrame f=frame(MP_ECG,1,10000);mp_router_put(&r,&f);
        admissible=0;assert(b5_egress_step(&r,&s,true) && r.ln==1 && r.cn==1 && starts==0);
        admissible=1;full=1;assert(b5_egress_step(&r,&s,true) && starts==1 && !last.replay && r.cn==1);
        full=0;f=frame(MP_RESP,1,10000);mp_router_put(&r,&f);
        s.tickets[0]=1;s.inflight[0]=frame(MP_HR,1,7000);
        assert(b5_egress_step(&r,&s,true) && starts==2 && !last.replay && r.cn==1);
        assert(b5_egress_step(&r,&s,true) && starts==2 && r.cn==1);
        s.tickets[0]=0;
        assert(b5_egress_step(&r,&s,true) && starts==3 && last.replay && r.cn==0);
        puts("PUBLISH_OPPORTUNITY_AND_INFLIGHT_DEADLINE_PRESERVED");
    }else return 2;
    return 0;
}
