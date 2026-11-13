# MPM-B5｜M1-P0 独立 PI 验收与 ECG60 单次入场门合同（R1）

> 日期：2026-10-30（America/New_York；项目交付记录为 2026-10-31 Asia/Shanghai）  
> 项目：`Serendipity-min/medical-multi-parameter-monitor`（PRIVATE）  
> 被审分支：`codex/b5-m1-p0-offline-entry-20261031`  
> 被审 SHA：`37630aee2ef0af5bee9b13b827d21b38351d2445`  
> 来源基线：`025839a2fc272232141b557bfce8aa10952ca682`  
> 决定：`M1_P0_OFFLINE_ACCEPTED / M1_E60_R1_FIELD_NOT_AUTHORIZED_YET`  
> **本合同仅准许最小离线修正、首场准入证据准备及后续 PI 复核；不是可执行的实板授权令牌。**

## 1. PI 已核对的事实

1. GitHub 远端分支 HEAD 确实为 `37630aee…`，比 T0 基线领先 1 次提交。19 个交付文件变更；18 项自引用排除清单均可在当前 Git tree 中找到，登记大小均匹配。**这不是对 18 个原始 SHA256 全部重新复算的声明。**
2. `node-b/evidence/CODEX-M1-P0-20261031/mock-and-execution-ledger.json` 的最终 `mock-release` 记录 19/19，退出码 0；保留早先失败。现场 CLI 的预期拒止为 exit 2。Mock 不是实板 SDK 连接、原生 Close 或真实 MCU WCET 的证明。
3. `b5_m1_entry.py` 为新 M1 Scope 编写了受签名约束的 B-only 路线，复用 BLink/B4 读取与 5692B 稳定槽；`b5_m1_review.py` 单独评价 45s 预热＋120s 评价、120 个固定 1Hz 槽。真实目标固件尚未本轮重新读回。
4. 已有 B41012B 同次制品：BIN 41,012 字节 SHA256 `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d`；AXF `e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7`；symbols `07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8`。历史完整 Flash `9ff8133d06330a4b05cb15d26bfb51b6f7e1197014692c5267d178d744f4287d`，均属**历史参考身份**，不是今天已读板结论。
5. 交付的 `M1-E60-R1-PILOT.disabled.json` 仍为 `enabled=false / sessions=0 / PI_signature=null / nonce=null`。同一 M0 矩阵其余 23 场不属于本轮授权。

## 2. 实板暂不开放的四项阻断

- **FIELD-GATE-SITE**：最近用户现场报告为 B/C 同时上电、USB 在 C、J-Link 在 B、L 在 LA，仅说 ECG 波形。当前 B-only 的电气隔离/反供电、真实 ECG60/1mV 菜单、SKX 充电 USB 隔离及人员 STOP 条件尚未证实。现场不能使用旧报告自填为今日事实。
- **FIELD-GATE-COLD**：单独 B 冷启动的实际物理事实和独立 BOOT epoch 未建立。`uptime <=120s`、新输出目录和 nonce 都不能单独证明冷启动。现场人员做冷态操作需要独立具体许可与防反供电步骤。
- **FIELD-GATE-TRUST**：`b5_m1_entry.py` 的 `TRUSTED_PI_KEY_SHA256=None`，生产 `--execute/--worker` 当前按设计拒止。PI 固定信任根应先由 PI 可信渠道选定并锁定，私钥不入仓库/EFS公开报告，也不应由 Codex 自己代签/自建根。更改固定根会改变工具 SHA，必须重新冻结整个 Scope 与同次依赖指纹并做负例回归。
- **FIELD-GATE-SDK**：J-Link 原生 OpenEx/Device/Connect/Close 仍可能有隐式状态作用，进程强杀也不等于 MCU 停止或成功 Close。须保留 `SDK_RESIDUAL_RISK_UNRESOLVED` 并经 PI 明确知情批准有限风险，同时指定现场人工停止/断电责任。

## 3. 新增代码的一个最小离线整改（签发 P1 前）

独立阅读 `b5_m1_entry.py::M1Link.gate()`：

```python
need(self.phase=='closing' or not (self.root/'STOP').exists(), 'M1_OPERATOR_STOP')
```

这意味着 `phase='closing'` 时，不仅 native `Close`，连 `final snapshot`、最终 BIN 前缀读取、身份读取及 `SetRestartOnClose` 策略都有机会在 STOP 文件已经出现后继续进行。虽然父监督器也会 kill worker，但子进程需要自己 fail-close。

**仅准许** Codex 在独立补丁分支修复这一条件：检测到 STOP 时停止进一步普通读、身份校验及续跑策略操作，仅按受审 `finally` 的安全关闭范围处理；严禁为追求退出码 0 而发出 Halt/Go/Reset/Flash。为 STOP 恰在 final snapshot 与准备 `SetRestartOnClose` 之间发生的情形增加定向 Mock 负例；原 SDK native Close 语义仍标 UNKNOWN。保留旧失败原件、最小 diff、重跑 19 项既有测试及新相关负例，生成新工具 SHA。任何 STOP 触发不能返回通过。

除此以外不要重写 M1 采集、RR 算法、旧历史门槛、T0 或三板工作。

## 4. 真正的 ECG60 首场授权必须如何签发

待第 2、3 章的阻断消除后，PI 另签**仅 `M1-E60-R1` 的一次性现场卡**，并与当期实际哈希一致。它必须至少绑定：

| 域 | 需冻结的条件 |
|---|---|
| 对象 | 仅 Node-B 当前 B41012B；B-only，不需要 Gateway-C、双 CAN、MQTT 或云 |
| 刺激 | SKX 正常 ECG60 bpm、名义 1mV；R→RA/L→LA/F→RL，非人体；充电 USB 断开；菜单、导联、供电由负责人当次目视核定 |
| 电气 | C 的电源、USB、CAN、反供电与探针路径经批准的冷态安全图确认；不能用“C未参与数据采集”替代 B-only 的隔离证据 |
| 冷启动 | 新独立物理冷启动，真实 BOOT epoch，按当次签署规定的时序执行；不授权软件 RESET/HALT/Go |
| 代码与制品 | 固定 Git commit/tree、M1 entry/reviewer、全部依赖/DLL SHA、同次 BIN/AXF/symbols、参考 identity/full/options；采前失败即 STOP |
| 签署与单次性 | 由 PI 掌控的 Ed25519 信任根、新 nonce、一轮父/worker 原子 claim、有效期、唯一 EFS 输出目录；失败不自动退还次数 |
| 时间 | 仅预检 75s＋采集 165s＋收尾 20s，整个会话建议 260s／父监督 265s；native 读/Close 的 5s/45s 上界按已审程序执行 |
| 异常 | 原生负返回/正短读、ROM/HALT、采样不连续、身份漂移、CPU 状态不明、Close 或监督超时立即停止；不重连、不二次试采、不写 Flash；人工保全与断电责任预先冻结 |

上述是**未来授权应绑定的内容**，并不构成现在对任何上电、插拔或一次采集的许可。既有 disabled JSON 不得通过改 `enabled` 或伪造签名来代替正式 PI 签发。

## 5. 首场预注册判据与完成后的分流

- 仅一次 `M1-E60-R1`，采集未发生时仍记录 `NOT_RUN`。由第一份合格 raw epoch 锚定 165s；前 45s 预热，后 120s 做 120 个半开 1Hz 槽评价。
- ECG 原码 CH2 与 CH1 均保留 250Hz，RESP50 仅依原 seq 每 5 点导出；保留未更改的 ADC/IRQ ms/cycles、flags、RAW、120B diag、过程日志和源校验哈希。不以插值、合成补点或择优 valid 来制造通过。
- 正确有效槽至少 118/120，且评价期每个已观测有效 HR 均在目标 60±2 bpm；原始帧完整性、无新增采样/ADC/CAN 不合格事件及合法 STOP/Close 全部满足。以正式工程评测器真实退出码为准。
- Capture exit 0 仅表示采集完成；review exit 0 且 `field_scope_PASS=true` 才能记 `M1_E60_R1_ENGINEERING_PASS`。若出现 exit 1/2/3/4，则本轮只记录失败/拒止并停止，不能以重新打印或第二场掩盖首场结果。
- 本场成功且 PI 接收后，可申请第一批 ECG90/120；RR12/15/18/24/30 的 HR 有效性单列，维持 `SOURCE_UNKNOWN`，不预称 RR 全窗 PASS；其余 23 场不自动解锁。

## 6. PI 结论

```text
M1_P0_OFFLINE                    = ACCEPTED
M1_P0_REUSE_FIRST               = ACCEPTED
M1_P1_TARGETED_STOP_GUARD_PATCH = OFFLINE_GO
M1_E60_R1_HARDWARE_FIELD        = NOT_AUTHORIZED_YET
PRODUCTION_PI_TRUST_ROOT        = NOT_CONFIGURED
CURRENT_B_ONLY_TOPOLOGY         = NOT_VERIFIED
CURRENT_ECG60_1MV_MENU          = NOT_VERIFIED
INDEPENDENT_B_COLD_BOOT         = NOT_VERIFIED
NATIVE_SDK_RESIDUAL_RISK        = UNRESOLVED
M1_OTHER_23_FIELD_SESSIONS      = NOT_AUTHORIZED
C_DOUBLE_CAN / A_B_C_FIELD      = NOT_AUTHORIZED
R5_R6_RR15_FORMAL               = NOT_PASS_EXIT_3
```

本合同属于 PI 阶段审查与下一次实板**签发前置条件**。Codex 可仅完成上述局部离线补丁、复测并生成待签独立首场授权包，提交/推送新分支后停止。不执行现场测试，不自动调整主控上电/接线，不借用旧 G3 令牌，不操作云端。
