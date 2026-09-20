#ifndef MP_MODEL_H
#define MP_MODEL_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef enum { MP_PPG,MP_SPO2,MP_PR,MP_NIBP,MP_ECG,MP_HR,MP_RESP,MP_RR,MP_TEMP,MP_NODE_STATUS,MP_FAULT,MP_GATEWAY_STATUS,MP_STREAMS } MpStream;
typedef struct {
  uint64_t timestamp;
  uint32_t seq,epoch,boot;
  int32_t values[250];
  uint16_t count,rate;
  uint8_t node,stream;
  bool valid,synthetic,replay;
} MpFrame;
const char *mp_stream_name(MpStream stream);
int mp_json(const MpFrame *f,char *out,size_t size);
int mp_topic(const MpFrame *f,char *out,size_t size);
#endif
