# AUTH-B5-G3-HW-PREP-001 R1｜一次C只读核验与冷态转接，待批准

`enabled=false; owner_approved=false; executions=0; B5START=0`。本卡不是G3联网许可。当前任务只批准工具、附件和卡片准备，下面的设备读取、断电及转接均等待负责人明确批准。不得沿用已经消费的G2-B写入许可。

## 前置与一次C只读范围

最后登记为J-Link在C、C由J5供电、C USB_UART断开、B断电。ESP保持在板供电，**未隔离**，其自主联网状态UNKNOWN；本卡申请在板例外，不把UNKNOWN改成已隔离。若当前状态不同，先停止补记事实，不自动改变电气状态。

固定入口 `b5_g3_joint.py --c-check --authorization <受限EFS一次性授权>`，由独立父进程监督，90秒硬限、一次连接/关闭、完整Flash和options各读一次；本卡不重复G2-RO双备份。全部私有UID、Flash/options与SDK原始返回码只存受限EFS。

核对F407/1MiB、实际私有UID、保护位、PCSR/VTOR/DHCSR及Fault/复位标志；CPU必须在应用Flash正常运行。完整Flash `0x08000000+0x100000` SHA应为 `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e`；options `0x1FFFC000+16` SHA为 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。C42552B BIN SHA为 `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`，DISARMED四字节必须全0。sector3/7/11通过全片逐字节身份覆盖，不写任何扇区或options。

工具固定SDK和地址白名单，禁止DAP访问、Flash解锁、强设寄存器、halt/go/reset、AT和串口命令。关闭仅在刚验证的健康Flash状态下设置SDK退出续跑策略；这不是独立Go命令，也不保证连接没有电气扰动。ROM/HALT/意外复位、身份漂移、DLL错误或短读任一出现即停，保存真实回执，不重试、不复位、不重刷。首次只读结果必须实际PASS后才能进入下面的冷态步骤。

## 通过后一次完成的人工步骤

1. 关闭B、C的J5电源；如C USB仍接着则拔下；拔下J-Link电脑端USB。确认B/C板、ADS模块、屏和ESP指示灯全部熄灭，等待10秒。若仍有亮灯，停止，不在有电状态转接。
2. 只将整只带定位的JTAG排线从C移到B原调试接口。方向不能确定就停止，不改跳帽或单根调试线。
3. C恢复原J5供电，将C的 **USB_UART/USB232串口口** 接到电脑，不能使用USB_SLAVE；保持原供电选择。B恢复原J5供电，J-Link电脑端USB先保持断开，观察B屏约10秒，再接回J-Link电脑端USB。
4. 一次回报：实际COM号、J-Link已在B、B/C均J5供电、B屏是否持续刷新及有无异常；同时只核对现有源为普通ECG60、1.0mV、电池且充电USB断开，红R→RA、黄L→LA、绿F→RL/N、LL空置。未确认项写未知，先不切模式或换导联。

CAN H/L及两板独立GND保持原状：B CAN1↔C CAN2，B P6 RX↔PA11/TX↔PA12，C P4 RX↔PB12/TX↔PB13；A段、INMP441、TTS及人体断开。B开发板USB不接。历史60.8Ω是历史记录，本卡不新增测阻，不把主动RLD接地或短接LL/RL。

完成后保持现状，**不按任何RESET、不发送B5START、不查询ESP**。断电转接不作为B5独立冷启动或ROM根因试验，也不据此签相应PASS。

## 与未来G3的接口

未来还需另批[G3 R4](AUTH-B5-G3-CLOUD-WINDOW-001-R4.md)，在B只读和云观察器均就绪后，工具才提示负责人仅按C实体RESET一次，随即回报；B不复位。该动作属于未来G3启动事务，本卡不允许现在提前执行。G3启动前所有现场事实、COM、工具/卡SHA及新鲜C回执重新绑定，授权不跨窗口复用。

本卡只读与转接通过也不允许烧录、sector3写入、云服务启动/恢复、ACL变更、真实联网或账号撤销。默认私有模板保持禁用；源码/白名单/环境及卡SHA见[冻结清单](../evidence/B5-G3-PREP/bindings.json)。
