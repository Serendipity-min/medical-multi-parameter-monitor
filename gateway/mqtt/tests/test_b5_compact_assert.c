#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MP_B5_EGRESS_FINAL 1
#define __arm__ 1
#include "../src/core_mqtt_config.h"

extern volatile uint32_t gateway_assert_latched;
static jmp_buf end;
static unsigned evaluated,polls,count,disabled,halted,unavailable;
static char text[64];
#define CHECK(condition) do{if(!(condition))exit(2);}while(0)
int gateway_assert_tx_ready(void){CHECK(disabled);polls++;return !unavailable;}
void gateway_assert_tx_write(unsigned char b){CHECK(disabled && count<63);text[count++]=(char)b;}
void gateway_assert_disable_interrupts(void){disabled=1;}
void gateway_assert_halt(void) __attribute__((noreturn));
void gateway_assert_halt(void){halted=1;longjmp(end,1);}
int main(void){
    assert(++evaluated==1);CHECK(evaluated==1 && !halted);
    evaluated=0;
    if(!setjmp(end)){assert(++evaluated==0);return 3;}
    CHECK(evaluated==1 && halted && gateway_assert_latched && disabled);
    CHECK(!strcmp(text,"GW ASSERT_FATAL\r\n") && polls==count);
    disabled=halted=count=polls=0;unavailable=1;
    if(!setjmp(end)){assert(0);return 4;}
    CHECK(halted && disabled && polls==8192 && !count);
    puts("COMPACT_ASSERT_CONDITION_ONCE_FATAL_MARKER_IRQ_AND_BOUNDED_UART_PASS");
    return 0;
}
