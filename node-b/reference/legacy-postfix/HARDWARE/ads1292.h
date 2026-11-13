#ifndef __ADS1292_H
#define __ADS1292_H

#include "stm32f4xx.h"

/* ============================================================================
 * 本轮修复接线：START 已迁移 PG15
 *   PA0 = PWDN/RESET   PG15 = START；PA1 释放为输入   PA2 = CS(软件片选)   PA3 = DRDY(EXTI3)
 *   PA5/6/7 = SPI1 (SCLK/MISO/MOSI)，见 spi.c
 * ==========================================================================*/
#define ADS_CS_LOW()    GPIO_ResetBits(GPIOA,GPIO_Pin_2)
#define ADS_CS_HIGH()   GPIO_SetBits(GPIOA,GPIO_Pin_2)
#define ADS_START_LOW() GPIO_ResetBits(GPIOG,GPIO_Pin_15)
#define ADS_START_HIGH() GPIO_SetBits(GPIOG,GPIO_Pin_15)
#define ADS_PWDN_LOW()  GPIO_ResetBits(GPIOA,GPIO_Pin_0)
#define ADS_PWDN_HIGH() GPIO_SetBits(GPIOA,GPIO_Pin_0)

// ---- SPI 命令（数据手册 6.1/6.2）----
#define ADS_WAKEUP 0x02   // WAKEUP：退出待机模式
#define ADS_RESET  0x06   // RESET：软件复位
#define ADS_START  0x08   // START：启动/重启转换
#define ADS_RDATAC 0x10   // RDATAC：进入连续读模式（上电默认），DRDY 后可连续读 9 字节
#define ADS_SDATAC 0x11   // SDATAC：退出连续读模式，之后才能读写寄存器
#define ADS_RREG   0x20   // RREG：读寄存器，其后 5 位为寄存器地址
#define ADS_WREG   0x40   // WREG：写寄存器，其后 5 位为寄存器地址

// ---- 寄存器地址（数据手册 5.1）----
#define ADS_REG_ID        0x00
#define ADS_REG_CONFIG1   0x01
#define ADS_REG_CONFIG2   0x02
#define ADS_REG_LOFF      0x03
#define ADS_REG_CH1SET    0x04
#define ADS_REG_CH2SET    0x05
#define ADS_REG_RLD_SENS  0x06
#define ADS_REG_LOFF_SENS 0x07
#define ADS_REG_LOFF_STAT 0x08   // 只读
#define ADS_REG_RESP1     0x09
#define ADS_REG_RESP2     0x0A
#define ADS_REG_GPIO      0x0B

// --------------------------------------------------------------------------

// 上电、复位、写寄存器（含回读校验）、进入 RDATAC 并启动转换。
void ADS1292_Init(void);

// 有一帧数据就返回 1（并把 9 字节填进 frame），否则返回 0。
// frame[0..2]=STATUS, frame[3..5]=CH1(呼吸), frame[6..8]=CH2(心电)。
uint8_t ADS1292_ReadFrame(uint8_t frame[9]);

/* SPI命令/寄存器接口仅用于初始化或已停采的配置阶段。
 * s_ready启用后SPI归DRDY ISR所有，主循环不可并发调用这些接口。 */
// 读一个寄存器（用于自检）。
uint8_t ADS1292_ReadReg(uint8_t addr);

/* ============================================================================
 * 命令时序接口（★ 2026-09-23 修正：这是"所有命令都不生效"的真凶）
 * ----------------------------------------------------------------------------
 * 数据手册 §6.4：默认512kHz下多字节命令需要4tCLK（≈7.81us）。
 * 数据手册时序表 tSCCS：第 8 个 SCLK 下降到 CS 高需要 3 tCLK（≈5.86us），当前实现保守保持10us。
 * 厂家 F429 例程在每个字节后、抬 CS 前都插了 delay_us(10)，本工程早期移植
 * 时把这些延时全删了 → 每条命令都在芯片刚解出它的那一刻被掐断。
 * 后果极具迷惑性：读数据完全正常（RDATAC 是上电默认模式，读 9 字节不需要
 * 任何命令），但读 ID / 写寄存器全部失败。
 * ==========================================================================*/

// 发一个单字节系统命令（RESET/SDATAC/RDATAC/START/STOP）。
// 内部已包含 CS 包夹与 tSCCS 保持，请不要自己在外面再拼 CS 时序。
void ADS1292_Cmd(uint8_t c);

// 写一个寄存器（WREG，含字节间隔与 CS 保持）。
void ADS1292_WriteReg(uint8_t addr, uint8_t val);

// 24 位二进制补码 → 32 位有符号。
int32_t ADS1292_S24ToS32(const uint8_t *p);

// 程序实际读走的帧数。
uint32_t ADS1292_GetFrameCount(void);

// 丢弃帧数：主循环未及时读取的帧，以及 STATUS 格式错误的帧。
uint32_t ADS1292_GetMissCount(void);


/* 统计为真实捕获/交付计数，不从时间间隔伪造丢帧数量。 */
typedef struct {
    uint32_t irq_count, captured, delivered, bad_status, spi_errors;
    uint32_t queue_overflow, queue_peak, init_errors, long_gap_count;
    uint32_t min_irq_gap_cycles, max_irq_gap_cycles, max_read_cycles;
} ADS1292Stats;
uint32_t ADS1292_GetLastFrameMs(void);
uint32_t ADS1292_GetLastFrameSequence(void);
uint8_t ADS1292_GetLastFrameFlags(void);
void ADS1292_GetStats(ADS1292Stats *out);
uint8_t ADS1292_IsReady(void);
#endif
