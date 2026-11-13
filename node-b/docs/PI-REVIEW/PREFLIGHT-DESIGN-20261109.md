# PREFLIGHT 设计与实板测试批次（PI 签发给 Codex）

**日期** 2026-11-09　**设计人** Claude（PI）　**执行人** Windows 上的 Codex
**承接** [R2](R2-20261109.md) 的 WP-F、WP-C1、WP-I、WP-G、WP-H。本文是它们的执行规格；与 R2 冲突处以本文为准。
**基点** `claude/project-review-v1@efc516a`；固件改动以 Codex 当前分支 `codex/pi-r1-offline-fixes@78a6d00` 为底。

## 0. 负责人决定（2026-11-09，本会话）

负责人明确：
1. **批准 PREFLIGHT 的设计**，不是只批准概念。
2. **预算与构建口径以 Windows 工具链为权威**；VPS 构建仅作离线交叉验证。
3. **支持上板实测，不要过度保守**：下面 §5 的实板批次按“成批授权、批内自治”执行，不逐步请示。

PI 对第 3 条的解读（有异议请直接指出）：批次包含 **安装候选镜像到 C 的 sector0/4（含回退）、C 上电、一条获准的控制台命令、受限的 ESP 易失 AT 操作、热点加入**。**不包含**：真实 `FIELD01 START`/`KEY`、TLS/MQTT 联云、sector3/Options/ESP 固件写入、`AT+UART_DEF`、`AT+RESTORE`、A/B/D/E 板、云与防火墙配置。这些仍是独立授权对象。

**不放松的底线**（AGENTS.md「不得取消」）：电气安全；Flash 写入边界只限 C sector0/4；凭据与真实端点/IP 不入库、不上控制台；设备异常即停。

## 1. 目标与非目标

**目标**：在不消耗 START 的前提下，一次上电窗口内回答这些问题，并把结果落为可核验的回执：
- U-02：`AT+UART_CUR?` 的实际五元组；ESP 是否接受 230400/500000 及切换后的行为。
- N-04：`AT+CWJAP` 的失败子码（1–4）或成功，以及 IPv4 是否就绪。
- 候选波特率下 ESP→STM32 方向的 UART 错误计数与每事务耗时（PI-01 / N-03 的实板证据）。

**非目标**：不跑 TLS/MQTT/音频、不测 TX 重载的二进制写入（需要 TCP，见 §5 的 S4）、不评价 CAN（PRE 时 CAN 空闲，N-03 的 CAN 余量仍靠 WP-I 的算术）。

## 2. 固件设计（FIELD01 构建）

### 2.1 命令面

在现有 `local_control()`（`gateway/b5/network_main.c:147` 起，`FIELD01` 分支，命令缓冲 `command[16]`）增加三条一次性命令，**均 ≤15 个字符**，否则会被 `length<sizeof command` 丢弃：

| 命令 | 行为 |
|---|---|
| `FIELD01 PRE` | 不改波特率，仅报告 |
| `FIELD01 PRE 230` | 在报告的基础上试 230400 |
| `FIELD01 PRE 500` | 在报告的基础上试 500000 |

速率只能是固件内的白名单 {115200, 230400, 500000}，不接受任意数字。仅在 `DISARMED`、未 START、未 stop 时接受；整个启动周期内**只执行一次**（`preflight_done` 置位后再收到一律忽略，要重试需断电重启）。

### 2.2 执行步骤与回执语法

在 `while(!armed && !stop_due){platform_poll();local_control();}`（`network_main.c:472`）的同一循环内同步执行；每步独立判定，**某步失败不中止后续诊断步骤**（诊断目的），但总时限到期即结束。

```text
PRE BEGIN boot_ms=<g_uptime_ms> target=<115200|230400|500000>
PRE AT ok=<0|1>
PRE GMR ver=<数字版本，如 2.3.0.0>                      # 复用 gateway_at_version，不输出完整行
PRE UART_CUR baud=<n> data=<n> stop=<n> parity=<n> flow=<n>   # 仅五个数字；解析失败写 baud=NONE
PRE WIFI ok=<0|1> code=<1|2|3|4|NONE> ms=<耗时>         # 复用 gateway_wifi_join_code
PRE WIFI_SIGNAL channel=<n> rssi=<n>                    # 仅 ok=1 时，复用现有解析
PRE IPV4 ready=<0|1>                                    # 只判断是否非 0.0.0.0，不输出地址
PRE NEGOTIATE target=<n> result=<OK|NO_REPLY|NO_SWITCH|MISMATCH|RESYNC_FAIL> actual=<n|NONE>
PRE STRESS rate=<n> n=<次数> fail=<n> uart_err=<n> rx_high=<n> ms=<总耗时>
PRE RESTORE result=<OK|FAIL>                             # 试速率之后退回 115200
PRE END result=<PASS|BLOCKED> reason=<枚举> uart_err=<累计>
```

- `PRE STRESS`：在当前速率下连续发 N=50 次 `AT+GMR`（回复约 150 B，用来给 ESP→STM32 方向施压并统计丢字节/错误）。`fail` 为 `at_command` 失败次数，`uart_err` 为 `platform_uart_errors_total()` 的增量，`rx_high` 为 `io_metrics.rx_high_water`，`ms` 为总耗时（每事务耗时 = ms/n）。
- 速率 ≠ 115200 时，STRESS 前后各做一次 `AT` 同步校验。
- **PRE 结束必须回到 115200**（`PRE RESTORE`）。失败则置 `preflight_dirty`，此后**拒绝 `FIELD01 START`**并输出 `PRE END result=BLOCKED reason=NEED_POWER_CYCLE`。
- 回执里**绝不出现** SSID、口令、BSSID、IP、模块原始回复。

### 2.3 与现有代码的接口

1. **共享入网前半段**：把 `gateway_network_open()`（`gateway/mqtt/src/gateway_transport.c:~826`）中从 `AT` 同步到 `AT+CWJAP` 的部分抽成内部函数，PRE 与 START 路径共用，**START 路径的行为与回执保持不变**。需要新增只读的 `AT+UART_CUR?` 解析器（只取五个整数）和 IPv4 就绪判断（对 `AT+CIPSTA?` 的回复只判断 `ip` 字段非 `0.0.0.0`，其余丢弃）。
2. **波特率协商**：复用 WP-C1 的 `esp_uart_negotiate(target)`（只用 `AT+UART_CUR`，禁止 `_DEF`；回退与保护间隔规则见 R2 WP-C1）。若 WP-C1 尚未完成，PRE-阶段 1 只提供 `FIELD01 PRE`（不带速率），见 §5。
3. **BRR**：STM32 侧切换速率用 WP-C1 的纯函数；构建期拒绝 |双方相对误差|>2%（R2 §3 N-06 的表）。

### 2.4 设计约束（Codex 必须用 Host 夹具证明）

- **DC-1 不得触发 STOP 锁存**：`platform_poll → service → field01_poll`（`network_main.c:~147`）在 PRE 期间同样被调用，其中 `network_fault` 会 `field01_latch(FIELD01_LINK)`。PRE 的任何 AT 失败都**不得**置 `network_fault`、不得让 `stop_due` 变真；CAN 诊断（`b4_hw_diag` 的 busoff/overflow）在 C-only 空闲状态下也不得在 PRE 期间误锁存。若现有行为会误锁存，用最小方式隔离（例如 PRE 期间不置位 `network_fault`），并说明原因。
- **DC-2 不影响 START**：PRE 成功且 `preflight_dirty` 为假时，`FIELD01 START` 的行为、`uart_error_baseline`、`field01_t0`、授权计数一律不变。PRE 本身不创建 T0、不启 150 s 窗口。
- **DC-3 有界**：PRE 总时限 60 s（含各速率试验）；单次 AT 命令时限 ≤20 s（`AT+CWJAP` 取 20 s，手册默认 15 s）；无重试循环；任何一步超时只记录并继续下一步。
- **DC-4 不读写持久配置**：只读 sector3 配置，不写 sector3/Options/ESP Flash；只发 `AT+UART_CUR`，不发 `AT+UART_DEF`、`AT+RESTORE`、`AT+SLEEP`。
- **DC-5 一次性**：`preflight_done` 防止同一启动周期里重复入网；`FIELD01 STOP` 仍随时有效。
- **DC-6 脱敏**：对含回显的回复、超长回复、畸形回复各一个夹具，证明回执只含枚举与数字、不越界。
- **DC-7 CAN 隔离**：确认 PRE 期间 CAN 不初始化或不会被 PRE 的阻塞 AT 拖累；若 `platform_poll` 里仍处理 CAN，说明阻塞时长上界。

### 2.5 预算

以 **Windows 工具链**报告：PRE 代码 + 协商 + STRESS 的 Flash、SRAM 增量，以及相对 `78a6d00`（Windows FIELD01 sector4 57,776 B、余 7,760 B）的 sector4 余量。超预算不得靠裁剪既有安全检查或 `MP_B5_EGRESS_FINAL` 的度量来凑；超出时先提出方案。

## 3. 主机侧设计

- **新脚本** `node-b/tools/field01_preflight.py`（不改 `field01_short_window.py`，避免污染既有授权计数与交易身份）。复用其 `mark()`、`capture` 骨架、`protected()` 与 `C-uart-private.jsonl` 的做法。
- 规则：新交易身份；无 `START`/`KEY` 发送路径（代码里不存在，不是靠开关禁用）；只发 `FIELD01 PRE[ 230|500]` 一条；`BOOT_BANNER` 出现后才发；读到 `PRE END` 或 210 s 上限即停止，输出公共回执 `PRE-RESULT-public.json`（只存回执里的枚举/数字）与受限的原始串口档。
- 公共回执字段：`transaction_id`、`image_sha256`、`boot_ms`、`target`、各 `PRE` 行解析结果、`result`、`reason`、原生退出码、工具版本。
- 断电：由现场人员断电；脚本只等待并记录，**不得声称已断电**，断电回执保持 `PENDING` 直到有人确认。

## 4. Host 验证要求（在上板之前必须完成）

1. 夹具：mock ESP 模拟 §2.2 的所有分支（含 `+CWJAP:1/2/3/4`、无子码、含回显、超长；`AT+UART_CUR?` 正常/缺失/畸形；协商的 `NO_REPLY/NO_SWITCH/MISMATCH/RESYNC_FAIL`；IPv4 `0.0.0.0` 与非零）。
2. 证明 DC-1 至 DC-7。
3. 证明 START 路径回归与 `78a6d00` 一致（沿用现有 `test_unified.py` 与 Wi-Fi 夹具）。
4. 把 `test_field01_wifi_failure.c` 与新夹具接入同一运行入口（R2 WP-G）。
5. Windows 构建 + 与 VPS 工具链的离线交叉构建各一次，记录两边尺寸差异（WP-H）。

## 5. 实板批次（成批授权，批内自治）

### 5.1 对象与上限（PI 建议值，负责人可改）

| 对象 | 上限 |
|---|---|
| 安装对象 | 仅 C 的 sector0/4；候选镜像 ≤2 个版本；回退 ≤2 次 |
| 上电会话 | 每个镜像 ≤8 次，每次 ≤210 s（PRE 自身 60 s） |
| 控制台命令 | 仅 `FIELD01 PRE`、`FIELD01 PRE 230`、`FIELD01 PRE 500`；每次启动周期 1 条 |
| ESP 操作 | `AT`、`AT+GMR`、`AT+UART_CUR?`、`AT+UART_CUR=<白名单速率>,8,1,0,0`、`AT+CWJAP`、`AT+CWJAP?`、`AT+CIPSTA?` |
| 热点 | 仅使用 C 的 sector3 里已有配置，不改 |
| 有效期 | 2026-11-09 至 2026-11-16 |

**不包含**：见 §0。

### 5.2 阶段

| 阶段 | 镜像 | 命令 | 目的 / 通过判据 |
|---|---|---|---|
| S0 | — | — | 只读核对：J-Link 读回当前 C 的身份与 sector3 CRC（沿用历史做法，写入前后各一次）；记录回退镜像身份与 SHA。 |
| S1 | PRE 候选 | `FIELD01 PRE` | 取得 `UART_CUR` 五元组、`WIFI code`、`IPV4`、115200 下 `STRESS` 基线。**通过判据**：回执完整且脱敏，`DC-1` 成立（无 STOP 锁存）。 |
| S2 | 同一镜像（含 WP-C1 协商） | `FIELD01 PRE 230` | 230400 下协商成功与否、`uart_err`、每事务耗时；`PRE RESTORE=OK`。 |
| S3 | 同一镜像 | `FIELD01 PRE 500` | 同上，500000。仅在 S2 `uart_err=0` 且 `RESTORE=OK` 时进行。 |
| S4（可选） | 另议 | 另议 | TX 重载（经 TCP 的二进制写入）与 CAN 同时活动的实测，需要隔离端点设计；由 Codex 先出设计，负责人用一句话确认后再做，**不在本批内**。 |

### 5.3 批内自治与停止条件

- 在上述范围内，Codex **不逐步请示**：按 S0→S3 顺序自行推进，失败按“重试一次再停”处理，并在批次结束时一次性汇报。
- **立即停止（STOP_TARGET）**：非预期复位或 HALT/ROM；J-Link 身份或 Flash 与记录不符；`uart_err` 在 `115200` 基线之外出现持续增长（STRESS 内连续两次试验 `fail>0` 或 `uart_err` 增长 ≥ 5）；`PRE RESTORE=FAIL` 且断电重启后同样失败；任何电气异常。停止后保存原件，不自动复位、不重刷、不继续上电。
- 候选速率只在 `S2` 通过后才试 `S3`；某速率 `PRE RESTORE=FAIL` 则该速率视为不通过，并记录断电恢复结果。
- 结束后按回退路径恢复原镜像（`gateway/microphone/unified_install.py` 的既有安装/回退入口；Codex 先确认它的子命令与对象边界，并在回执中说明回退目标即原五板镜像 boot 392 B + code 56,072 B 的身份核对方式）。

### 5.4 回执

每次会话：`PRE` 回执、`image_sha256`、`boot_ms`、串口原件 SHA、工具版本、原生退出码、断电状态（`PENDING`/`CONFIRMED`）；汇总表给出 S1–S3 各速率的 `fail`、`uart_err`、`rx_high`、`ms/n`、`NEGOTIATE`、`RESTORE`。**Host/Windows 构建 PASS 与实板结果分栏，不得混写。**

## 6. 结果如何解读（PI 预先约定，避免事后改标准）

| 现象 | 结论范围 |
|---|---|
| `WIFI code=2` 或 `3` | 支持 H1（sector3 凭据或热点名有问题）；是否改 sector3 是**独立授权对象**，由负责人另批，PI 不在本批内改 |
| `WIFI code=1` | 支持 H2（关联超时，如热点休眠/兼容模式），需热点侧核对（U-07） |
| `WIFI ok=1` 且 `IPV4 ready=1` | 当前 sector3 配置是可用的；FIELD01 当时失败原因未复现，**不得据此宣称已修复** |
| `NEGOTIATE=NO_SWITCH/MISMATCH` | 该 ESP 构建不支持或分频不同；按实际值记录，PI 重新评估候选档位 |
| 某速率 `fail=0` 且 `uart_err=0` | 只说明 **ESP→STM32 方向、AT 级负载** 下该速率可用；不等于 TX 重载、CAN 同时活动或整机容量通过 |
| 任何速率下的批/s 估算 | 不得由 PRE 得出；容量结论仍须走 P3 同负载对照与后续窗口 |

## 7. 需要 Codex 回答的问题

| 编号 | 问题 |
|---|---|
| W-01 | `platform_poll → service → field01_poll` 在 DISARMED 阶段是否确实被调用？PRE 期间 `network_fault` 与 CAN 诊断的行为怎样（DC-1/DC-7）？ |
| W-02 | 把入网前半段抽成共享函数的最小改动范围，以及对 START 路径回执的影响（预期无影响，请证明）。 |
| W-03 | `gateway/microphone/unified_install.py` 的安装/回退子命令、对象边界、是否只写 sector0/4；原五板镜像的身份核对方法。 |
| W-04 | PRE 之后若不重启直接 START，ESP 已处于已联网状态时，START 路径再发 `AT+CWJAP` 的行为（官方手册说明或实测）。PI 的设计是 START 路径不变；若手册显示有风险，请提出最小缓解。 |
| W-05 | `AT+CIPSTA?` 回复格式与 `ip` 字段的解析方法（只判断是否非 `0.0.0.0`），以及该回复是否可能被回显污染。 |
| W-06 | STRESS 用 `AT+GMR` ×50 是否足以代表“ESP→STM32 突发”；如有更合适的无副作用命令请提出并说明。 |
| W-07 | 是否保留 §2.2 回执语法，或有更省字节的等价形式（以 Windows 预算为准）。 |

## 8. 顺序

1. 先做 R2 的 WP-G、WP-H（小）。
2. WP-I（中断周期与 CAN 余量的算术）与 WP-C1（协商 + Host 夹具）并行；PRE 的固件在 WP-C1 的协商函数就绪后实现。若要提前取得 S1 数据，可先出只含 `FIELD01 PRE`（不带速率）的最小镜像，S2/S3 等 WP-C1 完成后再追加。
3. Host 验证 §4 全部通过 → 提交并 push，PI 评审 → 评审通过后进入 §5 批次。
4. 批次结束后的回执交 PI，PI 据 §6 裁定并决定是否进入 S4 与 P3 重跑。
