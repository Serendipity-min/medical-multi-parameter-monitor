# P6_V1_CLOUD_TEXT_TTS_HANDOFF

合同：MPM-P6-V1-20261012 v1.0。日期：2026-10-12（Asia/Shanghai）。

本回执交付本地隔离软件成果。**真实豆包接入未完成、生产部署未执行、喇叭未验收。** 用户最新指令为“暂时不同意 PR，提交到 P6 分支即可”；因此不创建 PR、不合并，推送分支后停止，等待后续优化安排。

## 1. 阶段裁定

| 阶段 | 状态 | 结果与边界 |
|---|---|---|
| A0 | PASS（本地隔离预检） | GitHub 固定 P4 精确匹配，独立 worktree/分支建立；原工作区保留。生产服务/Nginx/入口、真实账户与权限未核验，不声称完成云端现场预检 |
| A1 | PASS（MOCK）；REAL_MODEL_BLOCKED | 本机真实 Web → 独立 FastAPI → Mock/事实 → 可见回答、失败/取消/播报开关；真实豆包请求 0 次 |
| A2 | PASS / SIMULATED_DOWNLINK | 真实隔离 Mosquitto → 模拟 Gateway，turn_id/事实摘要一致、QoS1、不 retain、去重/寿命/频率约束 |
| B1 | PASS / HOST_VERIFIED | 默认关闭的 coreMQTT 下行适配、TW-TTS 脱机驱动、Host/隔离 Broker/默认与启用 ARM 全量构建；无实际 UART/开发板/音响验收 |

“PASS”只适用于表中范围。Mock 不等于真实豆包；Broker PUBACK 不等于 Gateway 业务成功，更不等于喇叭播放完成。

## 2. 精确提交、工作区和 GitHub

- 固定 P4：`67f5f57bd82c6e326e9e78ec9540481c80105e5f`。
- 独立分支：`dev/p6-cloud-ai-text-tts-v1`。
- 独立 worktree：`E:/medical-monitor-p6/p6-cloud-ai-text-tts-v1`。
- A 首次闭环提交：`e9e48f26a534e9e30c7d8abcdd5716ee6a69cfd0`。
- A 配置模板/云端与 MCU 字符边界对齐：`0654f31053c4c33b8a292e6e23d5748ef70ae565`。
- B 驱动/适配提交：`41988c88edcb0b486447b016409742a530597bab`。
- B 超大报文断言纠正、**最终受测源码 SHA**：`9012a2edfed3c74613bc2782b13ea6d6f4c58628`。
- 本回执、最终日志和证据在后续文档提交保存；不将尚无法自引用的回执提交 SHA 冒充受测源码 SHA。精确运行 SHA 与文件 SHA256 见 [checks.json](cloud/evidence/p6-v1/checks.json)。后续文档提交不改变受测 C/Python/TypeScript/CSS 源码。

GitHub [PR #6](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/6) 已在 2026-10-10 14:33:53 合入 P4，合并父提交为 `8dee339491cfd4edc468bb9451511d421f26db5e` 和 `88a993cb2dad828d2d13438445a67324e10f71d0`。历史完整 Gate 是绑定旧受测提交的条件通过，不能替代本轮或临床/硬件验收。已核对固定基线的 Transport/Hub/Web/CI 和相应历史进度，未继承过时文档“PR #6 仍 Draft / P6 是 FreeRTOS”的状态。

本轮远端复核：P4 仍为上述固定 SHA；main 仍为 `50699048010c57ba10f8573461844c525b022a07`。没有更新、提交或推送这两个分支。原工作区 HEAD 始终为 `47e59a67c949255d35b3f1e7e0f12459407d0ebc`，本地 P4 指针仍为 `8dee339491cfd4edc468bb9451511d421f26db5e`；fetch 仅刷新远端引用并取得固定对象。

首次 A0 因原工作区 5 个已修改文件、387 个未跟踪文件而按合同停止；用户随后明确批准保留全部改动并另建 worktree，之后才继续。最终只读核对原工作区仍有同样 5 个已修改文件，未跟踪计数变为 397；本轮未向该工作区写业务/证据文件，未调查或处理新增资料来源，未 reset/clean/stash/覆盖/搬迁。该变化不混入 P6 分支。

## 3. 修改范围与行为

**A 组**：新增 `cloud/ai/` 独立服务、依赖和普通功能夹具；新增 AI 模态面板/独立 CSS，`main.ts` 只组装组件；Vite 增加独立本机 AI 代理；提供未应用的独立 systemd/Nginx 模板。服务只读服务端 `/ws/v1/monitor`，不接受浏览器读数，不写 Hub/Telemetry。当前数值确定性生成，节点/网关/来源/session/seq/单位/采集时间独立核验；INVALID/STALE/OFFLINE/REPLAY 不当作当前有效值，MOCK/synthetic 明示。

模型适配使用官方 HTTPS Chat Completions、服务器外部环境注入密钥和模型 ID，并要求账户与预算批准标志；默认 MOCK，每进程真实请求硬上限 5。**V1 模型解释是有限模板选择**（数据质量/一般复测建议/项目架构），自由生成文字不得直接显示或播报。不是开放临床聊天，不提供诊断、处方、药量、治疗或设备控制。真实 HTTP 格式/输出拒绝测试均使用假响应，不计真实模型接入。

AI 独立 Bearer 鉴权、4096B 正文/500 字符问题、4 并发、全局 12 请求/分钟、128 个有寿命会话、每会话 4 轮，网关切换清空上下文。第三方错误返回固定码，不输出凭据/原异常。浏览器模型答案/事实用 textContent，AI 令牌只留在本页内存；没有麦克风、录音、ASR 或音频上传接口。

独立 `voice/reply` 契约：固定设备/Topic、QoS1、不 retain、至少 5 秒间隔、15 秒寿命、完整 UTF-8 边界、最大 240B 文本/294B 业务载荷。显示回答与短播报共享 turn_id/事实摘要；摘要是来源关联标识，不是签名。云端本轮只允许 loopback 隔离 Broker，凭据/ACL 与原遥测客户端分离。不开生产 Broker 权限。

**B 组**：新增 `p6_config.h`、`p6_voice.[ch]`；Transport 增加开关内的独立订阅标识/单条入站 QoS1 状态记录；SUBACK 精确匹配且授予 QoS1，不更改原出站 pending_id/PUBACK 判据。回调只核验入播放槽，原遥测返回值/Router ACK 保持既有语义。顺序高水位与 8 个 turn_id 在 RAM 中跨 MQTT 重连保留；异常/过期/乱序/重复/非法 Unicode/设备/Topic/QoS/retain 拒绝。

TW-TTS 采用 `FD + length(text+2) + 01 + 04(UTF-8) + text`，无末尾 XOR。9600 8N1 的硬件绑定未实施；发送异步、每次最多 32B、发送/接收确认/播放等待均有界，错误锁定 FAULT 不自动重播。0x41 接收与 0x4F 完成分别计数，首字节前再次检查消息寿命。所有驱动状态由主循环单一所有者维护；IRQ 接收缓冲/引脚适配留待硬件窗口。

`GATEWAY_P6_VOICE=0` 默认关闭；即使启用，没有已核验 writer 仍不订阅/不绑定 UART。既有 USART1/USART3/USART2 保留，不操作 GEC6818、开发板、Flash/sector7。没有 FreeRTOS。新增 ARM 参数只做独立脱机构建。

CI 仅修正 P4 已为 coreMQTT 的选择条件并保留原必需检查，增加普通 P6 用例；未取消步骤、修改安全门或启动扫描。当前 push 触发清单未包含 P6，且本轮不建 PR，因此本回执的 PASS 来自真实本机检查，不能写为 GitHub CI PASS。

首次推送文档提交 `200d1e7d3478da735369105b7d5a97158f96dfb2` 后，GitHub 自动产生 [security-gate.yml 失败记录 38246581405](https://github.com/Serendipity-min/medical-multi-parameter-monitor/actions/runs/38246581405)，状态 completed/failure，**jobs=[]**；CLI 提示“likely failed because of a workflow file issue”，不是扫描结论。固定 P4 同样已有 [失败记录 38031377591](https://github.com/Serendipity-min/medical-multi-parameter-monitor/actions/runs/38031377591)，同样提示工作流文件问题。本轮该工作流对固定 P4 无差异，未启动或运行任何 Gate job；不能把此自动失败隐藏或写为 GitHub 全绿。具体工作流修复留待后续明确安排，不改安全门政策。

受保护范围 `gateway/canopen`、`gateway/data_model`、`gateway/storage`、`gateway/third_party`、`platform.c`、312B 配置定义及 Security Gate 配置对固定 P4 的 Git diff 退出码 **0（无差异）**。原 Backend 源码/依赖未修改。

## 4. 最终测试与退出码

全部在独立工作区运行，源码绑定 `9012a2edfed3c74613bc2782b13ea6d6f4c58628`；[最终日志目录](cloud/evidence/p6-v1/logs/)和[检查总表](cloud/evidence/p6-v1/checks.json)保留真实退出码。

| 检查 | 实测结果 | 退出码 |
|---|---|---:|
| coreMQTT 普通 Host | 42 PASS | 0 |
| coreMQTT 固定来源核验 | 9 pinned files PASS | 0 |
| 来源/白名单普通用例 | 6 PASS | 0 |
| EMCY console 专项 | 5 PASS | 0 |
| CANopen 协议 / Router / 重启负向 | 12 / 11 / 17 PASS | 0 |
| Canonical C → Backend | 41 消息，schema v1 PASS | 0 |
| 原 Backend Pytest | 28 PASS | 0 |
| 原 Web 状态测试 / 生产构建 | 11 PASS / 构建成功 | 0 / 0 |
| AI 事实/鉴权/会话/模型 HTTP 假响应/只读 WSS | 38 PASS | 0 |
| A2 真实隔离 Broker/模拟 Gateway | 4 PASS / SIMULATED_DOWNLINK | 0 |
| P6 驱动/coreMQTT Host | 31 PASS / HOST_VERIFIED | 0 |
| B1 真实隔离 Broker + coreMQTT + 模拟 UART | 15 PASS | 0 |
| 原隔离 Broker 对照/保活/PUBACK | 30 PASS | 0 |
| ARM 默认 / P6 启用全量编译和链接 | 两份构建成功 | 0 / 0 |
| 最终普通检查收集助手 / 证据收集 | PASS | 0 / 0 |

原 Broker 对照仍是既有固定 `8dee339` Paho 与活动 coreMQTT 矩阵，不冒充新的 `67f5f57` 固件逐字节对照。B1 同时验证真实 Broker 下正常/延迟/错号 PUBACK、合法与非法下行、重连、去重、过期和超大 MQTT 报文 drain 后遥测继续。

**失败不复写**：新增超大报文用例首次退出 **1**，错误预期“超大包必须断开”；官方固定 coreMQTT 实际 drain 后继续，故 wait 8s 超时。未改上游或缓冲尺寸，纠正为“无 UART 执行、正常匹配 PUBACK 和遥测续传”，最终通过。首次失败记录见 [b1-oversize-first-failure.json](cloud/evidence/p6-v1/b1-oversize-first-failure.json)，对应冻结源码 `41988c88…`；成功记录另存。浏览器 CLI 初次等待失败也未算作 PASS，后用显式 DOM 事件验证，见 [browser.json](cloud/evidence/p6-v1/browser.json)。

浏览器证据：[桌面 Mock 回答](cloud/evidence/p6-v1/ai-mock-desktop.png)、[移动端面板](cloud/evidence/p6-v1/ai-mock-mobile.png)、[停止 AI 后原监护页](cloud/evidence/p6-v1/monitor-after-ai-stop.png)。原 Backend 使用 MONITOR_TESTING=1，WSS 空/离线快照仍从 5 帧增长至 264 帧、health 200；这是隔离功能证据，不是真人监测/生产运行截图。本轮持有的浏览器、本机 AI/Backend/Vite、Broker/Gateway/代理均已停止。

## 5. ARM 资源、产物与限制

真实 `.text/.data/.bss` 来自 `arm-none-eabi-size -A`，不是混用 GNU size 汇总列。单位 B；完整 map/编译器局部栈与哈希见 [resources.json](cloud/evidence/p6-v1/resources.json)。

| 资源 | 固定 P4 本机重建 | P6 默认关闭 | P6 启用、未绑定引脚 | 启用增量 |
|---|---:|---:|---:|---:|
| `.text` section | 35216 | 35216 | 36964 | +1748 |
| `.data` | 88 | 88 | 88 | 0 |
| `.bss` section | 87348 | 87348 | 87796 | +448 |
| 预留 heap/stack section（含对齐） | 32772 | 32772 | 32772 | 0 |
| 链接后未分配常规 RAM | 10864 | 10864 | 10416 | -448 |

GNU size 汇总 text/data/bss：默认 **35624/88/120120**，启用 **37372/88/120568**；汇总 bss 包含 heap/stack 预留。预留 heap 24576B、stack 8192B 保持不变。RX **512B**、Flash 配置 **312B** 保持不变，无新动态堆分配。编译器局部栈：p6_voice_receive 48B、mqtt_event 64B、gateway_mqtt_open 656B、main 2296B；不能据此宣称真机调用链动态峰值、CPU/协作延迟或 UART 时序已测。

| 产物 | SHA-256 |
|---|---|
| 默认 ELF | `1d0ac7ccf52338ad179e8fca174f346ce7351c4a254dd12dda005663da28a018` |
| 默认 BIN | `a83ce9ff20cc5122e5f25960e697e8311312d5d1e9287ee89b1d9db0d08c5010` |
| 启用 ELF | `de587cef3f86d6494214e13a0444eeadf96b48ada5c0f9a0287513b1787c839c` |
| 启用 BIN | `2bfc8e07384e0e061c945fea5d265c48b733f685d76cb69f0b23c61d7c498024` |

产物留在本机 `gateway/mqtt/build/` 与 `gateway/mqtt/build/p6-enabled/`，未上传服务器/烧录。默认资源与基线一致，但默认 ELF/BIN **不与重建基线逐字节相同**，不能写“复用原二进制”；源码回调条件已适配，行为以真实回归为依据。原固定 P4 及基线产物身份独立保留。

## 6. 后续优化与待授权事项

1. 真实豆包：确认服务器安全配置、账户开通、模型 ID 与明确小额调用预算，再做不超过 5 次真实验证；现为 **REAL_MODEL_BLOCKED**，不能依据 HTTP Mock 用例准出。
2. 当前问答范围受限模板；更广的项目知识与自由解释需要新的输出核验/知识来源设计，不能直接放行模型自由文字。
3. 云端正式服务/Nginx/公开入口与生产 Broker ACL/TLS 都未验证/部署；本轮独立模板不代表已安装。任何服务器文件须另按本机中转门禁执行。
4. 实物 TW-TTS V1.0 与官方 V0.21 手册的对应关系、空闲 UART/电平/供电、IRQ 接收缓冲、硬件 0x41/0x4F、喇叭出声、动态 RAM/栈/CPU 均待新硬件窗口。
5. RAM 去重跨重连有效但不跨掉电；可信 SNTP 时钟、防重播持久化及 FAULT 恢复策略仍有限制，不改 sector7 布局来掩盖限制。
6. 正式 Security Gate、真实 Broker、硬件烧录/接线、24h soak、PR 创建/审查/合并均未执行。本轮按照最新指令**只推送 P6 分支，不创建 PR**；未来恢复 PR 需用户再次安排，届时保持 Draft。

参考：[方舟官方接口与鉴权](https://docs.volcengine.com/docs/ark/base-url-and-authentication?lang=zh)、[TW-TTS 官方开发者手册](https://www.haohaodada.com/new/bbs/forum.php?extra=&mod=viewthread&tid=2621)。本次阶段软件交付完成即停止，不自行签署阶段结项或启动下一窗口。
