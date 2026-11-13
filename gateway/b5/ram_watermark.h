#ifndef B5_RAM_WATERMARK_H
#define B5_RAM_WATERMARK_H
#include <stdint.h>
/* 只填充链接堆末尾到当前MSP下256B的未用区；不改活动栈或CANopen堆。 */
static inline void b5_stack_watermark_init(void) {
    extern uint32_t _heap_end;uint32_t sp;
    __asm volatile("mrs %0,msp":"=r"(sp));
    for(volatile uint32_t *p=&_heap_end;(uintptr_t)p+256u<sp;p++)*p=0xa55a3cc3u;
}
static inline uint32_t b5_stack_used_upper(void) {
    extern uint32_t _heap_end,_estack;volatile uint32_t *p=&_heap_end;
    while(p<&_estack && *p==0xa55a3cc3u)p++;
    return (uint32_t)((uintptr_t)&_estack-(uintptr_t)p);
}
#endif
