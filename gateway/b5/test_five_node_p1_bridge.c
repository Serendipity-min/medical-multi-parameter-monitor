/* 离线原件回放调用实际Router，导出接口仅用于Host DLL。 */
#include "../storage/router.h"
#include <stddef.h>
volatile uint32_t g_uptime_ms;
static uint64_t utc;
static MpRouter router;
uint64_t gateway_epoch_milliseconds(void){return utc;}
#define API __declspec(dllexport)
API unsigned p1_frame_bytes(void){return sizeof(MpFrame);}
API void p1_init(void){mp_router_init(&router);mp_router_online(&router,true);}
API void p1_put(const MpFrame *f,uint32_t now,uint64_t current){g_uptime_ms=now;utc=current;mp_router_put(&router,f);}
API int p1_take(MpFrame *f,uint32_t now,uint64_t current,int pending){
    g_uptime_ms=now;utc=current;int ok=mp_router_take_egress(&router,f,now,current,pending!=0);
    if(ok)mp_router_ack(&router,f,true);
    return ok;
}
API unsigned p1_counter(unsigned i){
    const unsigned counters[]={router.ln,router.cn,router.live_replaced,router.live_overflow,router.dropped,router.expired,router.replayed};
    return counters[i];
}
