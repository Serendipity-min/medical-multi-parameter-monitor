# ESP8266 固定 AT 查询固件

这是 STM32F407ZGT6 的临时诊断程序，不是 Gateway-C MQTT 实现，也不烧录 ESP8266。
来源：复用本机 `E:/stm32/ai_serial_console` 的 HSI 时钟、链接脚本、系统调用桩与构建结构；
重新实现 USART3 查询逻辑。ST 标准库和 ARM GCC 在本机使用，不复制进仓库。

- COM15 → STM32 USART1：PA9/PA10，115200、8N1。
- STM32 USART3 → ESP Wi-Fi 插座：PB10/PB11，115200、8N1；P5 按原理图短接 3–5、4–6。
- MCU 使用复位后的 16 MHz HSI，不依赖 HSE/PLL。
- PC 只接受 `probe\n`，按固定列表发送 AT、GMR、UART_CUR 及 SSL/接收模式查询。
- 不接受任意 AT 透传，不设置网络、口令、证书、GPIO0 或 ESP 固件。
- 每项查询最多三秒，接收缓冲 4096 字节，记录串口错误与溢出。

## 构建

在已安装 ARM GNU Toolchain 14.2 rel1 和本机 ST 标准库的环境中：

```powershell
python -X utf8 gateway/esp_at_probe/build.py
```

实际依赖路径见 `build.py`。自有源码启用 `-Wextra -Werror`，构建产物保存在忽略的 `build/`。
本轮构建 text=4820、data=84、bss=7004 字节，二进制 4912 字节。

## 硬件测试与恢复

烧录前必须确认实际芯片、Flash 容量和目标身份，备份整片 Flash 并验证两次读取一致。
J-Link 下载前复位停核，避免旧应用的 DMA 等外设影响 RAM 下载程序。
下载后回读核验，复位运行；PC 打开串口前设置 DTR/RTS 为 False，避免额外握手脉冲。

2026-09-20 实测 AT/GMR 成功，ESP 返回 AT 1.1.0.0、SDK 1.5.4；所列新式 SSL 查询返回 ERROR。
这证明串口通路可用，但不证明当前 ESP 固件具备所需 TLS 证书验证能力。
测试后恢复原 STM32 程序并核对整片 Flash；原始备份和原始串口回复保存在仓库外的本机私有目录。
原始回复可能包含既有网络配置，不能直接提交。
