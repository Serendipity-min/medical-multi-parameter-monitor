/* 仅Host DLL：真实Router/推进器/coreMQTT，TLS套接字由loopback夹具提供。 */
#include "egress.h"
#include "gateway_config.h"
#include "esp_io_metrics.h"
#include <string.h>
#include <stdio.h>
#define API __declspec(dllexport)
const GatewayConfig gateway_test_config={GATEWAY_CONFIG_MAGIC,1700000000u,"synthetic-wifi","synthetic-wifi-password",
    "localhost","b5-gateway","synthetic-b5-local-only-password","b5-c-isolated"};
volatile uint32_t g_uptime_ms;
typedef int (*Io)(void *,int,int);
typedef uint32_t (*Clock)(void);
static Io writer,reader;static Clock clock_ms;static MpRouter router;static B5Publisher publisher;
static char time_response[48];
void platform_poll(void){g_uptime_ms=clock_ms();}
void mp_model_poll(void){platform_poll();}
void console(const char *s){(void)s;}
int b5_network_stopped(void){return 0;}
int platform_at_synchronized(void){return 1;}
int platform_at_unsynced(void){return 0;}
uint32_t platform_send_reserve(unsigned bytes){return ((bytes+24u)*10000u+115199u)/115200u+2100u;}
int platform_send_admissible(unsigned bytes,uint32_t budget){return budget>=platform_send_reserve(bytes);}
void platform_tx_context(unsigned qos,unsigned stream,uint32_t seq,unsigned pending,uint32_t age,uint32_t budget){(void)qos;(void)stream;(void)seq;(void)pending;(void)age;(void)budget;}
int at_command(const char *s,uint32_t timeout){(void)s;(void)timeout;return 1;}
const char *at_response(void){return time_response;}
void delay_ms(uint32_t ms){(void)ms;platform_poll();}
void esp_mqtt_reset(void){}
int esp_mqtt_send(const unsigned char *p,int n,uint32_t timeout){return writer((void *)p,n,(int)timeout);}
int esp_mqtt_recv(unsigned char *p,int n,uint32_t timeout){return reader(p,n,(int)timeout);}
API int bridge_open(Io write_fn,Io read_fn,Clock get_ms,uint32_t epoch){
    writer=write_fn;reader=read_fn;clock_ms=get_ms;platform_poll();
    (void)snprintf(time_response,sizeof(time_response),"+SYSTIMESTAMP:%lu",(unsigned long)epoch);
    mp_router_init(&router);memset(&publisher,0,sizeof(publisher));
    if(!gateway_network_open())return 0;
    MpFrame will={0};will.node=3;will.stream=MP_GATEWAY_STATUS;will.synthetic=true;will.timestamp=(uint64_t)epoch*1000;will.epoch=1;will.boot=1;
    if(!gateway_mqtt_open(&will))return 0;
    mp_router_online(&router,true);return 1;
}
API void bridge_put(uint32_t stream,uint32_t seq,uint64_t utc,uint32_t epoch,uint32_t boot,uint32_t valid,
                    uint32_t rate,uint32_t count,const int32_t *values){
    MpFrame f={0};f.node=stream==MP_GATEWAY_STATUS?3:2;f.stream=(uint8_t)stream;f.seq=seq;f.timestamp=utc;f.epoch=epoch;f.boot=boot;
    f.valid=valid!=0;f.synthetic=true;f.rate=(uint16_t)rate;f.count=(uint16_t)count;
    if(count>MP_FRAME_MAX_SAMPLES)return;
    if(count)memcpy(f.values,values,count*sizeof(int32_t));
    mp_router_put(&router,&f);
}
API int bridge_step(void){platform_poll();return b5_egress_step(&router,&publisher,true);}
API unsigned bridge_queued(void){return router.ln+(unsigned)publisher.pending;}
API unsigned bridge_error(void){return router.dropped+router.live_overflow+router.live_replaced+router.expired+router.cn+publisher.failed;}
API unsigned bridge_high_water(void){return router.high_water;}
API int bridge_temp_read(B5TempEntry *out){
    if(router.temp_reported==router.temp_written)return 0;
    *out=router.temp_entry[router.temp_reported++%8];return 1;
}
API unsigned bridge_trace_lost(void){return router.temp_trace_lost;}
API void bridge_status(uint32_t epoch,uint32_t boot,uint32_t seq,uint64_t utc){
    MpFrame f={0};f.synthetic=true;f.valid=true;f.count=1;f.epoch=epoch;f.boot=boot;f.seq=seq;f.timestamp=utc;
    f.node=3;f.stream=MP_GATEWAY_STATUS;mp_router_put(&router,&f);
    f.node=2;f.stream=MP_NODE_STATUS;mp_router_put(&router,&f);
}
API void bridge_close(void){gateway_network_close();}
