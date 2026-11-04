# 新窗口接手页与 Git 分支清单

**2026-11-04 更新：** 已按负责人本轮授权完成首批分支删名及本地入口整理；远端现为 34 个分支。M0 标签保持不变，当前 C 的 Flash 资源汇总有 8 字节勘误。执行结果、最新工作目录和未决项见 [接手与 Git 整合回执](05-Takeover-and-Git-Integration-20261104.md)。下文 36 分支表为发布前历史快照，不作为今日分支数量。

**工程底座**　`baseline/abc-unified-pre-split-v1` 解引用到 `26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e`。这是一枚附注标签，标签对象本身的 SHA 和提交 SHA 不同。M0 分支头也是这个提交，父提交 `c0b36430` 对应较早的 C 单板 R4。五板工作分支使用 `codex/five-node-single-module-v1`，以 M0 为父线，本轮交付内容为文档。[M0 提交](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e)

## 给新开的 Codex 窗口

可直接复制以下一段。后文的分支清单供需要追溯某个问题时查阅。

> 在 Windows 工程 `E:/medical-monitor-node-b5-cloud` 接手五板迁移。先看工作树状态，保留现有本地更改。按本页的 PowerShell 命令定位远端工作分支和 M0 标签。阅读根 `AGENTS.md`、M0 原交接与本目录 `04-Five-Node-Contract.md`。三场 M0 均已通过。当前先做 M1 离线节点映射、D/E 构建与相关回归。并行整理两段 CAN 的断电测量表；现场报 41 Ω 的段先分测。现场联调收到当期指令后，再按实际板卡、供电、终端、写入范围和恢复入口成批执行。复用现成工具、按故障复测，不重复 M0 整套。板间规划为 C.CAN1 接 A 血氧和 E 血压，C.CAN2 接 B 心电/呼吸和 D 物体温度。阶段末交付按板区分的镜像及证据，`main` 合并留到最终验收。

| 先查什么 | 权威入口 | 现场意义 |
|---|---|---|
| 两份汇报与迁移合同 | [技术路线](01-Technology-Route.md) · [P4 至 M0 问题](02-P4-to-M0.md) · [五板合同](04-Five-Node-Contract.md) | 新窗口先执行合同 M1。M2、M3、M4 分别有具体实物条件 |
| 最后一次状态、接线与遗留 | [原交接 §3–7、§10–16][handoff] | 上次结束时板卡已断电、两段 CAN 仍连、J-Link 板端在 B、主机端已拔、隔离服务停止。新窗口开始时应重新核实实物 |
| 唯一可恢复底座 | [制品清单][manifest] · [恢复入口][restore] | A42608、B41516、C 的 `C_M0_STARTUP_ORDER`。C 为 392 B boot + 54,500 B code。选择 `candidate-c-startup-order`，使用已有分段恢复流程 |
| 窗口与原失败 | [实测表][results] · [原始窗口索引][idx] | ABC ECG60 原联评 3 与更正后 0 同时保留。旧 R4、C44520 及旧观察器各自有不同覆盖 |
| 本地受限材料 | 本机忽略的 `node-b/build/m0-current-pointer.json` 和它指向的恢复回执 | 只读 Git 可做离线代码工作；实板恢复另需该台 Windows 上的身份、备份与读回资料。新工作树按已有指针定位原件，勿将原件推入仓库 |
| 新信息留在哪里 | 本页和五板合同；首轮实际分件数值填入五板结果表 | 原交接 16 节对 M0 已足够。另页追加已选架构、实际 41 Ω、节点身份和下一步，不回写冻结标签。现场未知项为电阻测点/组合、终端跳帽、收发器型号、PCB 修订、主干和支线长度、D/E 原始状态 |

在原工程中可使用以下 PowerShell 命令。独立工作树便于同时保留三板工作目录。若已有同名工作树，在已有目录继续，先查看其状态。

```powershell
git status --short --branch
git fetch origin --tags
git rev-parse 'refs/tags/baseline/abc-unified-pre-split-v1^{commit}'
git log -1 --oneline origin/codex/five-node-single-module-v1
git worktree list
# 首次接手且本地尚无同名分支时执行
git worktree add --track -b codex/five-node-single-module-v1 ../medical-monitor-five-node origin/codex/five-node-single-module-v1
```

## 分支要怎样整合

盘点口径为发布本组文档前的远端快照。GitHub 分支 API 第一页有 **36** 项、第二页为空；独立抓取全部远端 heads 后，以 `git rev-list` 及 `merge-base --is-ancestor` 核对提交图。全部 heads 共可达 **297** 个去重提交，M0 可达 **209** 个；其中 `P4..M0` 有 **151** 个。**29** 个分支头等于或已进入 M0（含 M0 自身及 main），**7** 个有 M0 之外的提交，去重后共 **88** 个。逐项数量不可相加，因为 A、H3 和旧 C 语音共享一条历史。盘点时开放 PR 为 0。下表链接固定到当次 tip，日后移动分支仍可回查。[远端分支](https://github.com/Serendipity-min/medical-multi-parameter-monitor/branches) · [PR #6](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/6)

**本轮整合落点**　给新窗口一个从 M0 派生的工作入口。M0 已包含当前 B、C 和通过的三板底座，直接在五板工作分支接续开发。7 个分叉保留原引用，后续确实需要旧实现时按文件/函数比对、挑取，并针对当前源回归。即使 M0 已具备同类能力，Git 也不会自动把旧分支的提交标为已合入。按标签重建 A42608/B41516 的记录已存在，可以直接从 M0 的 A/B 工程复用驱动。[离线重建记录](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/FINAL-SYSTEM-20261102/P0-STATUS.md)

| 对象 | 决定与理由 |
|---|---|
| `main`、`P4`、M0 和两枚已有标签 | 保留长期入口。main 为 M0 祖先，两者右侧相差 205 个提交；P4 当前头已接纳 PR #6。五板验收后，从工作分支单独审阅到 main 的累计差异及发布清单 |
| A → H3 → 旧 C 语音 | 三者是彼此有祖先关系的旁线。包含 A 实板资料、H3 专项、正式语音与恢复取证。M0 另有双 CAN 与新并发调度，不能把历史表述或旧固件覆盖到当前 C |
| P6 文字/语音 | 保留 Web AI 与历史 TTS、来源/预算经验。M0 工程短回复与五板实时事实问答的调用契约不同；只移植缺少的事实路径 |
| C3A 诊断、早期 A/B v0.7 | 各有独有提交。诊断脚本及合同可按需引用，旧树形和未决协议不适合作为新基座 |
| 已成为祖先的短期分支 | 对应提交即使撤掉分支名也仍可通过 M0 标签定位。删名前仍要查活动脚本、文档链接、工作树和新出现的 PR，分支名本身也可能是入口。本次只列候选 |

### 36 个原有分支逐项索引

“独有”是 `git rev-list --count M0..分支`。“距 M0”是仅 M0 一侧的提交数。两列均为可达提交的集合差，不代表文件缺失数。

| 原分支 | 冻结 tip | 独有 | 距 M0 | 用途、处置 |
|---|---|---:|---:|---|
| `A` | [3fa14b00](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5) | 15 | 151 | A 早期 CANopen、双次真实生命体征采集，H3 祖先，保留分叉 |
| `B` | [f8c99433](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/f8c99433561b2e110c04ba9fb33c30235910a3e9) | 0 | 149 | B 侧审查及历史诊断，保留检索入口 |
| `B2` | [2ca744d2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/2ca744d2f06d49711863968aeef15b64891edd18) | 0 | 150 | 双 F407 ECG 源 G0/G1，保留真值实验入口 |
| `P4` | [67f5f57b](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/67f5f57bd82c6e326e9e78ec9540481c80105e5f) | 0 | 151 | PR #6 后的 P4 集成头，保留 CI 与里程碑入口 |
| `P5-coremqtt-baremetal` | [88a993cb](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/88a993cb2dad828d2d13438445a67324e10f71d0) | 0 | 152 | 裸机 coreMQTT 验收，CI 引用，保留 |
| `audit/b5-r5qc-r6p0-20261030` | [8954c8ea](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/8954c8ea96af1eda99f00b927f19fecab3cc3215) | 0 | 54 | R5 失败台账及 R6 整改，保留 |
| `audit/b5-r6-p0b-20261030` | [64d07ff3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/64d07ff33e2fddb46a4a0570d9abfa83adbc3e02) | 0 | 53 | 线束与硬件复核、离线纠错，历史可追溯 |
| `audit/b5-r6-rr15-offline-causal-20261030` | [b9b17a76](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/b9b17a7657f101e8901a24115da8538becc420d0) | 0 | 46 | RR15 因果回放预注册，待真值补证 |
| `audit/codex-b5-r6-p1b0-20261030` | [98bd1f86](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/98bd1f86d8e1cbf3b764a0876142a888b8837343) | 0 | 49 | B41012 的 RR15 实板失败，保留证据 |
| `audit/codex-b5-r6-takeover-20261030` | [9f5a6641](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/9f5a6641fec2bcdb575f5f9ff549b8e9b0223820) | 0 | 50 | Gemini 到 Codex 接管审计，保留 |
| `codex/abc-two-group-integration-20261031` | [e1274b33](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/e1274b337e2b8393b315409cc5d030a83658b129) | 0 | 11 | 早期双组联动及独立温度屏，保留 |
| `codex/b5-m1-ecg60-stop-gate-20261031` | [cba0bcfe](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/cba0bcfeead7c0c0c38dd4046538b82ddf151722) | 0 | 40 | 关闭读取期间响应 STOP，保留故障入口 |
| `codex/b5-m1-p0-offline-entry-20261031` | [37630aee](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/37630aee2ef0af5bee9b13b827d21b38351d2445) | 0 | 41 | M1 旧离线入口；首批可撤分支名 |
| `codex/b5-m1-rr-batch15-owner-20261031` | [010706e2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/010706e2b196b59e489c2dfde557301dae0d0337) | 0 | 24 | RR 15 场与 TEMP180 原失败，保留 |
| `codex/b5-multirate-planning-20261031` | [e78cd191](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/e78cd19197bda2f9986355e28ecf05ce5cf02fb9) | 0 | 43 | 多率规划；首批可撤分支名 |
| `codex/b5-r6-ecg-temp-20261030` | [e24e9705](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/e24e9705a31ed9c2237ed38dd6bc843b6ffaa45c) | 0 | 48 | ECG60 与 TEMP 纠正后窗口，保留 |
| `codex/b5-r6-rr15-causal-candidate-20261030` | [eda6e24a](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/eda6e24a8eedcfe0b50416390022db0c187550af) | 0 | 45 | RR15 回放、物理原因未明，保留 |
| `codex/b5-rr15-source-truth-a0-20261030` | [6669a855](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/6669a855662f0655fc7d7b6fc4c9a45ee1ef13b0) | 0 | 44 | 源端真值 A0 设计，尚有依赖 |
| `codex/b5-tri-t0-host-20261031` | [025839a2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/025839a2fc272232141b557bfce8aa10952ca682) | 0 | 42 | 旧三节点 Host T0；首批可撤分支名 |
| `codex/c-inmp441-voice-20261102` | [be552179](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/be552179d77b21132d0027ff757e5db60959713f) | 0 | 6 | 独立 MIC/ASR/TTS 实测与恢复入口 |
| `codex/c-voice-cloud-20261022` | [ba61ae2c](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/ba61ae2c97204f240d8fa6f316eb700aff70d29e) | 66 | 151 | 旧 C 正式云语音与 H3 恢复，保留分叉 |
| `codex/final-system-20261102` | [baccc7bc](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/baccc7bc6ca2a14da6779664eead919a3240ccf4) | 0 | 3 | P0 读回、STOP 实测、CCM 预算，保留 |
| `codex/final-unified-c-runtime` | [c0b36430](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/c0b36430cb8262147b2249d18d889892d3c7b0fa) | 0 | 1 | 统一 C R4 单板阶段，保留 |
| `codex/m0-abc-unified-baseline-20261103` | [26e695ff](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e) | 0 | 0 | 与 M0 标签同一提交，保留 |
| `codex/node-b-bio-v2-field-20261022` | [bb9bc8e0](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/bb9bc8e00860ff4f61fa3c4f315edfb76815a59b) | 0 | 126 | 生理信号 RR 六窗，保留 |
| `codex/node-b-bio-v2-test-20261022` | [c0617b9f](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/c0617b9fc0ee1f1c6b2f3c4ece90b36db7a78740) | 0 | 148 | BIO 离线冻结与旧失败回放，历史可追溯 |
| `codex/node-b-precan-closeout-20261023` | [9988d37c](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/9988d37cd5470d6857bb535aab1d821cf2581302) | 0 | 118 | 上 CAN 前屏幕重启恢复，历史可追溯 |
| `codex/node-b4-dualbus-software-20261023` | [ffa440b3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/ffa440b31b8b4993967f0e9aef1b3071a0d1dcfe) | 0 | 101 | B4 B→C 真实 CAN 和 ECG 复验，保留 |
| `codex/node-b5-cloud-integration-20261026` | [2854d358](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/2854d3581658a91d65c1aa30d827ff489ff0f081) | 0 | 55 | B5 上云、R5 证据纠错，保留 |
| `codex/p5-c3a-diagnostic` | [38ccef7f](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/38ccef7fd7e265b848880dd2ca1015ca3f3a7099) | 3 | 163 | C3A 诊断和分类，保留分叉 |
| `dev/h3-nodea-cloud-ai-integration` | [a5cdd5b0](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/a5cdd5b0b1ad48108fd631136e9de69e30582f2d) | 62 | 151 | A/C 与正式云、MOCK 工程验收和恢复，保留分叉及 H3 标签 |
| `dev/node-a-v07` | [dab0b3de](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/dab0b3de78a8c76efb48593eb8a164a13663e422) | 6 | 182 | 早期 A 的协议约束/资料，保留分叉 |
| `dev/node-b-v07` | [ce84b33b](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/ce84b33b705403775790d4723978d586aeb877a4) | 2 | 182 | 早期 B 的合同/状态，保留分叉 |
| `dev/p6-cloud-ai-text-tts-v1` | [1a5d7d16](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/1a5d7d16a1df00a1195a6754c35d33f4380324a6) | 11 | 151 | 云端文字、AI 网页与 TTS 原始实现，保留分叉 |
| `main` | [50699048](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/50699048010c57ba10f8573461844c525b022a07) | 0 | 205 | 最终发布落点，保留 |
| `patch/b5-r6-patch01-20261030` | [01864fb4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/commit/01864fb4c1ea35c9da38aa98b1e85790d2ed5415) | 0 | 51 | PATCH01/FIX02；保留接管前后的人类可读里程碑 |

### 首批可申请撤掉的三个分支名

| 候选 | 盘点时的 tip | 可长期取回的位置 |
|---|---|---|
| `codex/b5-multirate-planning-20261031` | `e78cd191` | M0 内的多率规划提交 |
| `codex/b5-tri-t0-host-20261031` | `025839a2` | M0 内的 T0 Host 提交 |
| `codex/b5-m1-p0-offline-entry-20261031` | `37630aee` | M0 内的离线采集入口提交 |

这三项当前各自独有提交为 0。M0 的 354 个活动脚本、测试与工作流中未发现这三个完整分支名的字面引用；范围不含负责人本机其他工作树和外部自动化。P4 与 P5 分支名仍被 CI 点名。删名留到负责人另行授权时，复核 tip 未变、无新 PR、没有已知外部任务依赖即可。其余分支保留原名，日常仅需跟进 M0 标签和五板工作分支。[固定版工作流](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/.github/workflows/phase1.yml)

[handoff]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/MPM-M0-ABC-BASELINE-CONTEXT-HANDOFF-20261103.md
[manifest]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/M0-ABC-BASELINE-20261103/RELEASE-MANIFEST.json
[restore]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/M0-ABC-BASELINE-20261103/RESTORE-ENTRY.md
[results]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/M0-ABC-BASELINE-20261103/FIVE-NODE-RESULTS.md
[idx]: https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/M0-ABC-BASELINE-20261103/FIELD-WINDOW-INDEX.json
