#ifndef MP_CAN_ONLY_BENCH_H
#define MP_CAN_ONLY_BENCH_H
#ifndef CAN_ONLY_BENCH
#error "This interface requires the isolated CAN_ONLY_BENCH target"
#endif
#include "physical.h"
#include "mp_adapter.h"

/* 全部为固定大小 RAM 观测值；不保存设备UID、配置或网络凭据。 */
typedef struct {
    uint32_t count,first,last,minimum,maximum;
    uint8_t dlc,data[8];
} BenchRx;
typedef struct {
    uint32_t magic,uptime,armed,fault,test_time,pclk,btr,esr,tsr;
    uint32_t tx_started,tx_acked,nmt_started,nmt_txok,bootups,hb_op,hb_preop;
    uint32_t rx_overflow,bad_frame,uart_dropped,loop_lag,node_a_online,node_b_online;
    uint32_t mirror_epoch,mirror_tick,quality,generation,scalar[4],wave_value,wave_tick;
    uint32_t fresh_mask,model_frames,invalid_frames,last_stream,last_seq,last_boot;
    uint32_t last_valid,last_synthetic,last_stamp_low,last_stamp_high,router_dropped;
    uint32_t rx_sw_overflow,rx_high_water,rx_depth,rx_full,rx_fifo_depth;
    uint32_t rx_isr_calls,rx_isr_frames,rx_isr_cycles,rx_reinit_discard,rx_fault_discard;
    uint32_t rx_lag_cycles,rx_stale_discard,main_gap_cycles,report_cycles;
    uint32_t report_seq,paused,bus_dropped,diag_period_ms;
    BenchRx rx[8];
} BenchStats;
extern BenchStats bench_stats;
extern volatile uint32_t g_uptime_ms;
void console(const char *text);
/* 原驱动内部弱钩子；bench被动接收阶段也需显式推进。 */
void mp_bus_hardware_poll(void);
void bench_init(void);
void bench_command(int command);
void bench_step(void);
void bench_observe_rx(const MpCanFrame *frame);
void bench_observe_rx_at(const MpCanFrame *frame,uint32_t received_ms);
void bench_update_rx_metrics(void);
uint32_t bench_clock_cycles(void);
void bench_observe_tx(const MpCanFrame *frame,bool acknowledged);
void bench_observe_registers(uint32_t pclk,uint32_t btr,uint32_t esr,uint32_t tsr,
                             uint32_t overflow,uint32_t bad);
#endif
