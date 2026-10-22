# VOICE T1｜协议、非阻塞驱动与离线证据

所有测试均本机Host/离线ARM；板端、音频、生产网络结果为NOT_RUN。

## 协议与实现

厂家V0.21：9600、8N1；文本帧 `FD LEN_H LEN_L 01 04 UTF8`，LEN=文本字节数+2。你好精确帧 `FD 00 08 01 04 E4 BD A0 E5 A5 BD`。本项目上限240B，拒绝超限而非截断；254/255/256/4K边界全拒绝，避免长度低字节回绕。

STOP/PAUSE/RESUME/QUERY构帧分别 `FD 00 01 02/03/04/21`。手册查询示例/其他版本存在长度歧义：本版本只作为候选，不自动探测不同长度、不连续重发。厂家状态表41正确接收、45命令错、46数据不完整、4A初始化、4E播放、4F空闲；实际模块版本应答仍待抓取。

本地音量管理帧仅允许v0/v1，固定v1帧 `FD 00 06 01 01 5B 76 31 5D`；外来文本禁止方括号/控制符，不允许注入设置。语音文本“语音模块测试完成”，无真实读数/身份/健康建议。

`tts_frame`严格检查UTF-8过长编码、代理区、非法范围、控制/零宽/方向字符和截断；失败前不写部分帧。`tts_queue`固定单槽，无malloc，主循环每次最多尝试1字节，发送及ACK总预算500ms，播放20s，STOP只试一次/1500ms。ID严格递增、至少5s间隔；重启清本地队列不代表已经实现云端防重放。

`UART_TX_DONE`、模块41、模块4F分别累计；没有AUDIO_HEARD的软件成功标志。取消丢弃文本并尝试STOP，未获确认/空闲不得宣称静音成功；半帧截断与模块掉电可能使STOP不被解析。错误锁止需显式重新初始化，不靠自动重试续成PASS。

## 实际检查

| 本轮命令/证据 | 退出码 | 结果 |
|---|---|---|
| `wsl ... python3 gateway/voice/build.py --host` | 0 | 3103条C断言；含字节精确、UTF-8、忙态、防重放、禁用、乱序、断线/供电失败注入、无ACK/播放超时、取消、tick回绕、合成CAN/ESP调度 |
| `python -m pytest gateway/voice/tests/test_bench_window.py -q` | 0 | 7通过；合成sector0写/恢复、错角色、双读不一致、旧镜像、FLASH_CR异常、保护区变化及恢复原件篡改 |
| `python -m pytest cloud/backend/tests cloud/ai/tests gateway/physical_can/tests -q` | 0 | 318通过，1跳过，4子测试；比旧合同255项增加，不冒称原255项是本轮新增成果 |
| P5普通含既有CAN Host | 0 | 42检查及CAN协议/Router/重启链路 |
| P5 IRQ+wifi-awake+fresh-SNTP | 0 | 实际48检查；目录名p5-46沿用目标类别，成绩以实际48为准 |
| 物理Gateway `--host --irq --rx-order` | 0 | 100ms前台停顿/每个PPG点/B OFFLINE夹具通过 |
| 原C正式8883与隔离8884 ARM复现 | 0 / 0 | 均43172B；分别b9b25b18…、59229f1b…，与H3历史精确相同；只编译，未烧录 |
| 独立语音ARM候选 | 0 | 3756B，sector0，USART2/SysTick强向量；CAN/USART3无强ISR，未链接MQTT/配置 |

原C正式build的source_sha256和build_input_sha256与H3历史逐项差异0；宏前缀显式映射历史 `E:\medical-monitor-h3`，避免__FILE__使BIN路径不同。未改Router/CANopenNode/coreMQTT/ESP/SNTP/NIBP或旧构建脚本。

## 原始失败和限制

- 首次独立ARM链接成功，但误用了H3联网下载检查器，退出1 `H3_IRQ_NOT_STRONG_VECTOR`。失败JSON/log保留；新增独立bench_manifest，不放宽H3检查器。
- 初次从WSL直接调用两个P5脚本均退出1，原因Windows worktree的.git路径不能由Linux Git解析。随后用原Windows入口注入真实HEAD，两组通过；初始终端失败说明保留，非测试逻辑失败。
- 厂家页面证书/超时和初次旧资料目录不存在均保留说明，不冒称首次成功。首次pytest318项退出0，随后为生成文件化原始回执复跑一次，最终日志在独立regression目录。
- ARM GNU 14.2.Rel1链接器保留nosys未实现系统调用及RWX加载段告警；bench不调用系统I/O/动态分配。bss含2048B链接预留栈，真实运行栈水位、ISR时延、播放电流均未测，不拿静态size当运行水位。
- 新目录首次本地提交误含Host可执行文件/ELF，暂存允许集断言已失败但PowerShell后续commit仍执行。没有推送；随即从索引移除两产物、增加本目录build忽略，修正未发布提交并按逐命令check=True门禁重新核验。磁盘候选未删除；原始日志通过限定.gitattributes保持字节，不清理日志尾部伪装检查通过。
- 无真实模块ACK、无声音、无真实掉电/停止、无C CAN/MQTT并发窗口。纯Host的合成计数只证明每次调用有界，不证明实板调度性能。

完整带UTC、cwd、命令、源码SHA、退出码的回执见 `evidence/` 和不可变 `VOICE-INPUT-MANIFEST.json`。7项烧录工具合成测试的原始回执另列于该目录。

裁定：`T1_HOST_PASS / HARDWARE_NOT_RUN`；不能签发C_TTS_LOCAL_PASS或AI_LINK_PASS。
