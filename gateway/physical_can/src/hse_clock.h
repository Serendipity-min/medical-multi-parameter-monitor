#ifndef MP_H3_HSE_CLOCK_H
#define MP_H3_HSE_CLOCK_H
#include <stdint.h>

/* 已核验板卡Y2=8MHz；直接使用HSE，不引入PLL/Flash等待周期或电压档位切换。
 * 轮询有界且失败关闭：不得退回漂移HSI后仍把长期采集时间标成可信UTC。 */
static inline int physical_hse_start(volatile uint32_t *cr,volatile uint32_t *cfgr,
                                    void (*progress)(void),unsigned budget) {
    *cr|=1u<<16; /* RCC_CR_HSEON，晶体模式而非外部有源旁路。 */
    unsigned remaining=budget;
    while(!(*cr&(1u<<17))) {
        if(!remaining--)return 0;
        if(progress)progress();
    }
    *cfgr=(*cfgr&~3u)|1u; /* SYSCLK=HSE；复位态AHB/APB均不分频。 */
    remaining=budget;
    while((*cfgr&12u)!=4u) {
        if(!remaining--)return 0;
        if(progress)progress();
    }
    return 1;
}
#endif
