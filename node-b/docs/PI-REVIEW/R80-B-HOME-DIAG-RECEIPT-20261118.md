# R80 · B 主页诊断 v2 执行回执

2026-11-18（北京时间）。离线门槛及实板安装 **PASS**，模拟器验收待现场回报。分支 `codex/r79-b-home-diag`。

## 离线门槛

- 卡片提交 `80d749d7a20f10c81fd9d78b122bfc4a3132897d`，卡片 SHA-256 `b1fa0da171cb50ace61cf333623232d0d9970e585c48d3f69d53e9c1545256d7`。v2 及安装器提交 `ec5895dff14bf0181d72b57cc880fbd34c010d04`。
- 已重看 R78 封存的 `B-home-ecg60.jpg`（`db272679b5b01a8b8655824ba2188f2c792ad80b8a98c83ae452edc830827c30`）。主页底部在「暂停监护」按钮上方可完整显示「心电/呼吸采集中」。控件实显的 ASCII 容量在 S3 核对。
- 只有构建副本的 `hr_page.c` 编译输入改变。主页未暂停时，控件 20 每秒显示 `H%lu R%lu M%u`（最长 14 个 ASCII 字符）。控件 17 的短串和第 5 页完整串保留。控件 20 初始化先显示原文字样，首轮周期刷新后显示诊断。
- 主机 `python -m unittest discover -s node-b/tests -p test_build_b4_diag_reason.py -v` 退出 0，5 项通过。覆盖控件定位、非主页和暂停时不刷新控件 20，以及典型和最长格式。安装器离线核对了候选和写后整片，模拟验证了双读一致、双读相异、双读一致但基线错误三种情况。
- 同一 Keil AC5 与 DSP 库构建三种镜像。冻结源码校验通过。无诊断 BIN 40,040 B 与 `f2276540bb8ca92551d08b78aecfdf31346597d9e273783f456be90c67014991` 的归档逐字节一致。R78 BIN 40,360 B 与 `24612613b307558975c84ff3f763f5fd61439a1b60ac30744184e5a2eca0db0d` 的归档逐字节一致。
- v2 退出码 0，0 错误、0 警告。Code / RO / RW / ZI 为 36,984 / 3,144 / 1,480 / 18,088 B。构建回执和产物在本地 `node-b/build/b4-arm-20261118T021648449863Z`。

| 产物 | SHA-256 |
| --- | --- |
| `R80_HOME_DIAG_NODE_B.bin`（40,600 B，低于 49,152 B） | `e9f34d78215a57e14a54255f84d8c8ba22b1c5aa8ee0056f97400f59993a5b77` |
| `BIO_V2.axf` | `d907a5c40f9bb0db27d7949e2c6f00ee2f88e26e5550e4b10562664376ecc951` |
| `BIO_V2.map` | `886c2befe2323755b0204ac198f53b323ddc34688851918b54fbe41f5bbe42d1` |
| R78 写前整片基线 | `8b2cd047e9b09b715ef340591c2ae9b051b6bf84691697071e75fa4863d6ee60` |
| R80 写后整片预期 | `7d0e617ed609585e216a8aa258da63767ae8d289d2ec0da11cb7d539756d7d44` |

## 现场

负责人确认仅 B 上电、J-Link 只接 B、ECG 模拟器已接。唯一一次 J-Link 会话于北京时间 10:19:52 开始，10:21:15 写出关闭回执。独立核对两次写前整片读回等于 R78 归档，且写后整片等于预期。19 份会话原始文件已核对在受限 EFS。

| 项目 | 状态 |
| --- | --- |
| B 安装 S0–S2 | PASS，单次会话写入 sector0–2，写后通过后 Reset/Go，Close 完成 |
| 写前两次整片 SHA-256 | `8b2cd047e9b09b715ef340591c2ae9b051b6bf84691697071e75fa4863d6ee60`，逐字节一致 |
| 写后整片 SHA-256 | `7d0e617ed609585e216a8aa258da63767ae8d289d2ec0da11cb7d539756d7d44`，与预期逐字节一致 |
| options、身份及 sector3–11 | PASS |
| 原生动作计数、退出码 | Halt、BeginDownload、WriteMem、EndDownload、Reset、Go 各 1 次。SDK 调用共 258 次，worker 和监督器退出码均为 0 |
| S3 主页、两处诊断显示及断接恢复 | 待现场物理拔除 J-Link、冷启动和模拟器反馈 |
| S4 云端 | NOT_RUN |
| S5 收尾 | NOT_RUN |
| 回退至本轮写前 R78 | 已授权一次，NOT_RUN |
