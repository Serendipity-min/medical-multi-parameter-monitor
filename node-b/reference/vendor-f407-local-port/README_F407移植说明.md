# STM32F407 移植版（凌智 ADS1292 FIR 例程）

原工程：`..\STM32F429\STM32F429_FIR_ADS1292_usart`（HAL 库 + CMSIS-DSP FIR）

## 改了什么（其余与商家代码一致）

| 文件 | 改动 |
|---|---|
| User/SPI/spi.c | SPI5/PF7/8/9 → SPI1/PA5/6/7（函数名不变） |
| User/ADS1292/ads1292.h | START=PA1、PWDN=PA0、CS=PA2 |
| User/ADS1292/ads1292.c | 控制脚 GPIOA，DRDY 读 PA3 |
| User/EXTI/exti.c | DRDY=PA3，EXTI9_5 → EXTI3 |
| User/delay/delay.h | 系统时钟 180 → 168 MHz |
| User/stm32f429_Winner/stm32f429_winner.c | 去掉 F429 专有的调压器/OverDrive 调用 |
| Project/main.c | 时钟参数 (360,25,2,8)→(336,8,2,7)（8M 晶振→168M）；无 SDRAM |
| Project/DSP_FIR.uvprojx | 芯片 STM32F407ZGTx、启动文件 startup_stm32f40_41xxx.s、宏 STM32F407xx、剔除 lcd/ltdc/sdram |
| CMSIS/DeviceSupport | 加 stm32f407xx.h（取自本地 CubeFW V1.28.3）、startup_stm32f40_41xxx.s |

## 使用

- 接线：SCLK=PA5、DOUT=PA6、DIN=PA7、CS=PA2、START=PA1、PWDN=PA0、DRDY=PA3（与 ADS1292_Test 相同）
- 串口：USART1 PA9/PA10，**波特率 115200**（商家默认，调试工具里选 115200！）
- 输出协议：`B: xx A: xx C: xx.xx`（B=呼吸波、A=心电波、C=心率），配套 ADS1292调试工具2022.exe
- Keil 打开 `Project/DSP_FIR.uvprojx`，直接 Rebuild + Download
