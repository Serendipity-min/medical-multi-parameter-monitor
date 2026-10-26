# AUTH-B5-HW0-VISUAL-READONLY-001 R1｜现状核对，禁用

`enabled=false; owner_approved=false; executions=0`。仅准备；G0不向实板发送任何指令。[共同绑定](B5-G0-SPLIT-AUTHORIZATIONS.md)适用。

未来单独批准后一次≤180秒目视/已有资料核对，不移动跳帽、电极或线缆，不上电/断电/复位，不接表，不开COM/J-Link，不发AT。一次填写：

1. C/B当前电源接口、开关、USB与JTAG分别在哪块板，供电/ESP复位或EN隔离现状；不把旧记录当当前事实。
2. C已安装ESP8266的可见型号/板标及已有AT版本回执；看不到/无回执填UNKNOWN，不拆模块或查询。源码ESP接口为USART3 PB10_TX/PB11_RX；需核对跳线实际对应，不能凭同款板推断已连接。
3. C P4 CAN2_RX↔PB12、TX↔PB13，B P6 CAN1_RX↔PA11、TX↔PA12及USB D+/D−选择、H/L/独立参考地现状；A段是否物理断开、INMP441/TTS是否隔离；不测阻或改线。
4. 当前SKX源/电池/充电USB、电极/人体隔离及屏幕刷新现状；不为满足目标而切模式或重启。

G0已知“ESP装在C”、ABC同款F407与历史跳线资料不再重复索要。只有当前状态/未知项需此核对，未获准前不让负责人现在操作。目视结果不是ESP固件/TLS实测，也不是MCU身份/Flash读回。

若以后需要AT版本/CA/SNI查询，应另批确有电气隔离的ESP串口通道及精确只读命令/预算；开发板USB_UART是MCU诊断口，不能假定它是ESP AT直通。没有此通道则保持UNKNOWN，不能临时改P5或烧串口桥接固件。G2-RO只读MCU也不自动授权ESP查询。
