/*!
*  \file hmi_user_uart.h
*  \brief 串口初始化（STM32F407 标准外设库版）
*  \version 1.1 (F407 移植版)
*  \date 2012-2018 / 移植 2026
*  \copyright 广州大彩光电科技有限公司（原文件）/ F407 移植版
*/
#ifndef _USER_UART__
#define _USER_UART__

#include "stm32f4xx.h"        // F1 版这里是 stm32f10x_it.h，移植时改为 F4 头

#define uchar    unsigned char
#define uint8    unsigned char
#define uint16   unsigned short int
#define uint32   unsigned long
#define int16    short int
#define int32    long

/*
 * 与串口屏的通信波特率，必须与 VisualTFT 工程设置一致！
 * UI 工程 DeviceBaudRate=7，档位表第 7 档 = 115200。
 * 接线：PA9(TX)->屏 DIN，PA10(RX)<-屏 DOUT（屏背面 J5 短接才是 TTL 电平）。
 */
#define HMI_BAUDRATE   115200

/****************************************************************************
* 名    称： UartInit()
* 功    能： 串口初始化（USART1，PA9=TX -> 屏RX，PA10=RX <- 屏TX）
* 入口参数： Baudrate 波特率
* 出口参数： 无
****************************************************************************/
void UartInit(uint32 Baudrate);

/*****************************************************************
* 名    称： SendChar()
* 功    能： 发送1个字节（阻塞式）
* 入口参数： t  发送的字节
* 出口参数： 无
*****************************************************************/
void  SendChar(uchar t);

#endif
