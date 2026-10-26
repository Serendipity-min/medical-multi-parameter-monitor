#ifndef B4_GATEWAY_H
#define B4_GATEWAY_H
#include "b4_bus.h"
#include "../storage/router.h"
#include "b4_resources.h"
typedef struct {
    MpOD od; CO_config_t config; CO_t *co; B4Port port;
    uint32_t seen_at[5], generation, observed_boot, seq[MP_STREAMS], last_tick[2];
    uint32_t first_tick[2];
    bool seen[5], have_tick[2];
    uint32_t nibp_tick;
    bool nibp_emitted;
    bool link_up;
    bool status_sent, last_online;
    uint32_t status_at;
    MpFrame wave[2];
} B4Segment;
typedef struct {
    B4Segment segments[2]; MpRouter router;
    uint32_t now, epoch, utc_at, utc_fraction, time_sent, malformed, wrong_bus, resets, wave_gaps, unstamped;
    uint32_t session; /* B5由新鲜SNTP毫秒锚建立网关连接代次，不改节点原始boot字段。 */
    bool utc_valid;
} B4Gateway;
int b4_gateway_init(B4Gateway *g);
void b4_gateway_close(B4Gateway *g);
void b4_gateway_tick(B4Gateway *g, uint32_t now);
void b4_gateway_receive(B4Gateway *g, unsigned bus, MpCanFrame *f, uint32_t arrival);
void b4_gateway_sync(B4Gateway *g, uint32_t epoch, uint32_t now);
void b4_gateway_sync_ms(B4Gateway *g, uint64_t utc_ms, uint32_t now);
int b4_gateway_nmt(B4Gateway *g, unsigned node, CO_NMT_command_t command);
bool b4_gateway_online(B4Gateway *g, unsigned node);
void b4_gateway_link(B4Gateway *g, unsigned bus, bool online);
#endif
