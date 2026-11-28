# R104 · B 主线源码离线构建核对卡（只构建，不刷写）

2026-11-20，PI 签发，由 Codex 执行。负责人原话：“推送到 PR #25，ALC 保持关闭，然后让 codex 完成一次离线编码。”依据为 R103 §3。

## 0. 目的、授权与边界
- **目的**：R103 把 R89 C2 合入了主线 `bio_v2.c`，并加了两个默认关闭的编译开关 `BIO_V2_ALC`、`ADS_LOFF_DC`。PI 在 VPS 上用 GCC 只能证明“默认编译与 C2 目标码相同”。实际镜像由 Keil AC5 构建，所以需要 Codex 在 R89 的构建环境里核对两件事：
  1. 主线源码不加算法注入、默认编译时，BIN 是否与现装的 R89 C2 逐字节一致；
  2. 打开 `ADS_LOFF_DC` 后能否正常构建，体积是多少。这个镜像只留作后续候选。
- **授权（本卡签发即放行，仅离线）**：在 Codex 自己的 R89 构建环境里做 Keil AC5 构建、主机测试，写回执，向新分支 `codex/r104-b-mainline-build` 正常推送一次。
- **ALC**：负责人决定保持关闭。本卡不构建 `BIO_V2_ALC=1` 的镜像。
- **不在范围**：
  - J-Link 及一切下载、读写板卡；任何设备上电；
  - MQTT、Broker、服务器、网络服务；
  - 修改本分支源码，或修改 `node-b/tools/build_b4_arm.py` 的入库版本；
  - 提交 BIN、HEX、AXF，这些只报 SHA；
  - 合并、建 PR、删分支；运行 Security Gate。

## 1. 输入（事实）
- **源码**：分支 `claude/r99-r98-offline-test`（PR #25）上含本卡的提交。以下 SHA-256 均按仓库字节计算：

  | 文件 | 行尾 | SHA-256 |
  |---|---|---|
  | `node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c` | LF | `cded912b67fa3a8f0f333e2c02dc7ef832baae111caf51f682faf06a116650d5` |
  | `…/HARDWARE/bio_v2.h` | 同仓库 | `76198016006ab8de6126a7cb051aeb3ab296c5655152c74cf5565bd85aba0913` |
  | `…/HARDWARE/ads1292.c` | CRLF | `2a7e375aafe36a2004477b2adbffc9c34dad2e9af23e16efb5f33046b04c20fe` |
  | `…/HARDWARE/ads1292.h` | CRLF | `74e7bc6a25341ffc343d6d73de88e71d2e6cc2d8366de7b9eec21d213f34bbcc` |

  Windows 签出后如果行尾被转换，需同时报告转换后的 SHA 和统一行尾后的 SHA，后者应与上表一致。
- **R89 C2 基线**（`codex/r89-b-c2@23ce6c9` 回执）：
  - 应用 BIN 40,576 B，`f81063c9392a46924a1156d9851a24e47cc36f406b0980f5cfdbf7093093c540`；
  - Code / RO / RW / ZI 为 36,956 / 3,144 / 1,480 / 18,104 B；
  - 当时注入的 `bio_v2.c` SHA 为 `dcaba6fe…a9c3e7`，与 `analysis-r83-r96/scripts/r89/src/bio_v2_c2.c` 逐字节相同。
- **构建命令**：R89 的构建命令是 `python -X utf8 node-b/tools/build_b4_arm.py --candidate-r6 --diag-reason --diag-cap --algo-c1 --algo-c2 --dsp-library <已核验冻结库>`。其中 `--diag-*`、`--algo-*` 只存在于 Codex 本地的构建脚本，仓库版没有。本卡沿用该本地脚本，回执需写明它的 SHA-256。

## 2. 构建（Keil AC5，同一环境、同一冻结 DSP 库）
| 编号 | 命令差异 | 源 | 预期 |
|---|---|---|---|
| K0 对照 | 与 R89 完全相同（含 `--algo-c1 --algo-c2`），用 R89 时的源 | R89 源 | BIN = `f81063c9…`；不一致即**全部 STOP**（说明环境漂移） |
| K1 主线默认 | 去掉 `--algo-c1 --algo-c2`，其余同 K0；构建副本的 `HARDWARE/` 取 §1 四个文件 | 本分支 | **PI 预测** BIN = `f81063c9…`。这是预测，没有验证 |
| K2 LOFF | 同 K1，仅在构建副本的 Keil `Define` 里追加 `ADS_LOFF_DC=1` | 本分支 | BIN 与 K1 不同；应用 ≤ 49,152 B；0 错误 0 警告 |

- **源码清单**：每个构建都要输出编译源码校验清单（文件名和 SHA）。K1 与 K0 的差异应只在 `bio_v2.c`、`ads1292.c`、`ads1292.h` 三个文件。
- **K1 不一致时**：不改任何源码，标记 K1 FAIL，照常做完 K2 和 §3。回执附 K0 与 K1 的源码清单差异，以及 map 文件中 `bio_v2.o`、`ads1292.o` 的各段大小。
- **K2 的寄存器预期**：`LOFF_SENS` 回读应为 `0x0C`（初始化掩码 0xFF）。这一项只能上板验证，本卡不做。

## 3. 主机测试
1. **算法主机用例**：
   - 命令：`python -X utf8 node-b/firmware/biov2/tests/run_host.py --c1-cases --c2-cases`，环境变量 `NODE_B_TEST_OUT` 设为一个新目录。
   - 预期：**57/57**，旧用例 27/27，`algorithm_sha256 = cded912b…650d5`。
   - 注意：R103 把该脚本换成了 R89 用过的扩展版，现在从 PATH 找 `gcc`，不再写死 `C:/mingw64/bin/gcc.exe`。
2. **构建脚本单测**：`python -m unittest discover -s node-b/tests -p test_build_b4_diag_reason.py -v`。R89 时为 9/9，本次照常运行并报告结果。

## 4. 回执（`codex/r104-b-mainline-build`，从本卡所在提交新开，只加回执文件）
- **工具**：Keil AC5 版本、本地构建脚本 SHA、冻结 DSP 库 SHA、gcc 与 Python 版本。
- **K0、K1、K2 各自**：完整命令行、真实退出码、错误和警告数、Code/RO/RW/ZI、应用 BIN 的大小与 SHA-256、源码清单。
- **比对结论**：K0 与 R89 是否一致，K1 与 K0 是否一致，逐字节比较；K2 的体积余量。
- **测试**：§3 两项的原始输出摘要和退出码。
- **判定**：每项写 PASS、FAIL 或 NOT_RUN。上板一项写 NOT_RUN。
- **原件**：BIN、HEX、AXF 保存在 Codex 的受限构建目录，不入库。
