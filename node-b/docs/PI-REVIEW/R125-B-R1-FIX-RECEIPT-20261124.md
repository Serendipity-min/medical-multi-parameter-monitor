# R125 修订 1 · B 板离线回执

执行日期为 2026-11-26（北京时间）。PR #25 签发提交 `65803a1ba92f469c19e97d8550205e2fc742497c`。卡片 SHA-256 为 `1dd43d62e849f10e8001c3d766d1fc4011b73320fc5d1f9dec52978bcc2ceb26`。

**§2–§3 及安装范围离线核验 PASS。** K0、K1 与 R89 C2 归档逐字节一致，K3 与 R123 现装应用归档逐字节一致。K5 应用 44,200 B，链接 IRAM 45,784 B。

## 构建环境与命令

- Keil MDK Plus 5.35，ARM Compiler 5.06 update 7（build 960）。Python 3.11.9，MinGW-W64 GCC 8.1.0（x86_64-posix-seh-rev0）。
- 冻结 CMSIS DSP `arm_cortexM4lf_math.lib`，13,294,064 B，SHA-256 `ba416f23efb992105c36b67d9002d8142e38877d1010c0e0a1d0f74b83325ab7`，配套 `arm_math.h` 标为 V1.4.5。
- R89 构建脚本 SHA-256 `f0ca6a426004886d21403b1a50f6e453ac7b18f1189692bdbbe538c2c9acca4f`。R123 构建副本 SHA-256 `5d4382cef456e5149d4f680b28191595286af5b30d12610bedbb8de8d8d0a21b`。R125 构建副本 SHA-256 `1edf9cdee79f095da83354b910f37fd8cb9119d32c06ac6ba28cfc5eb74a1508`。
- R125 构建副本沿用 R123 的签发文件覆盖，只在 K5 覆盖 `B4/b_canopen_app.c`。K1 沿用 K3 的 CAN 源码，只追加 `BIO_V2_RR_R1=0` 并采用 R125 的 `bio_v2.c`。

在 `E:/medical-monitor-r89-b-c2` 依次执行：

```powershell
$lib = 'E:/medical-monitor-r83-b-c1/node-b/build/b4-arm-20261118T063619831432Z/firmware/CORE/arm_cortexM4lf_math.lib'
$r123 = 'E:/medical-monitor-node-b-precan-private/20261023/R123-B-R1-20261124T072030Z/build_r123_mainline_private.py'
$r125 = 'E:/medical-monitor-node-b-precan-private/20261023/R125-B-R1-20261126T113540Z/build_r125_mainline_private.py'
# K0
python -X utf8 node-b/tools/build_b4_arm.py --candidate-r6 --diag-reason --diag-cap --dsp-library $lib --algo-c1 --algo-c2
# K3
python -X utf8 $r123 --candidate-r6 --diag-reason --diag-cap --dsp-library $lib
# K1
python -X utf8 $r125 --candidate-r6 --diag-reason --diag-cap --dsp-library $lib --r125-r1-off
# K5
python -X utf8 $r125 --candidate-r6 --diag-reason --diag-cap --dsp-library $lib
```

## §2 构建结果

| 构建 | 脚本 / Keil 退出码 | 错误 / 警告 | Code / RO / RW / ZI（B） | BIN（B） | SHA-256 | 判定 |
| --- | --- | --- | --- | ---: | --- | --- |
| K0 | 0 / 0 | 0 / 0 | 36,956 / 3,144 / 1,480 / 18,104 | 40,576 | `f81063c9392a46924a1156d9851a24e47cc36f406b0980f5cfdbf7093093c540` | PASS |
| K3 | 0 / 0 | 0 / 0 | 40,248 / 3,176 / 1,480 / 44,272 | 43,900 | `cbbafe29bf33bdeec0c7113db4824140b4a4daebe3eaf394b9527028cdeaf104` | PASS |
| K1 | 0 / 0 | 0 / 0 | 36,956 / 3,144 / 1,480 / 18,104 | 40,576 | 同 K0 | PASS |
| K5 | 0 / 0 | 0 / 0 | 40,548 / 3,176 / 1,492 / 44,292 | 44,200 | `9619761bec634fdc061f2fe61e123341e0c79bd0fb60fd47559624f4cb3022c2` | PASS |
| K5 相对 K3 增量 | | | +300 / 0 / +12 / +20 | +300 | | |

K5 距 49,152 B 应用上限余 4,952 B。链接 map 的 `RW_IRAM1` 为 `0xB2D8`（45,784 B，比 K3 多 32 B，包含 1,024 B 栈），距 131,072 B 上限余 85,288 B。启动汇编的 512 B HEAP 段由链接器移除。

| 构建 | 对象 | Code（其中代码区数据） | RO | RW | ZI |
| --- | --- | ---: | ---: | ---: | ---: |
| K3 | `bio_v2.o` | 5,904（396） | 0 | 9 | 26,772 |
| K5 | `bio_v2.o` | 6,108（430） | 0 | 9 | 26,792 |
| K3 | `b_canopen_app.o` | 1,850（206） | 0 | 35 | 2,620 |
| K5 | `b_canopen_app.o` | 1,946（226） | 0 | 48 | 2,620 |

签出文件与仓库原字节一致。已核对卡中 `bio_v2.c`、`b_canopen_app.c`、`b4_node_protocol.c` 的 LF 和 SHA，以及 R123 原有四个文件的 SHA 和行尾。K5 与 K3 的编译清单只差 `HARDWARE/bio_v2.c` 和 `B4/b_canopen_app.c`。

| 构建 | 清单项数 | 清单 SHA-256 |
| --- | ---: | --- |
| K0 | 147 | `732f4c51f5eb261ca1e3b4903ccee730e14bb62085179b1e7834e4131ca5caf3` |
| K3 | 147 | `3d82496a2a12cb1fc88402a6668ce5d8b5e76972d6aab6a212f256da1fe818ff` |
| K1 | 147 | `bc323f531f98062a797982a92389f04ed552b8655d9792f86e979af55570842b` |
| K5 | 147 | `95c5521918a06e452b1c3f2f8f118b52ecac223fa2be515b8704cf4791b40305` |

## §3 主机回归

| 命令 | 原始结果摘要 | 退出码 |
| --- | --- | ---: |
| `python -X utf8 node-b/firmware/biov2/tests/run_host.py --c1-cases --c2-cases` | 61/61，`rr_r1=true`，`not_applicable=["expire_then_isolated_peak_no_old_rate"]` | 0 |
| 同上，加 `--define BIO_V2_RR_R1=0` | 57/57，`rr_r1=false`，`not_applicable=[]` | 0 |
| `python -X utf8 -m unittest discover -s node-b/tests -p test_build_b4_diag_reason.py -v`（R89 工作树） | `Ran 9 tests`，`OK` | 0 |
| `python -X utf8 node-b/tools/run_b4.py --out <新证据目录>`（修复前和 R125） | 两次均 PASS，13 个子项逐项一致 | 0 / 0 |

两组算法源码 SHA 均为 `fa1a7f73266df5a58687de391b026b999dee553eda41b0af9fb23e523f067efd`。R1 开启时 10 次/分用例出值 10，停止呼吸后 20.996 s 判无效，恢复后用例出值 15 次/分。

B4 对照使用现有 R123 回执工作树 `872d5a4`，核对其运行器、测试、固件、CAN、网关和后端受测目录与修复前 `7714245` 一致。两组使用同一台主机及编译器；两项预期负例都返回 1。

| B4 子项 | 修复前退出码 | R125 修订 1 退出码 |
| --- | ---: | ---: |
| `compile-node-b` | 0 | 0 |
| `node-b-protocol`（R125 含新增两条波形断言） | 0 | 0 |
| `node-b-jitter-protocol` | 0 | 0 |
| `compile-ecg-gain4` | 0 | 0 |
| `ecg-gain4-wire-and-json` | 0 | 0 |
| `ecg-gain4-existing-backend` | 0 | 0 |
| `compile-dual-gateway` | 0 | 0 |
| `dual-gateway` | 0 | 0 |
| `dual-gateway-5s-mqtt-pressure` | 0 | 0 |
| `dual-gateway-jitter` | 0 | 0 |
| `c-to-existing-backend` | 0 | 0 |
| `i2s2-conflict-negative` | 1 | 1 |
| `mixed-model-abi-negative` | 1 | 1 |

## 离线阶段的安装范围和授权快照

- 写前应用归档为 43,900 B，SHA-256 `cbbafe29bf33bdeec0c7113db4824140b4a4daebe3eaf394b9527028cdeaf104`。R123 写后实读 1 MiB 与当时预期镜像逐字节一致，SHA-256 `c6e956a767c3eb5b7e4cb2c34328e4fcc263b7d5b0ca117aa9ce406462e77858`。
- 以 K5 覆盖归档的前 44,200 B，核对 sector3–11 字节一致。**预期写后整片 SHA-256** 为 `effd37922418fc1977565b1582c42c4a8efdb1a91821a339f29816d392ea901a`。
- `R125_B_R1_FIX_APP012_INSTALL` 离线核对退出 0，绑定修订卡、当前应用和整片、K5 大小和 SHA、B 的 sector0–2、单会话、零重试。`enabled=false`。安装器 SHA-256 `4495ab246c61369f56b247825f4325e61fd4b6ae17ac95d17d2749a10e9e39a6`。
- 原始构建、测试、BIN、HEX、AXF、map 和安装计划均归档于本地受限 EFS `R125-B-R1-20261126T113540Z`。Git 交付回执。

| 项目 | 状态 | 放行 |
| --- | --- | --- |
| 离线构建、主机回归、安装计划 | PASS | §0 离线授权 |
| B 写入及模拟器 | NOT_RUN | 等待“放行 R125 写入” |
| 真人 | NOT_RUN | 等待 §5 PASS 及“放行 R125 真人，志愿者X” |
| 回退 | NOT_RUN | 未取得回退授权，未执行 |

## §4 实板写入

2026-11-26，负责人放行 R125 写入并确认仅 B 板上电、ECG 模拟器接入、J-Link 只接 B，电脑与导电链均采用电池供电，现场无人体连接。按修订 1 执行。北京时间 **19:52:25.231** 消费单次授权，监督回执于 **19:53:48.775** 落盘。

| 证据 | 结果 |
| --- | --- |
| 两次写前 1 MiB 读回 | 两份逐字节一致，SHA-256 均为 `c6e956a767c3eb5b7e4cb2c34328e4fcc263b7d5b0ca117aa9ce406462e77858`，匹配 R123 基线 |
| 写前应用 | 前 43,900 B 匹配 R123 K3 |
| 写入 | K5 应用 44,200 B，sector0–2 共下载 49,152 B（含原扇区尾部） |
| 实测写后 1 MiB SHA-256 | `effd37922418fc1977565b1582c42c4a8efdb1a91821a339f29816d392ea901a` |
| 与预期整片比对 | SHA-256 一致，逐字节一致 |
| 身份、options、sector3–11 | 校验一致 |
| Reset / Go 与关闭 | 运行态检查通过，J-Link Close 完成 |

**写入、读回及运行态 PASS。** J-Link 一次会话，Halt、BeginDownload、WriteMem、EndDownload、Reset、Go 各执行一次。SDK 计数 258。WriteMem 返回 49,152，Halt、Reset 返回 0，EndDownload 返回通过非负校验。监督器及子进程均退出 0。重试和回退计数为 0。原始读回与私有证据保存在本地受限目录。

## §5 模拟器 MQTT 录制启动

负责人指示先启动 MQTT，稍后开启 WSS。事务 `r125sim-20261126T115404Z` 四项只读订阅于北京时间 **19:54:07.339** 全部确认，上限 60 分钟。录前 MQTT 与 Web 后端的 `mmpm-control status` 均返回 0，服务状态均为 `active`。等待现场拔下 J-Link、B 板断电及 PI 的 WSS 就绪信号。模拟器分段验收待现场数据。

<details>
<summary>K0、K3、K1、K5 完整编译清单</summary>

| 路径 | K0 SHA-256 | K3 SHA-256 | K1 SHA-256 | K5 SHA-256 |
| --- | --- | --- | --- | --- |
| `B4/CO_driver.c` | `4181ed5bb00c80d3ebe78bbb9cb076efa7b4b60f4763d0242d5e18ebd5aa3199` | = K0 | = K0 | = K0 |
| `B4/CO_driver_target.h` | `422177d99481f4e49d398cee6410a2cdb7a4e858b5735c1119a1eedfd00bc880` | = K0 | = K0 | = K0 |
| `B4/OD.c` | `5aeadffde08d15970f566afcf0837532c00a719b99aff0c3a36183ccfcdd27e0` | = K0 | = K0 | = K0 |
| `B4/OD.h` | `b8f8b8bec593662668e584768f928db126c6c58b766fc94ffd80b88c9ff9ee52` | = K0 | = K0 | = K0 |
| `B4/b_canopen_app.c` | `00a7138087f4a78124d25fd4c180e933bdacc08e8703c3754fd28e9b9a159613` | = K0 | = K0 | `fb4513495554f1477ad2bc57bdef987fd0586c232950ec8f84d33e8e90f31eb4` |
| `B4/b_canopen_app.h` | `a73f0d8e2c5358e79f8ce3f63e7cadb7f02c4954add311cf89415b965d4dbb22` | = K0 | = K0 | = K0 |
| `B4/ecg_units.h` | `78611650d6daaff9620275c9a55f9d0966b1be2d094704fc00080c231a612b43` | = K0 | = K0 | = K0 |
| `B4/node_irq.h` | `59d42b66bde0515e927a108d4d1fa639e1d7fbc37e4689606378472c212b5861` | = K0 | = K0 | = K0 |
| `B4/node_policy.h` | `6c67161a18fc1daae242bc77c5abb07ef2b74bdc396e6fd33bb6725a0645ed00` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_Emergency.c` | `be85a4515c3b5b0c0da37e9025a4f60d8eae4fef739d7b4df463c16705bb06cb` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_Emergency.h` | `ebfb8fb2d635f869bd89b25856adc82945a875754683c2b85d3b778acc437791` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_HBconsumer.c` | `8507404f1fcf5e66680699cb3f698ea805d337a6f5c01e7688a780ac54ca0a8e` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_HBconsumer.h` | `73dda4d0fa6ce61f1d6c4aa2a4cf7046e1e15ef6e4effde9ab8e6a9f5f28bc2d` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_NMT_Heartbeat.c` | `2ad2b2f92ea1198de0ca3b28465d50039a8de09f6f33587ee9735c7b63e2589d` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_NMT_Heartbeat.h` | `4da3d1e3bf82e616a47c59096b6a58a12c58454916af4765adcefda31f8ff9bb` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_Node_Guarding.c` | `08549daae43832074b2c5e9f454d7d5793666621f69d37c27ebc6497cd9b9922` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_Node_Guarding.h` | `353e6579061331e57b02480efed3c532d66d90c4a98694ac9e75d17acb682c23` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_ODinterface.c` | `af3672c73c8b2e6141fb59a21d0f8b757240fc77dc25720b446a21a96fc1dd75` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_ODinterface.h` | `6d0335b932871f32b95beabef60a204b07aae7aa6294299a25ede92e3505ac93` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_PDO.c` | `4791d3acaa044fbe4c05b3b9cd4cbe76c07d9534b04adda3f3df12fdc71a2252` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_PDO.h` | `e370c8093356a60ef6cce7f346809182bc241f326090f7ecb568da37fc309201` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_SDOclient.c` | `2c5a779e4ec9e65215e3ebd119dfddcee98bac4d6ea59574e6f6d90d1f3b5529` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_SDOclient.h` | `052abb856a533001afbcc8de5b3404358c5678b56777fdd562c8eb0b5f1d47b7` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_SDOserver.c` | `27d3e86c519bd99e388f57f5b44192a44d75aaf3247aae9e00db13a17fddd00b` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_SDOserver.h` | `1679a82fb5b41114c2c9353b445cf4e408a2aa48082ad65f41da208c3bf5b2c3` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_SYNC.c` | `f140a45ea032cbf360a2fb8429ed7498a37c1e9ecedcb2b5d6dc387ea21c78a9` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_SYNC.h` | `3e9ae95c5b548a645f691829913e2bd118bf8d1857a6e2b8fbb9288eccc954a6` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_TIME.c` | `bea365c4d56bcd83182018c54fa4c2bf921dd835d10f3332ef191a148ff17bdc` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_TIME.h` | `da4dae715a3502f8a7eb88ad6385b8c9d8db6535c748fbf4c4ab733c8f2671fd` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_config.h` | `da059de7fa1108e038f25fa5004202b688538544dee08727f2ea8b3b3cd27503` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_driver.h` | `ab42dae276ff244ebb511cf8d5374f5017891eaa57a1c7696b8a91a06b95d246` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_fifo.c` | `f7bd28caa6af90bd243fddf500058113dd9cf0a22e46638c4b6f0c331fb6c3fc` | = K0 | = K0 | = K0 |
| `CANopenNode/301/CO_fifo.h` | `09d1af2b58bb7f270cad013e2c4b37990d721c73a44dddfe415d94e94f0fa8b4` | = K0 | = K0 | = K0 |
| `CANopenNode/301/crc16-ccitt.c` | `bc9a9278008276eefd264e6724b906230f7f8b3c32183c50443201c4ff4f25b8` | = K0 | = K0 | = K0 |
| `CANopenNode/301/crc16-ccitt.h` | `e503c0483788412f45cabd039155927e2ddd8d688f412a082bd249584d21c33b` | = K0 | = K0 | = K0 |
| `CANopenNode/303/CO_LEDs.c` | `d9147ae486e050d889e00ed1d4565ac5f1899a1cd287e4629e84dff5c0bbe637` | = K0 | = K0 | = K0 |
| `CANopenNode/303/CO_LEDs.h` | `3e61ccad54ef2575e62e936d0e45516acfb056419a84240a6cb3d963862aa4ab` | = K0 | = K0 | = K0 |
| `CANopenNode/304/CO_GFC.c` | `e5a9c2679dcfadcbc80d1cedb5fa247f0ec906223bb5a0a0136e3e093a4513ec` | = K0 | = K0 | = K0 |
| `CANopenNode/304/CO_GFC.h` | `a10aae6bdba97aa31a6af96d3d660f84587df98b70f50242a3a77566b8f500ce` | = K0 | = K0 | = K0 |
| `CANopenNode/304/CO_SRDO.c` | `7ffc75949a8cb677cc75eda5d5fc25a78c5eaeaf63d6b1cf2118ea8acfc2aba5` | = K0 | = K0 | = K0 |
| `CANopenNode/304/CO_SRDO.h` | `712ad749dd9dc1cd2cd73323649dcf61a97fa76bcae83972e43ff652f0215238` | = K0 | = K0 | = K0 |
| `CANopenNode/305/CO_LSS.h` | `78ad6c37377acfbb91337241e66c862df33f61c13e46199149cff0222de9a38c` | = K0 | = K0 | = K0 |
| `CANopenNode/305/CO_LSSmaster.c` | `542102a4656f4c87e703359666cb9cb899c083d141c9b10e89d7b33ed3744d78` | = K0 | = K0 | = K0 |
| `CANopenNode/305/CO_LSSmaster.h` | `b42c04aa71efbbb13f1680b8e5f44e7f771c9ef28db7e994c6dc469f7f147564` | = K0 | = K0 | = K0 |
| `CANopenNode/305/CO_LSSslave.c` | `a635d4735196913bcb5974fbcb5274bbe3de9160cfe411cef069ce4cb2c40643` | = K0 | = K0 | = K0 |
| `CANopenNode/305/CO_LSSslave.h` | `3d3280feb80c342c7008eabd7fc926568a4f6c8588f1b3eb5d355fb2e5cf8a10` | = K0 | = K0 | = K0 |
| `CANopenNode/309/CO_gateway_ascii.c` | `4ced6c4a651f570f14987b4e5e046be65fcc7bd9d99e967e7752b5fb977a6c3f` | = K0 | = K0 | = K0 |
| `CANopenNode/309/CO_gateway_ascii.h` | `a37f2b51ef040a8379e22c9c8f350a43f8a492c32ecae4feff5e1102075259e4` | = K0 | = K0 | = K0 |
| `CANopenNode/CANopen.c` | `880ce212a88b13d00d88cc3ad2bd0361e8eff904645f8d67c85f215805a9b658` | = K0 | = K0 | = K0 |
| `CANopenNode/CANopen.h` | `b4dd719b8fb45f6415e84a8fb78a435d8a1557f41eae36b78298cacf18fce689` | = K0 | = K0 | = K0 |
| `CANopenNode/example/CO_driver_blank.c` | `8abf2786a7f6b274335aa9ad411f9e95737d9b93748be0d7c98c2e1f8f9fb175` | = K0 | = K0 | = K0 |
| `CANopenNode/example/CO_driver_target.h` | `eab367f6aca14ac22eb16a4eb7e2dc22f50a4fa872ffaa66b0c0943edbebb2b3` | = K0 | = K0 | = K0 |
| `CANopenNode/example/CO_storageBlank.c` | `5f000046966e19985ad71f9525dad8e42033a1d37da4fa728ad5d556dc7f58a3` | = K0 | = K0 | = K0 |
| `CANopenNode/example/CO_storageBlank.h` | `3c462bfc478d93692b3571bcc734ad45535909a039e18e543094f0fafe689751` | = K0 | = K0 | = K0 |
| `CANopenNode/example/OD.c` | `ef52b2a2189fd450cda65c4e0bd663478e1dfcaf778d6f2de296705c2e766bc1` | = K0 | = K0 | = K0 |
| `CANopenNode/example/OD.h` | `737d5c0ca4685d8f2acea14c996836bee2845551aaf7db7cf005689b3c7299fd` | = K0 | = K0 | = K0 |
| `CANopenNode/example/main_blank.c` | `d21ef6eccbd3bee61b75dbefd631c69361431949b769856bac472de43eea2446` | = K0 | = K0 | = K0 |
| `CANopenNode/extra/CO_trace.c` | `f6d045ef1a5bce97624cb70894f8219f15159117a68d8afacdef998e3c90113e` | = K0 | = K0 | = K0 |
| `CANopenNode/extra/CO_trace.h` | `7fc4e3bf7f7577920ea5f59a1b7bf3f598c1e7bd0fb5dd8e38259c8612db8ce5` | = K0 | = K0 | = K0 |
| `CORE/arm_common_tables.h` | `126517411c54094b6d350853b997e7414b4a77711d801811b6750208bed63537` | = K0 | = K0 | = K0 |
| `CORE/arm_const_structs.h` | `7b5f63fa5ed80a98068c4157c5f9073cdc1a432016c3916ae3028140c617583c` | = K0 | = K0 | = K0 |
| `CORE/arm_math.h` | `ad247f1cec31c9d33b41288c8eb3b771bc446a5889df28e4e15ec291022f6004` | = K0 | = K0 | = K0 |
| `CORE/core_cm4.h` | `9b7fea7bd9d781849b22130db320b5946b73a4ccb1b297b179cff7e85447c2d9` | = K0 | = K0 | = K0 |
| `CORE/core_cm4_simd.h` | `767a6d37afba9850afaf090faa2ff14730cb61beed8516ab9f3e72853c93a0e0` | = K0 | = K0 | = K0 |
| `CORE/core_cmFunc.h` | `77ac1af1083cc8f62ea260578108e22d6474cd2f9a1c398cad9988768bd29052` | = K0 | = K0 | = K0 |
| `CORE/core_cmInstr.h` | `198df99902af512ffb2a54a7aa3bce7642e8825a30b46b93b5fb6df88851c472` | = K0 | = K0 | = K0 |
| `CORE/startup_stm32f40_41xxx.s` | `fee2962668dbef36f1b03863ce488490738cafcc6f17a89f56dabdd551f73a9d` | = K0 | = K0 | = K0 |
| `FWLIB/inc/misc.h` | `fe0b20dc5129ec5dbfeefdc0b552b6fd5f208e0fab3f64a0aac70819dcd08037` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_adc.h` | `f5d6218c383f4c426f32d36c4263276c4baa11fac55e73a55420bc9c55182c13` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_can.h` | `a3eebee84d8e739789de599b8fa90c608db7c2d28d04d1ef0199317930717120` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_crc.h` | `a458fe147e54f913fdb8d9aac05248d96f2d7e1349ebfbbbf8078bba2c670fb4` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_cryp.h` | `0da14dc2577ca24411dd476ff35cbc341e5d19760a13e642499b54298a21b23e` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_dac.h` | `2c2eeb87b713a4d21a37b59685b9da057665cb793dc822c9a7b5139be7b3b84e` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_dbgmcu.h` | `0db3db80fe1aa17e1f7cae45cc016a3023a7554f1653bc47ee96a25b0116b91a` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_dcmi.h` | `cb9e75b2042d47a5ca20fc5102ffe2626faf8cab6bc7f29f42a24851347ac748` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_dma.h` | `02341e80f9a541076afff5f63600926a687b8b56c5f934ae0236bbbf1fe54633` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_dma2d.h` | `e482dc75e4239757fbaa35337d4c04072963a0716918058666249fa18cd1dbe1` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_exti.h` | `2de6a414a32404eba150f6f06177a38fdd427e3b3eb35caf10f69927f4c055ff` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_flash.h` | `186476404dc1aada0e990770dabc6545f9961503e5ae39890fdabfa92e8adf18` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_flash_ramfunc.h` | `905ba4fcc88b977882b543f6f90583ad9f1e13c00962e21763bd5a603c1da494` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_fmc.h` | `c29f56f845e699f12b020bf7e72aa404c5b5c2bd6bf9a5038b3e7c7e15f0be71` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_fsmc.h` | `c2d804ef66ce58b29f4d2c0865cd6abdc7e56fa4c027059d48190bf8f9e1c2a0` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_gpio.h` | `8ec09c73453016095f18f263da39ea1a8559419584bd2090740cebd69a67f867` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_hash.h` | `ec91e634d86846684da5c52601dd396e61c66d6ed2ebac7f26056961ec4e8a04` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_i2c.h` | `42e56d9bb2b111fdcd45e23a3b0ef4575f5a89198f5139a94f52526f5ab536f5` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_iwdg.h` | `26ecc2a4b5bb925262181d7bd220ebaa5126bc928e6fb76c01e8f4a4664af47f` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_ltdc.h` | `890de684fa058e3db1d516c613dba8258af56b5dafcd5eb6514bafa16393c6f0` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_pwr.h` | `da06bc8d0e93935066b5528b8e90586569675af3ac508539dd58d474e98aacf7` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_rcc.h` | `49a6285869951e419e529cdc33a431abf85c99168484f0bcd06e40a797137fbe` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_rng.h` | `4ecdbb3008a0c1cdd9316df38d36306f823d2848d462609b748805f3d6b2d651` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_rtc.h` | `5245d8b11c02355dfded024c7340258c9def3d1be7f9ea7e02572d80adc65aa1` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_sai.h` | `b6469d9e0d3536aabd85962dda8b9caf9945c5a9717c170af908465f69d5e693` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_sdio.h` | `81c9af6c0f4e5d0c9138ce830db23642896ea809240b42c12e83a138e7198c78` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_spi.h` | `86785aa59c7ee4c0270493121f9fb5f24235f8dcdb199aee795078b7f7c4a6d1` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_syscfg.h` | `d2c9dad92e7f50848b70c6b688c5d7e0ae76bbc4a2afd426e7994357cd8e29c3` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_tim.h` | `01714c33a0fdbbd3f08c530684999765ed4843601aa1f29b2310e835a293c8df` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_usart.h` | `41ab3ee4f6e7ed6d0afcbbbe9905ae6345fccd9b1deffa1346781806fb5a7c7d` | = K0 | = K0 | = K0 |
| `FWLIB/inc/stm32f4xx_wwdg.h` | `2267624089c093cffe2915ef049a094374dc694a9752b59a0a31f38715d1ddff` | = K0 | = K0 | = K0 |
| `FWLIB/src/misc.c` | `4d0b131e42b44e8ad0de1630acf5dccfa7800d2bd952933ea639d79faf3f08c9` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_can.c` | `ee493be61736abf05c1adfc2d0fdfa9a17d01cc8301bf3536a039e8731a5d09f` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_exti.c` | `5332622af20155911e12a2db864654876c85aeab2a20cd7d61b1534f97c18b6e` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_gpio.c` | `3043fe9e52501fad9cea9afa95e741f0697d658471d930610447623784e80bf8` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_rcc.c` | `4169568c167d701fada6c2366d2537c62d194dbe9a311e513fc9ff80061dc998` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_spi.c` | `d170e859aa5bba0bf09c28104dbe2c724f225cc0252ebe6a7327c2b0c0321224` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_syscfg.c` | `50df08b1fa5afa13bc0e41eff85d2d40193a6992a5775f442cba99548d88a695` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_tim.c` | `5148767f785e72eb404d137d9d9198e8a4458c4eca936cc449bcd86e1aa1c7e9` | = K0 | = K0 | = K0 |
| `FWLIB/src/stm32f4xx_usart.c` | `f76877834c69e6f44f6a5daa61191ae06c17ef19c80318b3e05542f7bd6d869c` | = K0 | = K0 | = K0 |
| `HARDWARE/ads1292.c` | `f99c3d567338f95b4cbae5579554d15e3af4928f8b1a39e0f18b9dbd30192ced` | `2a7e375aafe36a2004477b2adbffc9c34dad2e9af23e16efb5f33046b04c20fe` | = K3 | = K3 |
| `HARDWARE/ads1292.h` | `fa5eaf065b6015d15865a783d5b64444fdacaa77c1fbed5f8a14061c2a8bbf28` | `74e7bc6a25341ffc343d6d73de88e71d2e6cc2d8366de7b9eec21d213f34bbcc` | = K3 | = K3 |
| `HARDWARE/beep.c` | `9bcdfb8baee1c4d7a0f956ca0551b830d56a3dd34276e33ac566ffdabf982d80` | = K0 | = K0 | = K0 |
| `HARDWARE/beep.h` | `4b7960c58bca4069638d6ab42d002a767788223517e1fcbc949c4432777e2a6b` | = K0 | = K0 | = K0 |
| `HARDWARE/bio_v2.c` | `dcaba6feafd89989b5921ee08adf4d4a75f4379b6203cf693ed1beff7aa9c3e7` | `1aaf419f58b3249aaf1b1b5a89bf161c96a4e7e6c75a217ebb4e2e635086cb49` | `fa1a7f73266df5a58687de391b026b999dee553eda41b0af9fb23e523f067efd` | = K1 |
| `HARDWARE/bio_v2.h` | `76198016006ab8de6126a7cb051aeb3ab296c5655152c74cf5565bd85aba0913` | = K0 | = K0 | = K0 |
| `HARDWARE/can.c` | `6fd10608a11e7bd23a155a2f594686f1c81e4390d917314d5be2cb587819da8c` | = K0 | = K0 | = K0 |
| `HARDWARE/can.h` | `ef5215dcd0bfb3f963160eac48ae2a6a7c6dfc55389a2f91ec22a5a57b8bce14` | = K0 | = K0 | = K0 |
| `HARDWARE/canopen.c` | `447d2ff2ec32eb10fda4be0ce94bdaeea992c8db5d778ff4afdae07210ae1157` | = K0 | = K0 | = K0 |
| `HARDWARE/canopen.h` | `338e99155f71bbd20b7e500953ea25055e0dfc52b3f0c9a39429369daf6b2aef` | = K0 | = K0 | = K0 |
| `HARDWARE/ecg_frame_queue.c` | `cab4719c4151386acbac422f28af517a5b54c8c3c933a52a9207b1c0140e319f` | = K0 | = K0 | = K0 |
| `HARDWARE/ecg_frame_queue.h` | `c6922d907966865586acd4c1427b34653d4e93d9a5a6d3d1f68278f98ffafc72` | = K0 | = K0 | = K0 |
| `HARDWARE/hr_page.c` | `99cb6e30fcc9ddb8d6f827a9e0d28df9541b535fb87e7a97249319f2259133c9` | = K0 | = K0 | = K0 |
| `HARDWARE/hr_page.h` | `ee5dd7426e95c2c89f122c1c2cc3570ec50feb90ed3e70e364b87de97d51a105` | = K0 | = K0 | = K0 |
| `HARDWARE/spi.c` | `5e09707c47cec710172a4e78e7ca21c15c7359d964d0fbe8bf5c2498243a8ec0` | = K0 | = K0 | = K0 |
| `HARDWARE/spi.h` | `fcc45addcce5a791b345404f77af2327ed5b6cb7167e432e46db8e9bf1815363` | = K0 | = K0 | = K0 |
| `HARDWARE/systick.c` | `bd0666b7c8cd31448d7791fc51866873283a0649648c57a339c8b52908e31a50` | = K0 | = K0 | = K0 |
| `HARDWARE/systick.h` | `c51d0250c353e48068cf34de4d04a4a21c12d86a51e4ee429d9c7671a3e65172` | = K0 | = K0 | = K0 |
| `HARDWARE/timer.c` | `a06d7c4ef0e4a38cc355a6829bedf744436258e8e340b026a966cfcadf6ecaf1` | = K0 | = K0 | = K0 |
| `HARDWARE/timer.h` | `57ba5444ffa77b72c89562496ac12c37055040fb0e47321588f8f0e0b41fa99c` | = K0 | = K0 | = K0 |
| `SCREEN/cmd_process.c` | `698287ab1d42600b719c75cf12de79ba3dfb354f8d5570f12363b707657b8943` | = K0 | = K0 | = K0 |
| `SCREEN/cmd_process.h` | `4ea51ee7781e26c92596a6141978b267809fe2de3821756accc65bf5080b7f43` | = K0 | = K0 | = K0 |
| `SCREEN/cmd_queue.c` | `70226503db0972c91c4490a307f3d4d8d1023049b279867717157a3212604b2c` | = K0 | = K0 | = K0 |
| `SCREEN/cmd_queue.h` | `b48301640a6cc8bc4ef8715a30772ab76c7193c0198dd6ab8c0e8b4710f68123` | = K0 | = K0 | = K0 |
| `SCREEN/hmi_driver.c` | `0cf00eaf0b032f20ead1f172a253c2765816be80264f3026fd7c5ea81e7fd287` | = K0 | = K0 | = K0 |
| `SCREEN/hmi_driver.h` | `ee9a7de81e69f265290fe03c147f0a2df2391db6ebd2b24f0f76d039b1de9738` | = K0 | = K0 | = K0 |
| `SCREEN/hmi_user_uart.c` | `5e8ddf6fde70675bacc84fbbc513a01c2000725a2eb7945c463af436b43c027a` | = K0 | = K0 | = K0 |
| `SCREEN/hmi_user_uart.h` | `aaf15d2cdee3815cac454417a7b7a74e8a4f122e27e37c27472cff4c0efdef93` | = K0 | = K0 | = K0 |
| `SCREEN/hw_config.c` | `ab225cf8477bd4a0cfabc988f26713a9656592bfb91e26c86a0e01a9e8b28490` | = K0 | = K0 | = K0 |
| `SCREEN/hw_config.h` | `3910e830cf87cf9d26b087d9150254543e20001b61d3202dfd04690913b9f0ac` | = K0 | = K0 | = K0 |
| `SCREEN/ulitity.c` | `d5e9eb07cb657e9d9e635099b02413c671158afd5ea38807d0363dd0f18c1075` | = K0 | = K0 | = K0 |
| `SCREEN/ulitity.h` | `44f6f81885dffa53b5c0e21e79f84dfc28b330c0c13a16a989e36e1711e0d299` | = K0 | = K0 | = K0 |
| `USER/BIO_V2.uvprojx` | `0c725c82339a59f0af919683218e4faf8c78bd866584565bd4fc3ff59d5eb5e0` | = K0 | `2cce21407ec63043a4913db1269c1c5446a024d4156ccdb605aa575f9705955d` | = K0 |
| `USER/main.c` | `a0aaa2224022bf2d606f899fa8f1813d3984efe99bfa14c448ef8751771d821f` | = K0 | = K0 | = K0 |
| `USER/stm32f4xx.h` | `f646cccb5b0bbc917be824fff049167a83956169b0e114acdb8c0484985dc26c` | = K0 | = K0 | = K0 |
| `USER/stm32f4xx_conf.h` | `1de02ba948488f61e50a0d217390ec90c0459ed63944acb9854426904469152b` | = K0 | = K0 | = K0 |
| `USER/stm32f4xx_it.c` | `7efb4c9dd77744869ccdc7333f8cf0faa6a1d29b31c8151956f36b4297ea00e7` | = K0 | = K0 | = K0 |
| `USER/stm32f4xx_it.h` | `e7f9b4ad495d3b8ba24e65b3445d135964c10f895a4691c2bd5f50b6c2d14752` | = K0 | = K0 | = K0 |
| `USER/system_stm32f4xx.c` | `b530011f741dfeae02f182a08ea11bfc670d42795c9dec0d98a70041cdcaf54a` | = K0 | = K0 | = K0 |
| `USER/system_stm32f4xx.h` | `50f5887a8d62d774e1bc3d0a2e8892dd43b5d200a2f6d9266f5b747d5810cb0f` | = K0 | = K0 | = K0 |

</details>
