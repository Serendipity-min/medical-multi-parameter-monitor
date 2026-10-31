#include <stdint.h>
/* 只替换外设读数入口，类型字段与原 app_bp.h 保持一致。 */
typedef enum { ST_IDLE, ST_MEASURING, ST_STOPPING } bp_state_t;
typedef struct { uint8_t valid; uint16_t sys,dia; uint8_t pr,irregular; uint16_t year; uint8_t mon,day,hour,min; uint32_t valid_tick,result_generation; } bp_last_t;
bp_last_t bp_last_get(void);
bp_state_t bp_state_get(void);
