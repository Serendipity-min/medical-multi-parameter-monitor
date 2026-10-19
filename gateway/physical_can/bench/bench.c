#include "bench.h"
#include <stdio.h>
#include <string.h>
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
BenchStats bench_stats;
static uint32_t report_at;
static const uint16_t ids[8]={0x701,0x703,0x181,0x381,0x481,0x681,0x281,0x100};

void bench_observe_registers(uint32_t pclk,uint32_t btr,uint32_t esr,uint32_t tsr,
                             uint32_t overflow,uint32_t bad) {
    bench_stats.pclk=pclk;bench_stats.btr=btr;bench_stats.esr=esr;bench_stats.tsr=tsr;
    bench_stats.rx_overflow=overflow;bench_stats.bad_frame=bad;
}
void bench_observe_tx(const MpCanFrame *f,bool ack) {
    if(ack) bench_stats.tx_acked++;else bench_stats.tx_started++;
    if(f->ident==0 && f->dlc==2 && f->data[0]==1 && f->data[1]==0) {
        if(ack) bench_stats.nmt_txok++;else bench_stats.nmt_started++;
    }
}
void bench_observe_rx(const MpCanFrame *f) {
    /* 禁止把不应存在的B或已禁用281当作正常验收数据；主循环锁止且保留证据。 */
    if(f->ident==0x702 || f->ident==0x182 || f->ident==0x282 || f->ident==0x382
       || f->ident==0x482 || f->ident==0x682) bench_stats.fault=4;
    if(f->ident==0x281) bench_stats.fault=5;
    for(unsigned i=0;i<8;i++) if(f->ident==ids[i]) {
        BenchRx *r=&bench_stats.rx[i];
        if(r->count) {
            uint32_t dt=g_uptime_ms-r->last;
            if(dt<r->minimum) r->minimum=dt;
            if(dt>r->maximum) r->maximum=dt;
        } else {r->first=g_uptime_ms;r->minimum=0xffffffffu;}
        r->count++;r->last=g_uptime_ms;r->dlc=f->dlc;memcpy(r->data,f->data,8);
    }
    if(f->ident==0x701 && f->dlc==1) {
        if(f->data[0]==0) bench_stats.bootups++;
        if(f->data[0]==5) bench_stats.hb_op++;
        if(f->data[0]==127) bench_stats.hb_preop++;
    }
}
void bench_init(void) {
    memset(&bench_stats,0,sizeof(bench_stats));bench_stats.magic=0x48324342u;
    mp_bus_reset();mp_adapter_init(&adapter);mp_router_init(&router);
    /* 本地消费Router产物，不是联网。仅在显式T注入测试时钟后Adapter才可能产帧。 */
    mp_router_online(&router,true);report_at=0;
    /* CAN控制器先就绪但不运行协议/发送，独立检查时不会因主动发帧无ACK而刷屏。 */
    if(!mp_bxcan_init()) bench_stats.fault=1;
    console("CAN_ONLY_BENCH OFFLINE_NO_CONFIG CAN_INIT_PASSIVE NMT_NOT_QUEUED TIME_BLOCKED NODE_B_OFFLINE\r\n");
}
void bench_command(int c) {
    if(bench_stats.fault) return; /* 故障后不能靠串口命令绕过现场停止门禁。 */
    if((c=='S' && !bench_stats.armed) || (c=='G' && bench_stats.armed)) {
        int rc=physical_gateway_open(&stack,bench_stats.armed!=0);
        if(rc) {bench_stats.fault=2;physical_invalidate();return;}
        /* 被动检查可能持续数分钟；首次启动不能从0追赶并伪造调度积压。 */
        stack.milliseconds=g_uptime_ms;
        bench_stats.armed=1;bench_stats.test_time=0;stack.epoch=0;
        mp_adapter_init(&adapter);mp_router_init(&router);mp_router_online(&router,true);
        console("CAN_INIT READY NMT_START_QUEUED id=000 data=0100 NOT_YET_TXOK TIME_BLOCKED\r\n");
    }
    if(c=='T' && bench_stats.armed) {
        /* 只允许隔离bench显式授时；固定测试epoch绝非可信SNTP或临床时间。 */
        stack.epoch=1800000000u-stack.milliseconds/1000u;bench_stats.test_time=1;
        console("BENCH_TEST_TIME_UNTRUSTED ENABLED CAN_TIME_100 NO_CLOUD\r\n");
    }
}
static void report(void) {
    char line[256];
    (void)snprintf(line,sizeof(line),"BENCH ms=%lu armed=%lu fault=%lu PCLK1=%lu BTR=%08lx TEC=%lu REC=%lu LEC=%lu BOFF=%lu TXOK=%lu NMT_START=%lu NMT_TXOK=%lu A=%lu B=%lu time=%s\r\n",
        (unsigned long)g_uptime_ms,(unsigned long)bench_stats.armed,(unsigned long)bench_stats.fault,
        (unsigned long)bench_stats.pclk,(unsigned long)bench_stats.btr,
        (unsigned long)((bench_stats.esr>>16)&255u),(unsigned long)(bench_stats.esr>>24),
        (unsigned long)((bench_stats.esr>>4)&7u),(unsigned long)((bench_stats.esr>>2)&1u),
        (unsigned long)bench_stats.tx_acked,(unsigned long)bench_stats.nmt_started,
        (unsigned long)bench_stats.nmt_txok,(unsigned long)bench_stats.node_a_online,
        (unsigned long)bench_stats.node_b_online,bench_stats.test_time?"BENCH_TEST_TIME_UNTRUSTED":"TIME_BLOCKED");
    console(line);
    for(unsigned i=0;i<8;i++) {
        BenchRx *r=&bench_stats.rx[i];if(!r->count) continue;
        (void)snprintf(line,sizeof(line),"RX id=%03x n=%lu first=%lu last=%lu dt_min=%lu dt_max=%lu dlc=%u data=%02x%02x%02x%02x%02x%02x%02x%02x\r\n",ids[i],
            (unsigned long)r->count,(unsigned long)r->first,(unsigned long)r->last,
            (unsigned long)(r->count>1?r->minimum:0),(unsigned long)r->maximum,r->dlc,
            r->data[0],r->data[1],r->data[2],r->data[3],r->data[4],r->data[5],r->data[6],r->data[7]);console(line);
    }
    (void)snprintf(line,sizeof(line),"MIRROR epoch=%lu tick=%lu Q=%08lx gen=%lu fresh=%02lx values=%lu,%lu,%lu,%lu wave=%ld/%lu HBboot=%lu HBop=%lu\r\n",
        (unsigned long)bench_stats.mirror_epoch,(unsigned long)bench_stats.mirror_tick,
        (unsigned long)bench_stats.quality,(unsigned long)bench_stats.generation,(unsigned long)bench_stats.fresh_mask,
        (unsigned long)bench_stats.scalar[0],(unsigned long)bench_stats.scalar[1],(unsigned long)bench_stats.scalar[2],(unsigned long)bench_stats.scalar[3],
        (long)bench_stats.wave_value,(unsigned long)bench_stats.wave_tick,(unsigned long)bench_stats.bootups,(unsigned long)bench_stats.hb_op);console(line);
    (void)snprintf(line,sizeof(line),"MODEL frames=%lu invalid=%lu seq=%lu session=%lu over=%lu bad=%lu uart_drop=%lu lag=%lu stream=%lu valid=%lu synthetic=%lu stamp=%08lx%08lx router_drop=%lu NODE_B_OFFLINE\r\n",
        (unsigned long)bench_stats.model_frames,(unsigned long)bench_stats.invalid_frames,(unsigned long)bench_stats.last_seq,
        (unsigned long)bench_stats.last_boot,(unsigned long)bench_stats.rx_overflow,(unsigned long)bench_stats.bad_frame,
        (unsigned long)bench_stats.uart_dropped,(unsigned long)bench_stats.loop_lag,
        (unsigned long)bench_stats.last_stream,(unsigned long)bench_stats.last_valid,(unsigned long)bench_stats.last_synthetic,
        (unsigned long)bench_stats.last_stamp_high,(unsigned long)bench_stats.last_stamp_low,(unsigned long)bench_stats.router_dropped);console(line);
}
void bench_step(void) {
    bench_stats.uptime=g_uptime_ms;
    if(bench_stats.armed && !bench_stats.fault) {
        unsigned budget=8;
        while(stack.milliseconds!=g_uptime_ms && budget--) {
            mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router);
            /* 每轮有界消费本地模型产物；success只表示本地消费，不宣称MQTT PUBACK。 */
            MpFrame f;
            while(mp_router_take(&router,&f,stack.milliseconds)) {
                bench_stats.model_frames++;if(!f.valid) bench_stats.invalid_frames++;
                bench_stats.last_stream=f.stream;bench_stats.last_seq=f.seq;bench_stats.last_boot=f.boot;
                bench_stats.last_valid=f.valid;bench_stats.last_synthetic=f.synthetic;
                bench_stats.last_stamp_low=(uint32_t)f.timestamp;bench_stats.last_stamp_high=(uint32_t)(f.timestamp>>32);
                mp_router_ack(&router,&f,true);
            }
            if(!physical_link_ready) {bench_stats.fault=3;break;}
        }
        if((uint32_t)(g_uptime_ms-stack.milliseconds)>bench_stats.loop_lag)
            bench_stats.loop_lag=g_uptime_ms-stack.milliseconds;
        MpOD *od=&stack.nodes[2].od;
        bench_stats.node_a_online=mp_stack_online(&stack,1);bench_stats.node_b_online=mp_stack_online(&stack,2);
        bench_stats.mirror_epoch=mp_od_read(od,0x3100,1);bench_stats.mirror_tick=mp_od_read(od,0x3100,2);
        bench_stats.quality=mp_od_read(od,0x3130,1);bench_stats.generation=mp_od_read(od,0x3130,2);
        for(unsigned i=0;i<4;i++) bench_stats.scalar[i]=mp_od_read(od,0x3120,i+1);
        bench_stats.wave_value=mp_od_read(od,0x3110,1);bench_stats.wave_tick=mp_od_read(od,0x3110,2);
        bench_stats.fresh_mask=0;
        bench_stats.router_dropped=router.dropped;
        for(unsigned i=0;i<5;i++) if(physical_fresh(1,i,stack.milliseconds)) bench_stats.fresh_mask|=1u<<i;
    } else if(!bench_stats.fault) mp_bus_hardware_poll();
    if(bench_stats.fault) {physical_invalidate();bench_stats.node_a_online=bench_stats.node_b_online=0;}
    if((uint32_t)(g_uptime_ms-report_at)>=1000u) {report_at=g_uptime_ms;report();}
}
