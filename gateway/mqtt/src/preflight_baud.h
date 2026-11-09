#ifndef GATEWAY_PREFLIGHT_BAUD_H
#define GATEWAY_PREFLIGHT_BAUD_H
#include "gateway_platform.h"

#define PRE_STM_CLOCK 8000000u
#define PRE_ESP_CLOCK 80000000u
#define PRE_BRR(baud) ((PRE_STM_CLOCK+(baud)/2u)/(baud))
#define PRE_ESP_ESTIMATE(baud) (PRE_ESP_CLOCK/(PRE_ESP_CLOCK/(baud)))
#define PRE_ERROR_OK(brr,baud) ((uint64_t)PRE_STM_CLOCK*100u>=(uint64_t)(brr)*(baud)*98u && \
                              (uint64_t)PRE_STM_CLOCK*100u<=(uint64_t)(brr)*(baud)*102u)
_Static_assert(PRE_ERROR_OK(PRE_BRR(ESP_UART_BAUD),PRE_ESP_ESTIMATE(ESP_UART_BAUD)) &&
               PRE_ERROR_OK(PRE_BRR(230400u),PRE_ESP_ESTIMATE(230400u))
#ifdef MP_FIVE_FIELD01
               && PRE_ERROR_OK(PRE_BRR(500000u),PRE_ESP_ESTIMATE(500000u))
#endif
               ,"ESP UART baud error");

static inline uint32_t preflight_brr(uint32_t baud) {
    if(baud==ESP_UART_BAUD)return PRE_BRR(ESP_UART_BAUD);
    if(baud==230400u)return PRE_BRR(230400u);
#ifdef MP_FIVE_FIELD01
    if(baud==500000u)return PRE_BRR(500000u);
#endif
    return 0;
}

static inline int preflight_baud_matches(uint32_t target,uint32_t actual) {
    uint32_t brr=preflight_brr(target);
    return actual && brr && PRE_ERROR_OK(brr,actual);
}
#endif
