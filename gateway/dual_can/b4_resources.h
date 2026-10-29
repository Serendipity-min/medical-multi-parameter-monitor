#ifndef B4_RESOURCES_H
#define B4_RESOURCES_H
/* PB12/PB13一旦交给CAN2，不允许未来麦克风目标默默复用I2S2默认引脚。 */
#if defined(B4_I2S2_PB12_PB13) && B4_I2S2_PB12_PB13
#error B4_CAN2_CONFLICTS_WITH_I2S2_PB12_PB13
#endif
#define B4_CAN2_FILTER_START 14u
#define B4_JSON_CAPACITY 2048u
#define B4_ECG_BATCH 100u
/* 隔离台架的管理禁用优先于物理ESR正常；CAN1共享时钟不等于允许A段发送。 */
static inline int b4_hw_protocol_link_up(unsigned bus,int physical_up) {
#if defined(B4_CAPTURE_SERIAL) || defined(MP_B5_CLOUD_CANDIDATE)
    return bus==1 && physical_up;
#else
    return bus<2 && physical_up;
#endif
}
#if !defined(MP_FRAME_MAX_SAMPLES) || MP_FRAME_MAX_SAMPLES != 100
#error B4_MODEL_REQUIRES_100_SAMPLE_ABI
#endif
#ifdef MP_B5_EGRESS_FINAL
#if MP_LIVE_CAPACITY != 24 || MP_CACHE_CAPACITY != 56
#error B5_EGRESS_REQUIRES_24_LIVE_56_HISTORY_SAME_80_FRAME_BUDGET
#endif
#elif !defined(MP_CACHE_CAPACITY) || MP_CACHE_CAPACITY != 64
#error B4_ROUTER_REQUIRES_64_CACHE_SLOTS
#endif
#endif
