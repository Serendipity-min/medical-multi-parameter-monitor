#ifndef __SPI_H
#define __SPI_H

#include "stm32f4xx.h"

// STM32F407 SPI1 底层驱动。PA5=SCLK，PA6=MISO(DOUT)，PA7=MOSI(DIN)。
void SPI1_Init(void);
uint8_t SPI1_TxRx(uint8_t data);

/* 有界采集收发，返回状态与采样字节分离。 */
uint8_t SPI1_TxRxChecked(uint8_t data, uint8_t *received);
#endif
