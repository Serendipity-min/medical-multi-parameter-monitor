// @file    can.h
// @brief   CAN1 底层驱动（ST 标准外设库）
// CAN1: PB8=CAN1_RX / PB9=CAN1_TX，AF9，1 Mbps（APB1 = 42MHz）。
// 只做帧收发 + 接收环形缓冲 + 统计，数据语义在 canopen.c。
// ★ CAN1_RX0_IRQHandler / CAN1_SCE_IRQHandler 在 can.c 里实现，别处不要重复定义。
#ifndef __CAN_H
#define __CAN_H

#include "stm32f4xx.h"

// 接收环形缓冲深度
#define CAN_RX_BUF_SIZE     (32)

typedef struct
{
    uint32_t id;  // 标准帧 ID
    uint8_t  dlc;  // 0~8
    uint8_t  data[8];
} CanFrame_t;

typedef struct
{
    uint32_t tx_ok;  // 发送成功帧数
    uint32_t tx_busy;  // 邮箱满丢弃帧数
    uint32_t rx_ok;  // 接收帧数
    uint32_t rx_drop;  // 接收缓冲溢出丢帧数
    uint32_t err_warning;  // 错误警告计数
    uint32_t err_passive;  // 错误被动计数
    uint32_t bus_off;  // 总线关闭次数（ABOM 自动恢复）
} CanStats_t;

void     CAN1_Config(void);
uint8_t  CAN1_Send_Msg(uint32_t std_id, const uint8_t *data, uint8_t dlc);
uint8_t  CAN1_Recv_Msg(CanFrame_t *f);
void     CAN1_GetStats(CanStats_t *s);
void     CAN1_ResetStats(void);

// 进入回环等特殊模式（mode 取 stm32f4xx_can.h 的 CAN_Mode_*），位时序不变
void     CAN1_SetMode(uint8_t mode);

#endif  // __CAN_H
