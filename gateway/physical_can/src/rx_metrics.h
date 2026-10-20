#ifndef MP_NETWORK_RX_METRICS_H
#define MP_NETWORK_RX_METRICS_H
#include <stdint.h>
#include <stdbool.h>
/* 网络候选只记累计计数/时延，ISR不触碰协议、日志或网络。 */
typedef struct {
 uint32_t pclk,rx_sw_overflow,rx_high_water,rx_depth,rx_full,rx_fifo_depth;
 uint32_t rx_isr_calls,rx_isr_frames,rx_isr_cycles,rx_reinit_discard,rx_fault_discard;
 uint32_t main_gap_cycles,rx_lag_cycles,rx_stale_discard,fault;
 uint32_t heartbeat_a,bootup_a,pdo_a[4],tx_acked,tx_failed,nmt_start_acked,time_acked,esr;
 /* 对端缺席独立于严重fault；寄存器快照首次锁存，不被后续轮询/自动硬件恢复覆盖。 */
 uint32_t peer_wait,peer_losses,peer_returns,tx_no_ack,tx_peer_discard;
 uint32_t fault_esr,fault_tsr,fault_at_ms,protocol_reset;
 uint32_t peer_event_esr,peer_event_tsr,peer_event_at_ms;
} PhysicalRxMetrics;
extern PhysicalRxMetrics physical_rx_metrics;
extern uint32_t physical_rx_overflow,physical_bad_frame;
void physical_rx_update_metrics(void);
/* 仅表示收到合法Node-A心跳/Boot-up，不等于OPERATIONAL或采集VALID。 */
bool physical_peer_seen(void);
#endif
