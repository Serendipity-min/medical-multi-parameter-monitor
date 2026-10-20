#include <assert.h>
#include <stdio.h>
#include "hse_clock.h"
#include "link_policy.h"
static volatile uint32_t cr,cfgr;
static unsigned steps;
static void ready(void) {
    steps++;
    if(steps==3)cr|=1u<<17;
    if((cfgr&3u)==1u)cfgr=(cfgr&~12u)|4u;
}
int main(void) {
    /* 晶体未起振及SWS未切换都不能静默使用HSI；寄存器无关位必须保留。 */
    cr=0;cfgr=0;assert(!physical_hse_start(&cr,&cfgr,0,5));assert((cfgr&3u)==0);
    cr=1u<<17;cfgr=0;assert(!physical_hse_start(&cr,&cfgr,0,5));
    cr=0x80;cfgr=0x100;steps=0;assert(physical_hse_start(&cr,&cfgr,ready,10));
    assert(cr&0x80);assert(cfgr&0x100);assert((cfgr&15u)==5u);
    /* 8MHz总线仍精确形成500kb/s、16时间量子/87.5%采样点。 */
    uint32_t btr=0;assert(physical_btr(8000000u,&btr));assert(btr==0x001c0000u);
    puts("HSE bounded startup / fail closed / preserved bits / CAN500k PASS");
    return 0;
}
