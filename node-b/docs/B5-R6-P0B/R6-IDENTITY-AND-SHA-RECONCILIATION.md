# MPM-B5｜硬件身份、固件指纹与交付哈希独立对账报告 (R6-IDENTITY-AND-SHA-RECONCILIATION)

- **文档版本**: v2.0-P0B
- **基线 Commit SHA**: `2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计提交 Commit**: `8954c8ea96af1eda99f00b927f19fecab3cc3215`
- **审计分支**: `audit/b5-r6-p0b-20261030`
- **repo_ref**: `Serendipity-min/medical-multi-parameter-monitor:node-b/docs/B5-R6-P0B/R6-IDENTITY-AND-SHA-RECONCILIATION.md`
- **source_sha256**:
  - `gateway/b5/flash.ld`: `6f8d169ceea1b12b591b9b1ce4893799c8bf8b84e554d326f39fa2776c5f78c9`
  - `node-b/deployment/current.json`: `6599b4f98108bfb02dc7cba24de7289f63624e525164bc4a737fcfce1543ba71`
  - `owner-observed-TEMP_OBJECT-R5-6104c2e6/C-ro-bundle-private.json`: `973e86c0c4e137b34b107e324dc8c9a3bf3eb4a9bb5b9ca7efd688fc9058b888`
- **review_tool_sha256**: `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91`
- **evidence_type**: `RAW_AUDIT_VERIFIED` / `CODE_INSPECTION`
- **verified_by**: Gemini (Antigravity) 独立审计复核
- **unresolved_items**: 当前实板硬件在未经实板预检上电读取前，物理芯片丝印保持 `actual_hardware_confirmed=false`

---

## 1. Gateway-C MCU 真实型号与内存架构对账 (`GATE-01`)

### 1.1 发现与冲突溯源
在先前提交的 `R6-FREEZE-MANIFEST.proposed.json` 中，Gateway-C 的 MCU 被记录为 `STM32F103C8T6`。经深入审查源代码、链接脚本及受限 EFS 硬件寄存器回执，证实该表述为**严重技术事实偏差**。

### 1.2 源码链接脚本证据
在网关核心构建配置文件 [`gateway/b5/flash.ld`](file:///e:/medical-monitor-node-b5-cloud/gateway/b5/flash.ld) 中明确规定：
```ld
/* 待审批持久化候选：应用只限sector0..2，sector3另作配置；不包含配置加载段。 */
/* STM32F407ZGT6，1 MiB Flash，常规 SRAM 使用前 128 KiB。 */
ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 48K
  RAM (xrw)   : ORIGIN = 0x20000000, LENGTH = 128K
}
```
- **Flash 分区架构**：前三个扇区（Sector 0, 1, 2，各 16 KiB，共 48 KiB）分配给应用程序，Sector 3（0x0800C000 起始）预留给非易失配置；
- **RAM 容量**：分配 128 KiB。
- **体系结构对比**：STM32F103C8T6 属于 Cortex-M3，仅具备 64 KiB Flash（按 1 KiB/2 KiB 页面擦除）与 20 KiB RAM，物理上不存在 16 KiB 大扇区，亦无法容纳 128 KiB 内存寻址。

### 1.3 硬件寄存器实读回执证据
查阅受限 EFS 目录中的网关硬件身份回执 `identity-after-private.json`（SHA256: `0e1392ac80a96ecf719636a7c27b5ded120378b40f9e52de05b6772d26640e67`）：
```json
{
  "cpuid": 1091551809,
  "device_id": 268919827,
  "uid_hex": "3300540006504d3256313120",
  "capacity_kib": 1024,
  "optcr": 268413677,
  "flash_sr": 0
}
```
- `capacity_kib = 1024`：芯片内部存储器容量寄存器（`FLASH_SIZE`）读取值为 **1024 KiB (1 MiB)**；
- `cpuid = 1091551809 (0x410FC241)`：ARM CPUID 明确为 **ARM Cortex-M4 r0p1**；
- `device_id = 268919827 (0x10076413)`：`DBGMCU_IDCODE` 低 12 位 `DEV_ID = 0x413`，在 ST 官方手册中唯一指代 **STM32F405xx / STM32F407xx**；
- `optcr = 268413677`：存在 Flash 选项控制寄存器（`FLASH_OPTCR`），该寄存器为 STM32F4 系列特有。

### 1.4 对账裁决 (`C_MCU_IDENTITY_VERIFIED`)
- **芯片型号判定**：Gateway-C 实际运行的核心微控制器为 **STM32F407ZGT6**（Cortex-M4，1024 KiB Flash，128 KiB RAM）；
- **冻结字段规范**：在未进行现场开壳肉眼确认芯片表面激光丝印前，R6 机器清单中记录为：
  `"mcu": "STM32F407ZGT6", "actual_hardware_confirmed": false`，严禁再将其误写为 STM32F103。

---

## 2. Node-B 固件与全 Flash 哈希对账 (`GATE-02`)

### 2.1 历史 B4 部署 vs R5 实装固件
在历史文件 [`node-b/deployment/current.json`](file:///e:/medical-monitor-node-b5-cloud/node-b/deployment/current.json) 中记录：
```json
{
  "deployed": {
    "commit": "dca9a23f357a391c232b0e5248b5685562bf1c98",
    "bytes": 39948,
    "bin_sha256": "676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82",
    "full_flash_sha256": "a1abed50a4c4dbab142a2319d61c047bc43b6816dd62754a080e3f7e12415091",
    "scope": "ISOLATED_B4_BENCH_ONLY_NOT_FORMAL_CAN_DEPLOYMENT"
  }
}
```
**澄清**：上述 `a1abed50...` 是第四阶段（B4）历史孤立台架测试时的 39948 字节固件，**绝不是 R5 阶段实装的 Node-B 固件**！

### 2.2 R5 实装 Node-B 固件 (B40928B) 真实基线
经对照负责人签发的《MPM-B5-GEMINI-R5-DUAL-AUDIT-EXECUTION-CONTRACT.md》第 33 行及《MPM-B5-C-REPAIR-R4-EXECUTION-CONTRACT.md》第 18 行：
- **固件代号**: **B40928B**
- **固件大小**: 40,928 字节
- **BIN SHA256**: `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`
- **完整 Flash SHA256**: `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae`

### 2.3 Gateway-C 固件 (C49132B) 真实基线
- **固件代号**: **C49132B**
- **完整 Flash SHA256**: `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`
- **身份回执 SHA256**: `0e1392ac80a96ecf719636a7c27b5ded120378b40f9e52de05b6772d26640e67`

### 2.4 当前现场实板状态声明
在当前 R6-P0B 离线阶段，由于禁止任何 J-Link / SWD 连接与设备上电，当前实板 Flash 是否被改写属于**离线不可核验状态**（标记为 `NOT_VERIFIED_LOCALLY_WITHOUT_HARDWARE_PREFLIGHT`）。必须在未来取得独立书面授权的 R6-P1 只读预检中，通过只读校验重新验证实板是否保持 `ceebec5a...` 与 `9bba23b4...`。

---

## 3. Git 提交字节 SHA256 与评审原件哈希对账 (`GATE-03`)

### 3.1 R5 actual-review.json 真实基线哈希核验
使用 Python 对仓库中的三个实际联评 JSON 文件求原始字节 SHA256：
- **ECG60-WINDOW-01/actual-review.json**:
  - Git Blob SHA256: `c1f6dfe92286c30ea35a2e9c42682f51747c2f5076e0616e9157dd9461ab5631`
- **TEMP_OBJECT-WINDOW-01/actual-review.json**:
  - Git Blob SHA256: `6fc3ec9f963fcc1caa03cc3e54c5a9727998b78b941410a8058972d7001f737f`
- **RR15-WINDOW-01/actual-review.json**:
  - Git Blob SHA256: `20e88c85330ed18900c78b23b77a67a2549c8a8979b2284527f3bb5de9af4711`

*(证实：前序报告中曾误引脱敏中间件哈希，现正式以 Git 原始字节为准)*

### 3.2 提交 `8954c8e` 交付的九份文档 Git Blob 字节哈希

| 文件名 (node-b/docs/B5-R5QC-R6-P0/) | Git Blob 字节 SHA256 (git show 8954c8e:...) | 字节数 | 换行符形式 | 差异说明 |
|---|---|:---:|:---:|---|
| `ECG-ROOT-CAUSE-MATRIX.md` | `77066b289a270d57a5b9fb83edb0cd8a7329f24238e7b0426d233c37fba2728e` | 8999 | LF (`\n`) | 与本地文件一致 |
| `FINAL-PI-REVIEW-PACKET.md` | `fa491ebff49dc38efc7e04066e4d52d8cd236f24b089ccf912cf1bbe63830fe2` | 9952 | CRLF (`\r\n`) | Windows 写入导致换行符为 CRLF；其内部早期表格引用的为初稿临时哈希，本次已全量修正 |
| `R5-QC-EVIDENCE-LEDGER.md` | `8be664c114a65ee01e160ea59de4c4568c7c25eb0a8ff909056adeaecf5576e4` | 7658 | LF (`\n`) | 与本地文件一致 |
| `R5-QC-ISSUES-AND-ERRATA.md` | `1958cd79ad5c5f38372fbe5039a3aa6332ac6a7c97497d2ffba8dea846d7c9be` | 7838 | LF (`\n`) | 与本地文件一致 |
| `R5-QC-REPLAY-RECEIPTS.md` | `2838d9d60c45f82b6870d4ff1eef6bc4b5340078a79ca3c00748a28f9ecaf6fb` | 7514 | LF (`\n`) | 与本地文件一致 |
| `R6-FREEZE-MANIFEST.proposed.json` | `76e6f8b4600285587cf37a6b80e8b7c5d06d4c31d5458a307b314db6f2aff2fd` | 4762 | LF (`\n`) | 与本地文件一致 |
| `R6-ONE-BATCH-REMEDIATION-PLAN.md` | `803309f5d554c094795c8214568af170b0249959a9dd3ecfe3c31b8dca7fd0b1` | 8317 | LF (`\n`) | 与本地文件一致 |
| `RR-HR-ARTIFACT-ANALYSIS.md` | `5d7649630f37f749ac8498f96b87d379be234e9b5479bf5d8c84180ab8140c14` | 8665 | LF (`\n`) | 与本地文件一致 |
| `TEMP-TIMING-CAUSAL-ANALYSIS.md` | `e47267959ed35aabeb63c1c3eadb156a17bee1f4bac4163d1b7afa5ab6bec30d` | 9817 | LF (`\n`) | 与本地文件一致 |

---

## 4. 审查结论

1. 确认 Gateway-C MCU 为 STM32F407ZGT6，完成 `GATE-01`。
2. 确认 R5 实装 Node-B 固件指纹为 `ceebec5a...`，澄清历史 B4 `a1abed50...` 偏差，完成 `GATE-02`。
3. 建立真实的 Git Blob 字节哈希基线，解释了 CRLF 与自引用哈希成因，完成 `GATE-03`。
