#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

enum { GPIO_Pin_0=1, GPIO_Pin_6=64, GPIO_Mode_IN=0, GPIO_Mode_OUT=1,
       GPIO_PuPd_UP=1, GPIO_OType_OD=1, RCC_AHB1Periph_GPIOC=4,
       RCC_AHB1Periph_GPIOF=32, ENABLE=1 };
typedef struct { unsigned GPIO_Pin,GPIO_Mode,GPIO_PuPd,GPIO_OType; } GPIO_InitTypeDef;
typedef struct { unsigned OTYPER; } TestGpio;
static TestGpio gpio_c,gpio_f;
#define GPIOC (&gpio_c)
#define GPIOF (&gpio_f)

static uint32_t g_uptime_ms,strap_drop_at,started,released_at;
static unsigned pulses,releases;
static bool pf6_high,strap_low_after_release;
static void RCC_AHB1PeriphClockCmd(unsigned pins,int on){
    assert(pins==(RCC_AHB1Periph_GPIOC|RCC_AHB1Periph_GPIOF) && on);
}
static void GPIO_Init(TestGpio *port,GPIO_InitTypeDef *pin){
    assert(pin->GPIO_PuPd==GPIO_PuPd_UP);
    if(port==GPIOC)assert(pin->GPIO_Pin==GPIO_Pin_0 && pin->GPIO_Mode==GPIO_Mode_IN);
    else assert(port==GPIOF && pin->GPIO_Pin==GPIO_Pin_6 && pin->GPIO_Mode==GPIO_Mode_OUT &&
                pin->GPIO_OType==GPIO_OType_OD && gpio_f.OTYPER==GPIO_Pin_6 && pf6_high);
}
static int GPIO_ReadInputDataBit(TestGpio *port,unsigned pin){
    assert(port==GPIOC && pin==GPIO_Pin_0);
    return g_uptime_ms<strap_drop_at && !(strap_low_after_release && releases);
}
static void GPIO_SetBits(TestGpio *port,unsigned pin){
    assert(port==GPIOF && pin==GPIO_Pin_6 && gpio_f.OTYPER==GPIO_Pin_6);
    if(pulses){releases++;released_at=g_uptime_ms;}
    pf6_high=true;
}
static void GPIO_ResetBits(TestGpio *port,unsigned pin){
    assert(port==GPIOF && pin==GPIO_Pin_6 && pf6_high);
    pulses++;started=g_uptime_ms;pf6_high=false;
}
static void platform_poll(void){g_uptime_ms++;}
#include "../src/esp_pf6_reset.inc"

int main(void){
    strap_drop_at=0;
    assert(platform_esp_hard_reset()==0 && !pulses && !releases);
    strap_drop_at=UINT32_MAX;
    assert(platform_esp_hard_reset()==1 && pulses==1 && releases==1 && pf6_high &&
           released_at-started==21u);
    pulses=releases=0;
    strap_drop_at=g_uptime_ms+5u;
    assert(platform_esp_hard_reset()==-1 && pulses==1 && !releases && !pf6_high);
    pulses=releases=0;strap_drop_at=UINT32_MAX;strap_low_after_release=true;
    assert(platform_esp_hard_reset()==-1 && pulses==2 && releases==1 && !pf6_high);
    puts("PASS_AN_PF6_OPEN_DRAIN_PULSE_AND_GPIO0_INTERLOCK");
}
