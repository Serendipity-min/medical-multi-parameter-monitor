# VOICE-002 V0/V1 核对

2026-10-22。仅在 `codex/c-voice-cloud-20261022` / `E:/medical-monitor-c-voice-cloud` 写入。
旧 H3 和旧语音租约均已释放，新租约保存于仓库外受限目录。根工作区未提交文件不触碰。

## 两源身份与取舍

- GitHub 私有仓库已实查。H3 HEAD `a5cdd5b0b1ad48108fd631136e9de69e30582f2d`；tag object `8a9265146a293f8a020df39863943e9de4adce68`。
- P6 HEAD `1a5d7d16a1df00a1195a6754c35d33f4380324a6`。merge-base `67f5f57bd82c6e326e9e78ec9540481c80105e5f`。
- 以 H3 建 worktree，只取 P6 的 frame/queue/UART 及原 Host 用例；不整体合并、不以 P6 Backend/AI/MQTT 覆盖 H3。
- `evidence/V0-remote-refs.txt` 冻结全部保护分支；`V0-source-diff.json` 保存实际文件字节差异。P6 不含 physical_can；原 H3 Router/CAN/Adapter/NIBP 完成协议保留。
- 原 H3 mqtt_event 拒绝所有 PUBLISH。新增行为只在 `MP_CLOUD_VOICE` 下存在；默认目标仍可逐字节复现 43172B 原正式镜像 `b9b25b18…`。

## 资源与协议

USART2 PA2 TX→模块 R、模块 T→PA3 RX，AF7/9600/8N1；USART3 PB10/11 和 CAN1 PA11/12不复用。
P3 必须隔离板载 RS232/485 输出；PA2 还连 ETH_MDIO，当前目标无 ETH 初始化。USART2 IRQ15 低于 CAN1 IRQ1 和 ESP IRQ0。
原 32B UART SPSC，主循环每次最多写1B、读4B，无 malloc；只开一个 TTS 槽。

P6V1 54B 头+1–240B文本，精确 C topic、QoS1/nonretain；签名字节并不存在，digest仅绑定事实。
云端保留原 BMP 字符白名单并补拒绝非字符；C 网络入口取同一交集，本地 TTS 编码能力不倒退。
网络文本不允许内嵌参数标签；v1 音量为本地独立管理命令。

fresh SNTP 成功、当前 SUBACK QoS1 和本地按键三条件同时具备才允许一条云短句。
新会话/手工许可时间下界为当前UTC+1001ms，拒绝未来/旧会话/过期/剩余不足1s/回退时间。
保留8个turn和单调issued高水位；入槽成功才消费一次许可。重连不恢复许可。
冷启动RAM丢失由重新授时+新下界防止旧包恢复；该边界信任既有SNTP/ACL，不能宣称具备认证时间或抗恶意NTP能力。

语音构建使用官方coreMQTT入站记录和PUBACK，回调内完成校验/复制，不保留RX指针；上行单在途和5000ms不变。
错误业务载荷丢弃并计数；超出512B库缓冲或损坏MQTT分帧仍可能按库规则断网，不声称能无损接收任意恶意字节洪泛。

## 云端只读结果

`V0-server-readonly.json`、`V0-formal-roles-tls.json`：H3 runtime仍为 `runtime-b8fbb14b5c35`，AI/Backend PID未变。
TLS8883链和名称验证通过，8884无监听；未更改安全组，不重复旧8884外网闭合推断。
正式C限权遥测角色当前没有语音read；需要只增加精确voice/reply read，另建仅该topic write身份。
已保存实际ACL/password/config/env/Nginx SHA。两个更早只读定位尝试失败（wrapper非直接mosquitto ExecStart），未写服务器；最终按实际wrapper源码定位成功。
实际豆包模型 `doubao-seed-2-0-mini-260428`，服务器账户/预算配置为approved；免费/体验为负责人历史报告，当前余额/费用不推断。

## 验证及边界

原H3 ARM镜像逐字节复现；P5普通42项、IRQ/fresh-SNTP 48项通过，原CAN/Router通过。
Backend/AI/physical Python本轮332 passed、1 skipped、4 subtests passed；最初一轮保留WSS取消异常及Unicode策略测试失败，后者已纠正为原P6交集，前者在未修改Backend情况下复跑通过。
原TTS 3103断言、P6V1 84检查、真实MQTT混合流Host通过；Host UART为假设备，不能证明喇叭可闻。
Web最初新状态导致数量断言5→6失败，已更新语义断言；15项测试及正式Vite构建通过。详见原始日志及退出码JSON。
最终拟下载镜像和链接区间以 `V1-image-resources.json` 为准；ARM栈静态函数帧可查，不能替代运行高水位。

负责人最新指令：不另起隔离Broker测试，V2记为OWNER_SKIPPED；第二份合同后续提供，B不介入。
实板接线最新报告与旧拆线记录不同，以新现场核对为准。尚未把任何Host结果升级为真实语音PASS。
