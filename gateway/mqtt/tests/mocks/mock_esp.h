#ifndef MOCK_ESP_H
#define MOCK_ESP_H
#include "gateway_transport.h"
#include "../../../storage/router.h"
#include <stddef.h>
enum { ACK_MATCH, ACK_WRONG, ACK_NONE, ACK_HALF, ACK_DUPLICATE, ACK_INBOUND, ACK_OLD, ACK_INBOUND_QOS1 };
extern int mock_ack_mode, mock_delay_ms, mock_read_limit, mock_send_limit;
extern int mock_send_error, mock_send_zero, mock_connack_code, mock_drop_ping;
extern int mock_drop_connack;
extern int mock_tls_started, mock_ping_count;
extern uint16_t mock_last_id, mock_old_id;
extern unsigned char mock_packet[2048];
extern size_t mock_packet_length;
extern const char *mock_fail_at;
extern MpRouter *mock_router_probe;
void mock_reset(void);
MpFrame mock_frame(MpStream stream, uint16_t rate, bool replay);
void mock_connect(void);
void mock_queue(const unsigned char *packet, size_t length);
#endif
