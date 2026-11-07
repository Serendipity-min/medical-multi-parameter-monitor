# FIELD01 隔离链路恢复回执

**ISOLATION_SERVER_PREFLIGHT_PASS。** 旧临时服务因达到运行上限退出。新开独立临时 Broker，公网 `28895/TCP` 使用 TLS，`18885/TCP` 仅绑定回环，由 SSH 转发供观察器使用。旧实装制品的 `1883` 保持无监听。独立服务最长运行 2 小时，启动于 2026-11-07 17:38:51 CST。原正式监听身份启动前后相同。

| 项目 | 结果 |
| --- | --- |
| 外部 TLS | 使用历史 C sector3 保存的主机名，从本机验证 TLS 1.2、证书链、有效期和主机名 |
| 网关认证 | 历史 C sector3 记录 CRC 通过。板上归档账户与旧语音 Broker 的账户口令不一致，匹配早期 G1 隔离测试账户。新 Broker 使用该测试账户原有哈希。以档案中的 MQTT 3.1.1 身份登录成功，错误口令被拒绝 |
| 观察者 | 经过 SSH 转发订阅五板遥测树及音频上下行，三个订阅均确认。合成遥测、合成上传及合成下行消息在预期端收到 |
| ACL | 网关越权发布下行、观察者越权发布遥测均收到 MQTT 5 PUBACK 135。新 ACL 限定五板遥测和两个音频主题 |
| 记录器 | 带 `--audio-metadata` 的本地订阅和五板网页 WebSocket 自检通过，浏览器收到 24 个快照，子进程退出。离线 MC01/MR02 测试只提取元数据，现场音频尚未发生 |
| 现场 | 当前 C 读回、ESP8266 握手、热点和断电接线核对仍待执行。实板 START 为 0。隔离语音 worker 与真实 TTS 尚未运行 |

[网络回执](../../build/field01-isolation-issue8/network-preflight-public.json) · [服务状态](../../build/field01-isolation-issue8/isolated-service-public.txt) · [记录器回执](../../build/field01-isolation-issue8/receiver-preflight-public.json)

恢复操作仅使用独立临时 Broker。它复用既有证书材料，由 systemd 以服务凭据交给非特权进程。原正式服务与配置、历史服务定义、板上凭据均未写入。上一轮的 [PRECONDITION_BLOCKED 回执](FIELD01-RESULTS.md) 保留为当时记录。

## C 新鲜只读回

[脱敏回执](../../build/field01-isolation-issue8/C-readonly-public.json)记录原生退出码 0。J-Link 核对历史 C 身份后完成两次独立读取并正常关闭。两次 Flash/Options 一致，整片与上次实装逐字节相同，sector3 CRC 有效并与已通过隔离认证的档案相同。板上写入为 0。读回期间独立 Broker 仍 active，两端口均监听。现场阻值回执及 ESP 握手仍待核。

## C 探针安装与现场就绪

现场断电实测 C1–A1–E1 为 40 Ω，C2–B1–D1 为 40.9 Ω，仅作为受控诊断端接。确认仅 C 上电、J-Link/COM15 都在 C 后安装探针。[分段安装回执](../../build/field01-isolation-issue8/C-probe-install-public.json) 原生退出码 0，sector0/4 的镜像哈希匹配，整片写后回读通过，Options、sector3 和区外一致。原制品回退入口记录在安装档案的受限路径。单次 UART 记录器通过模拟串口边界检查，实际 START 仍为 0。

## 首次上电准备收尾

现场确认原热点联网、非人体输入和值守就绪，K1 对应 PE3。隔离订阅和主机记录器先进入就绪状态。发出上电口令后，主机未在 15 秒的串口打开预算内打开 COM15，控制器退出码 2，观察器退出码 0。主机随后可枚举 COM15，但本次记录器没有保留串口打开异常明细，无法区分枚举时序和端口占用。无 START、T0、K1、串口行或 Broker 遥测。唯一 150 秒窗未消耗，未自动再次上电。[本次准备回执](../../build/field01-isolation-issue8/FIELD01-PRESTART-RECEIPT.json)

第二次准备中 COM15 已预开，隔离观察器也已就绪。主机未见新的 C 启动标记，只在预开约 13.8 秒后收到 C 自身第 45 秒的未武装停止回执。START、T0 和 K1 计数仍为 0，观察器无实板数据。供电是否完全切断仍需现场确认。[第二次准备回执](../../build/field01-isolation-issue8/FIELD01-PREOPEN-RECEIPT.json)

### USB_UART 单独接入观察

主机在五板断电、USB_UART 尚未接入时确认 COM15 未枚举。随后进行被动监听，COM15 出现并打开后收到探针启动标记，串口写入为 0。该记录支持 USB_UART 接入与 C 启动相关，具体供电路径仍需现场确认。本次仍无 START，唯一短窗未消耗。[被动观察回执](../../build/field01-isolation-issue8/COM15-passive-power-check.json)

### 唯一 START 的执行结果

现场确认原 USB_UART 可给 C 供电。将插入 USB_UART 作为 C 上电动作，主机捕获新启动标记并发出唯一 START，C 明确接受。ESP-AT 初始化通过 AT、ECHO、VOLATILE 和 STA，随后 `GW FAIL WIFI`，C 发出停止回执。固件未输出 Wi-Fi 失败子码。T0、C 端 TLS/MQTT、K1 和 150 秒评价均未执行，隔离观察器未收到数据并正常退出。**唯一 START 已消耗。** 断电回执待收。[本次回执](../../build/field01-isolation-issue8/FIELD01-USB-POWER-RECEIPT.json)

### Wi-Fi 失败复核

只比对归档字节，不输出热点名称或口令。上两次成功五板窗口的主机脚本把热点配置临时注入 C 的 RAM，两个成功窗口使用同一份热点配置。此次 FIELD01 探针只读 sector3，历史完整回读及本轮写后验证确认 sector3 保留。sector3 的热点名称及口令与两个成功窗口使用的 RAM 配置均不同。此前服务器验证覆盖保存的 Broker 主机和 MQTT 身份，尚未覆盖 ESP 使用 sector3 对当前热点的接入。若现场开启的是前两次的同一热点，这一差异足以解释当前失败路径。此次 AT 回执没有关联失败子码，当前手机热点参数未经主机现场核实。 [脱敏比对](../../build/field01-isolation-issue8/WIFI-CONFIG-COMPARISON.json)
