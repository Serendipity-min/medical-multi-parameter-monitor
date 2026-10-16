// @file    canopen.h
// @brief   心率节点 CANopen 从站（CiA 301 精简子集，标准外设库）
// 网络：ADS1292_心率屏工程（本节点） ──CANopen/CAN──► 神舟号 STM32F407ZGTX（主机）
// 已实现：NMT 从站 / Heartbeat(0x700+ID) / TPDO1 心率呼吸(0x180+ID) /
// SDO 服务端加速+分段(0x600/0x580+ID) / EMCY 越限报警(0x080+ID)
// 预定义连接集（NodeID = CO_NODE_ID，默认 3）：
// NMT 0x000 / SYNC 0x080 / EMCY 0x083 / TPDO1 0x183
// SDO 收 0x603 / SDO 发 0x583 / 心跳 0x703
#ifndef __CANOPEN_H
#define __CANOPEN_H

#include "stm32f4xx.h"

// ---------------- 节点身份 ----------------
// ★ 体温节点占 NodeID=2，心率节点用 3，避免同总线冲突（待与主机确认）
#define CO_NODE_ID          (3)
#define CO_DEV_TYPE         (0x00000000)  // 厂商特定，未分配 DS 子协议
#define CO_VENDOR_ID        (0x00000001)
#define CO_PRODUCT_CODE     (0x0000A129)  // ADS1292 心率/呼吸
#define CO_REVISION         (0x00010000)  // 1.00
#define CO_SERIAL           (0x00000003)

// 0x1008 / 0x1009 / 0x100A 字符串对象
#define CO_DEV_NAME         "ADS1292-HR-NODE"  // 15 字节，走分段上传
#define CO_HW_VER           "1.00"
#define CO_SW_VER           "1.00"

// 0x1001 错误寄存器位：bit0 通用错误 + bit5 设备特定（有报警时置位）
#define CO_ERR_BITS         (0x01 | 0x20)

// ---------------- 预定义连接集 ----------------
#define CO_COB_NMT          (0x000)
#define CO_COB_SYNC         (0x080)
#define CO_COB_EMCY         (0x080 + CO_NODE_ID)
#define CO_COB_TPDO1        (0x180 + CO_NODE_ID)
#define CO_COB_SDO_RX       (0x600 + CO_NODE_ID)  // 主机 -> 本节点
#define CO_COB_SDO_TX       (0x580 + CO_NODE_ID)  // 本节点 -> 主机
#define CO_COB_HEARTBEAT    (0x700 + CO_NODE_ID)

// ---------------- NMT 状态 ----------------
#define CO_NMT_BOOTUP       (0x00)
#define CO_NMT_STOPPED      (0x04)
#define CO_NMT_OPERATIONAL  (0x05)
#define CO_NMT_PREOP        (0x7F)

// ---------------- NMT 命令字（帧 ID 0x000，data[0]） ----------------
#define CO_NMT_CMD_START    (0x01)
#define CO_NMT_CMD_STOP     (0x02)
#define CO_NMT_CMD_PREOP    (0x03)
#define CO_NMT_CMD_RSTNODE  (0x04)  // 复位节点
#define CO_NMT_CMD_RSTCOMM  (0x05)  // 复位通信
#define CO_NMT_CMD_RSTAPP   (0x06)  // 复位应用

// ---------------- 对象索引 ----------------
#define CO_IDX_DEV_TYPE     0x1000
#define CO_IDX_ERROR_REG    0x1001
#define CO_IDX_COB_SYNC     0x1005
#define CO_IDX_DEV_NAME     0x1008
#define CO_IDX_HW_VER       0x1009
#define CO_IDX_SW_VER       0x100A
#define CO_IDX_HB_TIME      0x1017
#define CO_IDX_IDENTITY     0x1018
#define CO_IDX_SDO_SRV      0x1200
#define CO_IDX_TPDO1_COMM   0x1800
#define CO_IDX_TPDO1_MAP    0x1A00
#define CO_IDX_HR_OBJ       0x2100  // 厂商特定：心率/呼吸应用对象

// 0x2100 子索引
#define CO_APP_BPM          1  // int16 bpm，0x7FFF 无效
#define CO_APP_RPM          2  // int16 rpm，0x7FFF 无效
#define CO_APP_STATUS       3  // uint8 bit0 心率有效 bit1 呼吸有效 bit2 导联 bit3 监护中
#define CO_APP_ALARM        4  // uint8 0 正常 1 心率报警 2 呼吸报警 3 两路都异常
#define CO_APP_QUALITY      5  // uint8 0~100 信号质量
#define CO_APP_HR_LIM_HI    6  // int16 bpm 可读写
#define CO_APP_HR_LIM_LO    7  // int16 bpm 可读写
#define CO_APP_RR_LIM_HI    8  // int16 rpm 可读写
#define CO_APP_RR_LIM_LO    9  // int16 rpm 可读写

#define CO_STATUS_HR_VALID  (0x01)
#define CO_STATUS_RR_VALID  (0x02)
#define CO_STATUS_PROBE     (0x04)
#define CO_STATUS_RUNNING   (0x08)

// ---------------- EMCY 错误码（厂商特定区 0x5000~0x5FFF） ----------------
#define CO_EMCY_NONE        (0x0000)
#define CO_EMCY_HR_HI       (0x5001)  // 心率过速
#define CO_EMCY_HR_LO       (0x5002)  // 心率过缓
#define CO_EMCY_RR_HI       (0x5003)  // 呼吸过速
#define CO_EMCY_RR_LO       (0x5004)  // 呼吸过缓
#define CO_EMCY_LEAD_OFF    (0x5005)  // 导联脱落/电极故障

// ---------------- 统计 ----------------
typedef struct
{
    uint32_t tpdo_tx;  // TPDO1 发送帧数
    uint32_t hb_tx;  // 心跳帧数
    uint32_t emcy_tx;  // EMCY 帧数
    uint32_t sdo_rx;  // 收到的 SDO 请求数
    uint32_t sdo_abort;  // SDO 中止应答数
    uint32_t nmt_cmd;  // 收到的 NMT 命令数
} CoStats_t;

void     CanOpen_Init(void);
void     CanOpen_Task(uint32_t now_ms);  // 主循环调用，可每 10ms 进一次
uint8_t  CanOpen_GetNmtState(void);
void     CanOpen_GetStats(CoStats_t *s);
uint8_t  CanOpen_SelfTest(void);  // 回环自测：1=通过 0=失败（自动切回 Normal）
uint8_t  CanOpen_GetSelfTest(void);  // 上电自测结果：0xFF=未测 1=通过 0=失败

#endif  // __CANOPEN_H
