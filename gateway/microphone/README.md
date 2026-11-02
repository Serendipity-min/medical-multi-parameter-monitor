# Gateway-C INMP441 独立台架

起点是三板集成 `e1274b337e2b8393b315409cc5d030a83658b129`，当前记录C44520；附件C49132为旧状态。A/B源码、双CAN、ESP USART3、TTS USART2及sector3均不为麦克风挪用。此目录不进入现有固件默认构建，不是统一发布镜像。

唯一现场方案为I²S3 AF6：VCC→3V3、GND→GND、L/R→GND、WS→PA4、SCK→PC10、SD→PC12。本机神舟号V2.0图纸第4页标注PA4=P9-37、PC10=P8-35、PC12=P8-37，接线依实物丝印；图纸版本不冒充实物PCB修订已确认。PA4另到无源ADC/DAC排针；PC10/PC12到TF卡座。负责人确认无SD卡和外部设备，已完成断电接线。备选PB3/PB5涉及JTAG/SWO、SPI Flash，未选择；WM8978在I²S2，未启用。

模块去耦及外部SD下拉是否存在为UNKNOWN；SD启用MCU内部下拉以确定三态期间电平，不声称已实测电源纹波。不得接5V，不带电改线。

`build.py`复用当前C的GNU/SPL工具链和48KiB链接器，核对真实ELF加载段、中断向量和DMA可达地址。Flash只能触及sector0–2；sector3、Options和其他扇区必须保留。真实部署使用现有`abc_board_backup.py`/`abc_board_install.py`，先核对今日C身份和备份，台架结束恢复备份原应用，不用旧C49132回退。

`bench_main.c`保持SYSCLK=8MHz HSE，仅在主PLL及PLLI2S均关闭时设置共享PLLM=8、PLLI2SN=256/R=5；不重置全局RCC。I²S3 Master Receive、Philips、24bit/32slot、16kHz、64BCLK、无MCK。DMA1 Stream0 Channel0，两个1280B目标，半字宽，每10ms切换。ISR仅计数/记原始DWT时间/标记完成；主循环检测未消费覆盖及复制跨DMA切换，错误停止，不拼接坏块。

只响应显式`R`录音：先时钟稳定0.5秒，再收32000个左声道样本（2秒），保存前16帧双槽原始半字及右槽统计。PF9低亮表示录音；停止后通过`D`导出PCM16及CRC32、寄存器和全部250个IRQ时间戳。没有增益、归一化、实时串口音频或联网。`S`人工停止；`I`只查询台架标识。每次R独立覆盖RAM录音，主机保存到新的加密目录。

`mic_format.c`保留24bit二补码，明确半字顺序和左右槽，丢弃低8位转换PCM16。`test_format.c`是真实转换器的正负数、双槽及CRC夹具；`test_capture.py`检查真实导出校验器的截断、篡改、DMA错误、错声道、时钟错误及周期计数回绕。合成夹具只记HOST_I2S_FORMAT_PASS。

`capture.py --port COMx --condition quiet|tone|speech --out <新的EFS目录>`默认不打开串口，加`--execute`才发起一次采集。原始串口、PCM、WAV和回执仅进受限EFS，录完才传输。依次取得静音、已知固定音调、近讲短句，并比较声道、频谱/RMS、截幅、IRQ时序及人工听音后，才能认定MIC_LOCAL_PASS；单份CRC通过不等于完整验收。

后续真实音频经PC代上传只能记HOST_BRIDGE_PROOF；实际C分块上行及隔离ASR通过才记MIC_ASR_UPLINK_PASS；同会话AI回复及TW-TTS人工可闻才记MIC_CLOUD_ROUNDTRIP_PASS。V1实录通过前不启动V2实测，不因空间不足覆盖配置区。

`build.py --network`构建独立C语音候选：复用上述录音器、原ESP8266 TLS/MQTT传输及VOICE-002的USART2/TTS组件。此镜像不链接CAN驱动，必须仅C上电、两段CAN隔离；保留CAN引脚不代表三板负载共存通过。2秒原始PCM录完后分125个512字节块上传，云端核对序号、长度、CRC及会话再执行ASR和真实AI；未设固定回复兜底。

`field.py --job <受限目录> --port COMx --action connect|capture|stop`先查询当前镜像标识，再执行对应动作。`connect`仅向RAM配置隔离MQTT角色，核对TLS、SUBACK及低音量设置ACK；`capture`只观察Broker，不代发C音频，结束后导出源PCM与云端实收逐字节对账。ACK、播放完成、STOP确认和人工听到分别记录。原音频及运行凭据不得进入Git。现场声源须在回复准备完成前开始持续播放，采集完成后停止，以免把没有覆盖录音窗口的说话判成麦克风失败。

现场迁移后原Wi-Fi不可用，最终`WIFI_RAM_V3_SSH_UTC`标识对应249字节`MCF3`配置帧：MQTT角色后追加33字节SSID、65字节Wi-Fi口令与32位UTC秒，末尾CRC32。配置仅在RAM，按AT引号边界拒绝换行、引号及反斜杠，禁止向旧入口发送新帧。主机从受限`host-hotspot-runtime-private.json`读取负责人确认的当前手机热点配置；不把现场口令编入固件或写回sector3。

手机网络下三个既有UDP授时端点均未取得有效回复，原失败保留。此独立镜像改用现有SSH认证链读取隔离服务器UTC，先确认`NTPSynchronized=yes`并记录实际查询往返耗时，再通过易失`AT+SYSTIMESTAMP`设置及读回模块时钟。C继续进行CA/主机名校验，毫秒推进仍来自本板单调计数；UTC为秒级量化且包含已记录的主机查询延迟，不冒充独立精密授时或UDP SNTP通过。原B5/C构建及新鲜UDP判据未修改。

外部18884连接未到达服务器，故仅占用已放行且无既有监听的1883，运行`cloud/microphone/ingress.py`临时TCP透传到隔离Broker18884。透传不终止TLS、不解密、不记录音频，正式服务与防火墙不改；结束停止本任务入口。主机监听Broker仅用于观察C实际上传，不代发C输入。

发布型客户端原本仅配置出站QoS1表，直接订阅QoS1会被coreMQTT以`MQTTBadParameter`拒绝。语音适配层增加一条入站记录；`test_subscription.c`使用真实coreMQTT、真实adapter及实际订阅回调，覆盖分片SUBACK、降级/拒绝/错ID和入站QoS1及PUBACK。ESP返回为合成数据，只记Host回归；现场`MIC_VOICE_READY`才证明C的订阅及音量设置ACK。

资料：[TDK INMP441，页8/10–12/15](https://product.tdk.com/system/files/dam/doc/product/sw_piezo/mic/mems-mic/data_sheet/inmp441.pdf)、[ST F407数据手册](https://www.st.com/resource/en/datasheet/stm32f407vg.pdf)、本机`E:/stm32/stm32文件/STM32F407_原理图.pdf`（6页）、本机RM0090及现有C启动源码。首次上电零输出时间按TDK的2^18个SCK处理：1.024MHz下约256ms，台架预留500ms。HSE与IRQ推导的采样率不是独立频率计测量。
