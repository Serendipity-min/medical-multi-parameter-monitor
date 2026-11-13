# MR02与隔离环境准备（未部署）

## 录音上行

保留MC01、16kHz、S16LE单声道及544字节封包。新构建允许实际PCM为32,000–64,000字节（1–2秒）；总块数为ceil(bytes/512)，末块length为真实剩余字节。整段/每块CRC覆盖真实PCM，填零仅是封包未使用区域，不计入PCM、不送ASR。旧默认AudioAssembler仍只收固定64,000字节。

隔离音频输入必须来自认证角色、精确`mpm/mic/v1/in`、QoS1且非retain。序号/长度/CRC/装配期限90秒不符拒绝；完成身份拒绝重放。只有完成音频能建立录音session/CRC上下文，浏览器Question禁止新增身份/读数字段。`AudioFactFlow`在ASR90秒预算内只取识别问题，再通过真实事实API问答；300秒整轮期限不变。

## 回复下行

P6V1按原解码、15秒寿命及事实摘要检查后，定向生成MR02。不是把原P6V1搬到MC Topic，也不是放宽旧MR01。新构建只接受新协议，原手动构建仍支持旧MR01。

MR02小端头82字节，文本最大120 UTF-8字节：

| 偏移 | 字段 |
|---:|---|
| 0 | `MR02`，4字节 |
| 4 / 8 | 录音session / PCM CRC32，uint32 |
| 12 / 20 / 28 | issued / expires / fact_timestamp，uint64毫秒 |
| 36 / 40 / 44 | fact_seq / B5网关session / observed_boot，uint32 |
| 48 / 49 / 50 / 51 | node / stream / status / synthetic，uint8 |
| 52 | 固定业务网关 `GW-B5-001`，12字节NUL填充 |
| 64 | 原事实SHA256前16字节摘要 |
| 80 / 82 | uint16文本长度 / 文本 |

流枚举沿用MpStream：SPO2=1、PR=2、NIBP=3、HR=5、RR=7、TEMP=8；角色固定A血氧/脉率、B心率/呼吸率、D物体温度、E血压。状态0有效、1无效、2过期、3离线、4历史；synthetic只允许0或1。

C只有等待当前录音回复时才接受，绑定session和CRC；核对网关、角色、非零摘要及可信UTC，拒绝超过15秒的消息、源过期或不同观察身份。有效回复期限不超过源时间＋5秒/血压90秒；播放中到期、节点离线/代次变化、新血压完成代次到达会请求STOP。无效/过期/历史分支忽略下发文本，改播本地固定“当前读数不可用”。

云端必须验证整份事实digest、选定单个流、规范`can-{gateway_session}-{observed_boot}`与seq，数值文本必须等于可信事实模板。摘要**不是数字签名**，C不保存/重算完整云端事实；信任边界仍是隔离TLS Broker认证及最小角色ACL。PUBACK只证明Broker接收，C本地ACK/DONE和人工可闻是独立后续证据。

## 隔离差异

| 表面 | 本候选要求 |
|---|---|
| 业务ID | GW-B5-001，与MQTT Client-ID概念分开 |
| C | MP_FIVE_APPLIANCE、five-node、P1队列修复；SSL端口拟议28895；持久host/账户仍只读且未修改 |
| Backend | MONITOR_GATEWAY_IDS仅B5、MPM_NODE_PROFILE=five、MONITOR_WAVE_BATCH_DELIVERY=1；独立进程拟议18965 |
| AI | 显式五板profile和隔离WSS地址；拟议独立18966；P6_MODEL_MODE默认MOCK、P6_MQTT_MODE默认DISABLED |
| Web | `vite build --mode five-appliance`，独立产物和入口；`/medical-monitor/ws/v1/monitor`需转到隔离Backend |
| Broker | 独立实例/TLS入口和认证配置；后端loopback拟议18895；ACL仅B5及MC01/MR02精确主题 |
| 事实语音 | 必须由完成MC01录音建立上下文；网页没有该上下文则NO_RECORDING_CONTEXT，不伪造会话 |
| 音频worker | 旧MR01 worker保留原样；新 `cloud.ai.appliance_worker` 使用同一录音上下文和同进程事实API，外部ASR/订阅发布端口已实现但未运行 |

模板：[隔离环境](../../../cloud/deploy/five-appliance.env.example)、[隔离ACL](../../../cloud/broker/five-appliance-acl.example)。空凭据不是可启动配置；没有生成令牌、配置Broker、开放端口或重启服务。模板只是约定，不代表这些端口已可用。

监护`MONITOR_VIEW_TOKEN`授权只读WSS；AI `P6_AI_TOKEN`是调用AI API的Bearer；服务器`ARK_API_KEY`用于模型供应方，三者互不等同。`P6_MONITOR_VIEW_TOKEN`在隔离AI中配置为隔离监护只读令牌；不得把ARK key给浏览器或固件。默认MOCK不读取ARK。沿用H3真实模型账户/预算显式许可逻辑，本轮没有调用。

未来现场准备还需实际身份/镜像核对、隔离host及证书/认证确认、实体PE3电平/音频接线验证，以及容量分项。仅改变编译端口不保证隔离host正确，也不授权更新sector3；本轮不发送上电或刷写指令。

新worker需明确 `P6_MQTT_MODE=ISOLATED` 才能进入网络路径；命令入口 `python -m cloud.ai.appliance_worker --asr-bin <现有whisper可执行文件> --asr-model <现有模型> --runtime <仓库外受限目录>` 仅供后续评审，**本轮未执行**。原生ASR stdout/stderr不进入公开日志，临时WAV和转录JSON在回合结束后清理；控制台只报固定状态。MONITOR/AI令牌和Broker账户从受限进程环境读取，不写代码或命令行。网页AI独立实例若没有设备录音上下文仍会返回NO_RECORDING_CONTEXT；实体K1录音由该worker自己的事实API完成回复，不借用网页伪造身份。
