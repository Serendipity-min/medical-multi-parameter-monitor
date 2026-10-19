# H2 CAN_ONLY_BENCH

只用于A/C非人体、完全离线验收。完整联网候选的main/platform、ESP/AT/TLS/MQTT库和配置读写实现均不参与链接。本目标不覆盖原候选输出。

```text
python gateway/physical_can/bench_build.py --host
python gateway/physical_can/bench_build.py
python gateway/physical_can/tests/test_flash_plan.py
```

输出在忽略的`build/bench/`，时间戳原始证据在`evidence/h2/`；失败不覆盖。C链接硬限制前64KiB，实际镜像的受影响扇区、向量和load地址另作检查。24KiB堆/8KiB栈预算沿用原候选。

控制台仅USART1 PA9/PA10，115200 8N1。C板USB232/CH340C对应此接口，P6切换的USB_SLAVE数据是另一路。只初始化USART1与CAN1，默认控制器正常接收但不运行协议、不发送NMT。独立供电检查时不得发送S。

| 命令 | 行为 |
|---|---|
| S | 两板静态、电源及身份门禁通过后，首次启动真实Gateway栈并单次提交START |
| G | 无故障时显式重建Gateway协议/CAN，清除bench时间使能，再提交START |
| T | 已启动后显式开启固定测试epoch及0x100 TIME；所有诊断均标为BENCH_TEST_TIME_UNTRUSTED，不是SNTP时间 |

其他字节不提供网络或配置功能。无时间/无传感器不填入示例值；Node-B没有本地协议实例/生产者。真实TSR.TXOK后才计NMT成功；Host策略注入单列为模拟。Bus-off、发送锁止、意外B帧或禁用281触发锁止；命令不能解除故障停止门禁。

每秒诊断包括PCLK1/BTR、TEC/REC/LEC/BOFF、实际TXOK计数、701 Boot-up/OP心跳、181/381/481/681等帧的计数/首末时刻/周期范围/最后8字节、RPDO镜像、质量/代际/新鲜度、Adapter/Router本地产物身份/有效性/来源及丢弃/调度积压计数。原始未授时镜像不等于有效监护数据。USART输出采用有界队列，溢出单列，不阻塞CAN；不能把诊断缺帧当作总线零丢帧。

## 下载与恢复门禁

先核对身份并只读备份A完整Flash两次，保护本地原件，且两个摘要必须一致。A应用使用同源Keil镜像，禁止调用工程默认整片下载设置。C按用户指令不做Flash整片备份；只核对sector7（0x08060000）和既有配置宏指向sector11（0x080E0000）的整扇区及前312B摘要，不保存正文。

`flash_c.py`是C/COM15专用受限入口，只有正确的已提交源、ARM镜像SHA、A已验证备份、外部身份源及现场C角色核对全部通过才可进入下载。只调用非空明确的Extended Erase扇区列表（最多0..3），不使用None/空列表、mass erase或RDP解锁；回读应用、保护区及选项寄存器。CLI只在当前H2现场角色门禁通过后调用，不能用它绕过批准步骤。

既有`ai_serial_console/tools/flash.py`使用固定的其他镜像和未限定扇区的erase，本轮不调用、不修改该工程，也不调用MCP固定擦除烧录工具。旧脚本的UID字面量只由外部身份源在内存读取，不能复制入库。

若下载失败或校验不符立即停止，不自动复位运行或重刷。A恢复使用受限目录内同一设备的备份，先核对身份/只恢复本轮改动扇区；C的原配置须全程保持摘要一致，后续恢复应用也仅用已核验本地旧镜像及明确应用扇区，不能用整片擦除。任何实际恢复必须记录，不宣称从未执行的回滚已成功。
