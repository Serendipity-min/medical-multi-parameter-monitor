# R78 · B 屏诊断原因码执行回执

2026-11-18（北京时间）。离线构建 **PASS**，实板安装 **NOT_RUN**。分支 `codex/r78-b-diag-reason`。

## 来源与验证

- 签发卡提交 `9bbd1c517c374353f974771d7bbcfa23aeb785d5`，卡片 SHA-256 `84dbb0db2a49d5a69a5f6ca3e3d128d76c8d853551434ea579769aaed14b6b0e`。代码提交 `0cb1fd727452cef3498a985b0a0bee404fb53d78`。
- 冻结源码校验 **PASS**。诊断开关默认关闭。相对于无诊断的 R6 构建，编译副本输入只有 `HARDWARE/hr_page.c` 的 SHA-256 改变。注入只替换探头页“处理建议”的一次文本输出，沿用现有刷新。显示为 ASCII，工频占比四舍五入后限制在 0–100，信号强度取整后限制在 0–999999。
- 主机测试 **PASS**。命令 `python -m unittest discover -s node-b/tests -p test_build_b4_diag_reason.py -v`，2 项，退出码 0。验证锚点唯一和实际注入 C 代码的典型值、边界值。
- 无诊断基线 **PASS**。本机构建器的旧 DSP 库路径不存在，首次执行在查找依赖时以 1 退出。通过 `--dsp-library` 显式指定原 B 启动修复归档中的同 SHA-256 库（`ba416f23efb992105c36b67d9002d8142e38877d1010c0e0a1d0f74b83325ab7`），保留库哈希门槛。最终代码只启用 `--candidate-r6` 时，AC5 退出码 0，BIN 40,040 B，与现场安装记录指向的归档 BIN 逐字节一致，SHA-256 `f2276540bb8ca92551d08b78aecfdf31346597d9e273783f456be90c67014991`。
- 诊断构建 **PASS**。使用同一 DSP 库和 Keil AC5 V5.06 update 7 (build 960)，启用 `--candidate-r6 --diag-reason`，退出码 0，0 错误、0 警告。Code / RO / RW / ZI 分别为 36,744 / 3,144 / 1,480 / 18,088 B。BIN 小于 49,152 B 扇区边界。

| 产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `R78_DIAG_REASON_NODE_B.bin` | 40,360 | `24612613b307558975c84ff3f763f5fd61439a1b60ac30744184e5a2eca0db0d` |
| `BIO_V2.axf` | 775,076 | `315e49d9a9fe75797f608f32f913f1596cce7baffaadf67c7e8658ed7e5b8694` |
| `BIO_V2.map` | 276,640 | `f994f763d5a2dd806e283e05556dd3b381812e9dac3c1bcfa8b2d590d0958540` |

基线和诊断构建回执分别保存在本工作树的 `node-b/build/b4-arm-20261118T011635438705Z`、`node-b/build/b4-arm-20261118T011653981394Z`。

## 实板状态

负责人授权 R78 回退一次，并指定使用现有 `ai_serial_console` MCP 经 USB_232 烧录。查阅本机实现确认其下载入口固定为 COM15 和 `ai_serial_console.bin`。它所调用的 `stm32loader 0.7.1` 未收到擦除长度时执行整片擦除，`--verify` 只读回所下载的 BIN 长度。该入口无法执行 R78 的 sector0–2 限定、写前两次整片读回和写后全片、options、身份核对。R78 安装器 scope 待确定现场使用的安装路径。

| 项目 | 状态 |
| --- | --- |
| S0–S2 实板准备、写前两次整片读回、写入、写后核对 | NOT_RUN，端口打开、读回、下载、Reset/Go 均为 0，无安装器退出码 |
| 写前整片预期 SHA-256 | `328d48e3567e2fa18a2fee9b0cca831578cdb44364caf8ef575c1d5bbbef99ae`，来源为签发卡 |
| options、身份、sector3–11 对照 | NOT_RUN |
| S3 模拟器、屏幕照片及诊断串原文 | NOT_RUN |
| S4 可选云端 | NOT_RUN |
| S5 硬件状态 | 现场报告五板断电、J-Link 未连接、USB-TTL 留在 C 板。本次仅操作主机文件 |
| 回退一次 | 已授权，NOT_RUN，次数未使用 |
