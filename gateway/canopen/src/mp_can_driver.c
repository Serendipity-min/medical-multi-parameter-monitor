/* CANopenNode 驱动适配：核心协议由上游实现，收发队列不分配动态内存。 */
#include "mp_can_driver.h"
#include <string.h>
static MpCanPort *ports[3];
static MpCanFrame pending[128];
static unsigned head, tail, count;
static uint32_t frames, dropped;
static bool bus_online = true;
void mp_bus_reset(void) { memset(ports,0,sizeof(ports)); head=tail=count=0; frames=dropped=0; bus_online=true; }
void mp_bus_set_online(bool online) { bus_online=online; if (!online) { dropped+=count; count=head=tail=0; } }
uint32_t mp_bus_frames(void) { return frames; }
uint32_t mp_bus_dropped(void) { return dropped; }
void mp_bus_receive(MpCanFrame *frame) {
  if (!bus_online || frame->dlc>8) return;
  for (unsigned p=0;p<3;p++) {
    MpCanPort *port=ports[p];
    if (!port || !port->enabled || !port->module->CANnormal) continue;
    CO_CANmodule_t *m=port->module;
    for (unsigned i=0;i<m->rxSize;i++) {
      CO_CANrx_t *rx=&m->rxArray[i];
      if (rx->CANrx_callback && ((frame->ident^rx->ident)&rx->mask)==0) {
        rx->CANrx_callback(rx->object,frame); break;
      }
    }
  }
}
/* 主机测试使用内存 CAN 总线；STM32 构建提供同名硬件实现覆盖此弱符号。 */
__attribute__((weak)) int mp_bus_transmit(MpCanFrame *frame) { mp_bus_receive(frame); return 1; }
__attribute__((weak)) void mp_bus_hardware_poll(void) { }
void mp_bus_poll(void) {
  mp_bus_hardware_poll();
  unsigned budget=64;
  while (count && budget--) {
    if (!mp_bus_transmit(&pending[tail])) break;
    tail=(tail+1)%128; count--; frames++;
  }
}
void CO_CANsetConfigurationMode(void *ptr) { (void)ptr; }
void CO_CANsetNormalMode(CO_CANmodule_t *m) { m->CANnormal=true; }
CO_ReturnError_t CO_CANmodule_init(CO_CANmodule_t *m,void *ptr,CO_CANrx_t rx[],uint16_t nr,CO_CANtx_t tx[],uint16_t nt,uint16_t rate) {
  if (!m || !ptr || !rx || !tx || rate!=500) return CO_ERROR_ILLEGAL_ARGUMENT;
  MpCanPort *port=ptr;
  if (port->id<1 || port->id>3) return CO_ERROR_ILLEGAL_ARGUMENT;
  memset(m,0,sizeof(*m));memset(rx,0,sizeof(*rx)*nr);memset(tx,0,sizeof(*tx)*nt);
  m->CANptr=ptr;m->rxArray=rx;m->rxSize=nr;m->txArray=tx;m->txSize=nt;
  port->module=m;ports[port->id-1]=port;return CO_ERROR_NO;
}
void CO_CANmodule_disable(CO_CANmodule_t *m) { if (m) { m->CANnormal=false; MpCanPort *p=m->CANptr; if (p) ports[p->id-1]=NULL; } }
CO_ReturnError_t CO_CANrxBufferInit(CO_CANmodule_t *m,uint16_t i,uint16_t id,uint16_t mask,bool_t rtr,void *obj,void (*callback)(void*,void*)) {
  if (!m || i>=m->rxSize || !callback) return CO_ERROR_ILLEGAL_ARGUMENT;
  m->rxArray[i]=(CO_CANrx_t){(uint16_t)(id|(rtr?0x800:0)),(uint16_t)(mask|0x800),obj,callback};return CO_ERROR_NO;
}
CO_CANtx_t *CO_CANtxBufferInit(CO_CANmodule_t *m,uint16_t i,uint16_t id,bool_t rtr,uint8_t dlc,bool_t sync) {
  if (!m || i>=m->txSize || dlc>8) return NULL;
  CO_CANtx_t *tx=&m->txArray[i];memset(tx,0,sizeof(*tx));tx->ident=id|(rtr?0x800:0);tx->DLC=dlc;tx->syncFlag=sync;return tx;
}
CO_ReturnError_t CO_CANsend(CO_CANmodule_t *m,CO_CANtx_t *tx) {
  MpCanPort *p=m->CANptr;
  if (!bus_online || !p->enabled) { dropped++; return CO_ERROR_NO; }
  if (count==128) { dropped++;m->CANerrorStatus|=CO_CAN_ERRTX_OVERFLOW;return CO_ERROR_TX_OVERFLOW; }
  pending[head].ident=(uint16_t)tx->ident;pending[head].dlc=tx->DLC;memcpy(pending[head].data,tx->data,8);
  head=(head+1)%128;count++;return CO_ERROR_NO;
}
void CO_CANclearPendingSyncPDOs(CO_CANmodule_t *m) { (void)m; /* 本阶段仅用异步 PDO。 */ }
void CO_CANmodule_process(CO_CANmodule_t *m) {
  if (!bus_online) m->CANerrorStatus|=CO_CAN_ERRTX_BUS_OFF;
  else m->CANerrorStatus&=(uint16_t)~CO_CAN_ERRTX_BUS_OFF;
}
