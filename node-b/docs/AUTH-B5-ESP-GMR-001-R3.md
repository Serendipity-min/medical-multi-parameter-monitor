# AUTH-B5-ESP-GMR-001 R3｜备用模块一次对照查询

负责人已提出更换备用模块尝试。本卡把替换和查询限定为独立一次事务；私有执行器仍需实际替换完成事实后才启用。原模块记A（负责人确认ESP-01S、灯不亮），备用模块记B，不预先标成“旧/新”或“坏/好”。

R2中C已正常运行Flash，固定115200档仅发送AT四字节，新RX=0、新UART错误=0，未发GMR，版本仍UNKNOWN；完整Flash/options前后完全一致。该结果不证明A损坏或一定是旧AT版本。原件保留，不重试原卡。

查询权限完全沿用[R2](AUTH-B5-ESP-GMR-001-R2.md)与[R1](AUTH-B5-ESP-GMR-001-R1.md)：一次SDK连接、180秒硬限，AT一次成功后才GMR一次，UART_DR最多12字节，115200/8N1不变。禁止Flash/options/配置/GPIO/波特率写、工具halt/go/reset、ESP升级、Wi-Fi/TLS/MQTT命令及B5START。新R3工具只更换卡与现场绑定，UART查询逻辑不变。

## 负责人一次完成

1. 关B/C J5，拔C USB（当前应断开）及J-Link电脑端USB，确认板/ADS/屏/ESP灯全部熄灭并等10秒。
2. 记录A原来的天线/针脚方向，拔下A另放并标记A。仅当备用B是相同2×4针ESP-01/ESP-01S接口、VCC/GND和方向都能确定时，按原方向完整插入；不能确定就停，不试反插、不加5V。A保留，不刷写、不丢弃。
3. P5/P7/P4/P6/CAN/地/BOOT及源/导联不动，JTAG留C。仅恢复C原J5及J-Link电脑端USB，B保持断电、C USB_UART断开。
4. 为与A的R2查询采用相同的正常启动准备，仅短按C实体RESET一次，随后不再复位。工具核验仍ROM/HALT就停止，不能为了读版本反复复位。
5. 一次回复“备用B已更换，方向已核对，全暗10秒，C已复位一次，J-Link在C，C J5，B断电，C USB断开”，并抄B可见型号（看不清写未知）。

工具只在完整C身份/Flash/options、CPU正常Flash及DISARMED均通过后查询，完整记录回应字节、版本或失败原因；结束匹配完整Flash/options及DISARMED。查询/监督失败不重试、不自行恢复。MEM-AP/SDK连接与R2相同，不重新Configure，不接电脑串口。

若B响应，结论仅为“替换后的模块及插接状态下AT通路可用，版本实读为…”，不单凭一次换件认定A损坏或唯一根因；重插也可能改变接触状态。若B仍无响应，回到供电/EN/启动/实际信号通路补证，不刷两块模块碰运气。G3首次失败仍冻结，上云窗口另行决定，不因GMR成功自动启动。

精确工具/卡/测试SHA见[B5-ESP-GMR-R3-PREP](../evidence/B5-ESP-GMR-R3-PREP/bindings.json)。原件均在现有受限EFS，Git不含UID、Flash、UART原码或凭据。

型号资料采用[安信可ESP-01S官方规格书](https://aithinker-static.oss-cn-shenzhen.aliyuncs.com/docs/Public%20Document%20Center/WiFi/esp8266/Specification/ESP-01S%E8%A7%84%E6%A0%BC%E4%B9%A6-20250802.pdf)：DIP-8、3.3V供电及默认115200仅为型号资料，不能代替对这块备用模块的实际GMR查询。
