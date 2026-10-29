#ifndef B_TEMPERATURE_H
#define B_TEMPERATURE_H
#include "gy641.h"
typedef struct {
    uint32_t received, overflow, uart_errors;
    Gy641 module;
} BTempDiag;
extern BTempDiag g_b_temp;
void BTemp_Init(void);
void BTemp_Task(uint32_t now);
int BTemp_Get(uint32_t now, uint16_t *centi);
#endif
