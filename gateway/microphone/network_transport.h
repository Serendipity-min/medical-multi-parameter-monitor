#ifndef MIC_NETWORK_TRANSPORT_H
#define MIC_NETWORK_TRANSPORT_H
#include <stdint.h>
#include <stddef.h>
int mic_network_configure(const uint8_t *packet, size_t length);
int mic_network_connect(void);
int mic_network_send(const uint8_t *packet, size_t length);
int mic_network_poll(void);
void mic_network_close(void);
uint32_t mic_network_epoch(void);
void mic_network_reply(const uint8_t *packet, size_t length);
#endif
