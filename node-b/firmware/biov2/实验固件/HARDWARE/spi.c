/** @file spi.c @brief SPI1：PA5=SCLK、PA6=MISO/DOUT、PA7=MOSI/DIN。
 * 模式1；84MHz/128=656.25kHz，满足512kHz芯片时钟下寄存器SCLK<=2fCLK。
 * 72位纯移位约109.7us；保留10us命令间隔、有界收发及独立错误状态。
 */
#include "spi.h"

void SPI1_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;
    SPI_InitTypeDef SPI_InitStructure;

    // F4 的 GPIO 时钟位于 AHB1。
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_SPI1, ENABLE);

    // PA5=SCLK / PA6=MISO(DOUT) / PA7=MOSI(DIN) 全部复用为 SPI1
    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_5 | GPIO_Pin_6 | GPIO_Pin_7;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_NOPULL;
    GPIO_Init(GPIOA, &GPIO_InitStructure);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource5, GPIO_AF_SPI1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource6, GPIO_AF_SPI1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource7, GPIO_AF_SPI1);

    SPI_I2S_DeInit(SPI1);
    SPI_InitStructure.SPI_Direction = SPI_Direction_2Lines_FullDuplex;
    SPI_InitStructure.SPI_Mode = SPI_Mode_Master;
    SPI_InitStructure.SPI_DataSize = SPI_DataSize_8b;
    SPI_InitStructure.SPI_CPOL = SPI_CPOL_Low;
    SPI_InitStructure.SPI_CPHA = SPI_CPHA_2Edge;
    SPI_InitStructure.SPI_NSS = SPI_NSS_Soft;                 // 片选用 PA2 软件控制
    SPI_InitStructure.SPI_BaudRatePrescaler = SPI_BaudRatePrescaler_128; // 寄存器及数据共用安全速率，仍远小于4ms帧周期
    SPI_InitStructure.SPI_FirstBit = SPI_FirstBit_MSB;        // ADS1292 高位在前
    SPI_InitStructure.SPI_CRCPolynomial = 7;
    SPI_Init(SPI1, &SPI_InitStructure);
    SPI_Cmd(SPI1, ENABLE);
}

/**
 * @brief  全双工收发一个字节。
 * @param  data 要发送的字节（读数据时发 0xFF 产生时钟）。
 * @retval 同时收到的字节。
 * @note   两个 while 都有超时保护：硬件异常（线没接、时钟没起）时不会死等，
 *         而是返回 0xFF，让上层能继续跑并把错误暴露出来。
 */
uint8_t SPI1_TxRx(uint8_t data)
{
    uint32_t guard = 0;   // 超时计数，防止硬件异常时死等

    // 等待发送缓冲区空（TXE=1），超时则放弃并返回 0xFF
    while (SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_TXE) == RESET)
        if (++guard > 100000) return 0xFF;
    SPI_I2S_SendData(SPI1, data);
    guard = 0;
    // SPI 全双工：发送数据的同时必须读走接收数据，否则会溢出。
    // 等待接收缓冲区非空（RXNE=1），超时同样返回 0xFF
    while (SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_RXNE) == RESET)
        if (++guard > 100000) return 0xFF;
    return (uint8_t)SPI_I2S_ReceiveData(SPI1);
}

/* 新采集路径：每个等待最多 50us，时间含更高优先级抢占，不用循环次数当时间。
 * 失败单独返回，0xFF 仍可作为合法数据；不做无限自动重试。 */
uint8_t SPI1_TxRxChecked(uint8_t data, uint8_t *received)
{
    uint32_t begin, budget = SystemCoreClock / 20000u;
    if (received == 0) { return 0; }
    begin = DWT->CYCCNT;
    while ((SPI1->SR & SPI_I2S_FLAG_TXE) == 0) {
        if ((uint32_t)(DWT->CYCCNT - begin) > budget) { return 0; }
    }
    if (SPI1->SR & (SPI_SR_MODF | SPI_I2S_FLAG_OVR)) { return 0; }
    SPI1->DR = data;
    begin = DWT->CYCCNT;
    while ((SPI1->SR & SPI_I2S_FLAG_RXNE) == 0) {
        if ((uint32_t)(DWT->CYCCNT - begin) > budget) { return 0; }
    }
    *received = (uint8_t)SPI1->DR;
    return 1;
}
