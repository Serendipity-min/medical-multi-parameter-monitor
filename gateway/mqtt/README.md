# Gateway-C MQTT 传输与阶段二 CANopen 汇聚

P5 分支的 STM32F407ZG 裸机运行固定 coreMQTT v2.3.1 / MQTT 3.1.1；ESP8266 原厂 AT
仍提供原有 SSL Socket。P4 继续保留 Hardened Paho 基线；P5 真机合成Smoke/Wi-Fi恢复已通过，全阶段待审。
不需要商家 MQTT AT 固件，也未刷写 ESP8266 启动镜像。当前模块 AT 2.3.0.0-dev / Bin 2.2.0 ESP8266_1MB。
这只描述 AT 构建，未通过 ROM 工具确认物理 Flash 容量。

## 硬件与构建

Wi-Fi 插座实际使用 USART3 PB10/PB11；本机调试为 USART1 PA9/PA10、COM15。
P5 当前接线已在前序记录核对，勿依据旧 P1 描述盲目改接。
`python gateway/mqtt/build.py` 使用本机 ARM GNU 14.2、既有 ST 标准库与 HSI 16MHz。
输出 build/gateway_mqtt.bin；本项目 C 代码以 -Wall -Wextra -Werror 构建。
coreMQTT 固定 commit `2beef04725328923e05e576b884212d53ec97af7`，原字节、MIT 许可和哈希见
`../third_party/coreMQTT`；构建前离线核验 active 源白名单。Paho PATCH-01/02/03 与清单原样保留。
主循环、CANopen、模型和 Router 未改。QoS1 发布成功必须经过匹配本次 packet ID 的 PUBACK；
SEND OK 或 MQTT_Publish 返回成功均不足以 ACK Router。一个 context、一个在途 QoS1 记录。
当前资源与测试见 [P5 阶段材料](../../doc/P/04_第四阶段_P5_coreMQTT裸机迁移/README.md)。

普通测试：`python gateway/mqtt/tests/run_p5_host_tests.py`，详情见 [tests/README.md](tests/README.md)。
2026-10-08获准窗口B01/B02/B04通过，原1MiB完整Flash已恢复并独立回读一致；B03和统一Security Gate未授权。
详见[真机报告](../../doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/P5_真机合成Smoke与WiFi恢复报告_20261008.md)。
30秒断网使原32帧缓存满载，最后lost=203，不代表无损采集。动态资源对照仍待审。
下文硬件/历史 acceptance 命令仅供获准窗口参考。

P0 补充：保留 assert，Gateway 侧固定输出 `GW ASSERT_FATAL` 后停机；UART 每字符最多
8192 次就绪检查，禁止用 stdio/OS signal、关闭 assert 或自动复位来消除告警。现场 UART
不可用时跳过输出，`gateway_assert_latched=1` 仍可供后续获准调试观察。软件单测与 ARM 反汇编
已验证实现路径，实际串口与停机行为仍待硬件窗口。隔离 Mosquitto 的 30 项普通对照已通过，
详见 [P0 补充证据](../../doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/P5_P0_证据与资源补充_v1.0.md)。

## 配置与烧录边界

1. 烧录前用 J-Link 对原始 1MiB Flash 双读并验证一致，备份放在仓库外；记录哈希。
2. 私有 Wi-Fi JSON 含 ssid/password；MQTT JSON 含 host/port/username/password/client_id/gateway_id。
   `python gateway/mqtt/provision.py --wifi <私有JSON> --mqtt <私有JSON> --output <仓库外新bin>`。
   支持端口 8883、GW-C-001；当前不支持需要 AT 转义的字符串，遇到则拒绝。
3. 链接脚本为程序保留前 896KiB，配置独占最后 sector 7。程序地址 0x08000000，配置地址 0x080E0000。
   此配置是开发样机明文 Flash，不具备抗物理读取能力，不能作为量产凭据方案。
4. ESP 的 client_ca 分区需要目标证书链的可信根。先双读备份，确认分区表，再按官方 ESP-AT PKI 格式写入并整块回读。
   本次只改 client_ca，不读取或写入 client_key，不更换 AT 固件。根证书变化需重新核对，不关闭校验。
5. 临时烧录后逐块 verifybin。恢复时必须恢复程序涉及扇区及配置 sector 7，并对完整 1MiB verifybin；仅恢复 sector 0 不够。

阶段二验收后原始1MiB已恢复，并额外整片回读一致。此次用户重新上电后CPU进入系统ROM启动程序，调试器明确设置Flash向量表/栈/入口后才能运行项目；未修改启动引脚或Option Bytes。后续需要独立上电运行时先核对BOOT0选择，不能把J-Link启动成功视为上电启动已验证。

当前网络实现：SYSSTORE=0，STA 加入 2.4GHz，SNTP 时间有效后开启 authmode=2，CCN/SNI 同时绑定外部主机，SSL:8883。
该模块 SNI 优先，仅错误 CCN 的负向测试不足；CCN/SNI 同时错误和不可信 CA 均已证明连接失败。
MQTT Keepalive 15 秒，状态/标量 QoS1、波形 QoS0，Gateway retained ONLINE 与 OFFLINE LWT。
SSL 被动接收需先查 CIPRECVLEN，无数据直接 CIPRECVDATA 会 ERROR；MQTT 二进制按明确长度接收。
当前数据来自两个独立 CANopenNode 测试生产者，经CAN1静默loopback进入Gateway模型；ECG250Hz、PPG/RESP50Hz，一秒批次。RR对象已预留但保持INVALID。真实Node及正式RR算法尚未接入。
CANopen OD/PDO和RAM缓存已在 [阶段二](../canopen/README.md) 实现，旧占位头已由统一模型替代。

## 验证

`python gateway/mqtt/acceptance.py --config <仓库外浏览器配置> --port COM15 --ssh-alias tencent-codex --output <结果JSON>`。
需要 pyserial、websockets；该命令会执行本地 Wi-Fi 断网和项目 Broker 重启，必须在获准测试窗口使用。
调试口 D 触发断网并等待 30 秒后自动恢复；不提供云端传感器控制。
[evidence/hardware-acceptance.json](evidence/hardware-acceptance.json) 保存真实状态转换；截图与浏览器结果位于同目录。

以上 acceptance.py 与 evidence 为第一阶段历史验证。当前使用 gateway/canopen/tools/board_acceptance.py；升级已运行的本阶段固件时加 `--quiesce`，先让旧固件退出Wi-Fi再烧录，避免ESP仍等待未完成的CIPSEND数据。完整阶段二接口、故障日志和准出记录见阶段二目录。
