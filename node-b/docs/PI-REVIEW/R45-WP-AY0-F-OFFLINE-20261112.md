# R45 · WP-AY0 F 固件离线回执

**2026-11-12 · 送 PI 复核。** 源码 `79143baf6d5251ed3a599017fde515efa4bd5d11`，固件基线 WP-AX `b057a65e886cc0000db10faea30733162d19f083`。本次完成 F。正式云服务、实板和 Flash 验证为 `NOT_RUN`。 [R45 §3、§5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/3fe278b/node-b/docs/PI-REVIEW/R45-20261111.md)

## 正式构建档位

| 项目 | 带 `--formal-cloud` |
| --- | --- |
| 入口 | 五板 WP-AX 自动启动路径，115200 透传、4 个 QoS1 槽、音频关闭 |
| TLS 端口 | 8883。透传的隔离档位仍校验 28895。 |
| Gateway ID 与主题 | `GW-C-001`，`mpm/v1/GW-C-001/…`，含遗嘱、节点状态、实时与补传 |
| MQTT 用户名与 client ID | `gateway-c` / `gw-c-001`，精确匹配二元组。client ID 为本轮固定常量，与 sector3 打包器一致。 |
| 数据来源 | 实时生理遥测为 `LIVE`、`synthetic=false`。补传仍用 `REPLAY`。网关状态、节点状态及事件保留 WP-AX 的来源语义。 |
| 链路与配置 | 沿用 WP-AX 的 TLS 校验、授时门禁、断网保留、重入和恢复逻辑。主机、Wi-Fi 和 MQTT 口令由 sector3 提供。 |

## Windows ARM 制品与复建

Arm GNU Toolchain 14.2.Rel1（GCC 14.2.1，Build `arm-14.52`），STM32F4 SPL v1.4.0。VPS 独立复核可沿用 R43 的环境变量 `P5_ARM_TOOLCHAIN_BIN` 和 `P5_STM32F4_SDK_ROOT`。 [WP-AX 复建说明](R43-WP-AX-FREEZE-20261111.md)

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention --tx-integrity-diag --link-resilience --formal-cloud
```

| 制品 | 字节 | SHA-256 |
| --- | ---: | --- |
| [boot](r45-wp-ay0-f/FIVE_APPLIANCE_C_2S_V1-boot.bin) | 392 | `c9caa44fad7c2eb2c2a05f0ba7c927e9b3e5ad37b773d16d908d0bd8478b1f19` |
| [code](r45-wp-ay0-f/FIVE_APPLIANCE_C_2S_V1-code.bin) | 58,480 | `125c4b61a48a72dc2348aacb868ce31f8b5bd79cc3c26286b2508fac317c85d2` |
| [HEX](r45-wp-ay0-f/FIVE_APPLIANCE_C_2S_V1.hex) | 165,691 | `fed83d655a92ae7c47bad9f3568c381857dac4daf9a3b441cd243ab5b2e96277` |

正式制品的 HEX 数据记录与 boot/code 逐字节一致，仅覆盖 sector0 和 sector4。实际 CAN1、CAN2 RX0、USART3 和 SysTick 中断向量均已核对，安装布局通过统一安装器的离线加载校验。 [安装布局](r45-wp-ay0-f/unified-layout.json)

| 区域 | 占用 | 余量 |
| --- | ---: | ---: |
| sector0 | 392 B | 15,992 B |
| sector4 | 58,480 B | 7,056 B |
| 常规 SRAM | 115,000 B，含链接器保留的堆与栈 | 16,072 B |
| CCM | 61,824 B | 3,712 B |

用同一份源码、工具链及参数去掉 `--formal-cloud`，重新生成 boot、code 和 HEX，与 `r41-wp-ax/` 中的三个冻结制品分别逐字节相等。

| WP-AX 重编 | SHA-256 |
| --- | --- |
| boot | `1692cd7fe7a84e99bce8ae4708ad2a7c7d88280a9e6d2a4a42836a1dea5461bb` |
| code | `0fa2e77469ba02d213541118219f15cd285536edfe45575cf3518f42d2aab922` |
| HEX | `ea8a6a8cee368ad2d5ac39328dcd6e2e0d213f743678236365117237d114fbc7` |

## Host 与 sector3 交接

- `gateway/microphone/test_unified.py` **31 组通过**。新增五节点真实 CANopen 软件入口用例验证正式身份通过、隔离及混配身份拒绝、正式主题、LIVE 遥测、REPLAY 及原有网关状态语义。
- 定向 pytest **131 项、40 个子例通过**。覆盖 `node-b/tests/test_field01*.py`、`test_transport_bench.py`、`test_r18_s1_capture.py`、`test_b5_sector3_plan.py`、`test_b5_sector3_write.py`，以及 `gateway/microphone/test_unified_install.py`。另执行四条构建入口拒绝测试，覆盖单独开正式档、正式档指定 28895、隔离档指定 8883、正式档和 FIELD01 混用。
- `b5_sector3_package.py --formal-cloud` 支持从受限 EFS 下的当前整片备份和正式 MQTT 配置 JSON 生成纯离线计划。沿用旧 Wi-Fi 与时间下界，保留 sector3 尾部和其他扇区。合成夹具验证正式身份、CRC、提交位、TLS 端口、全片字节范围及隔离档位校验。正式口令和实际板卡配置包待 S/B 阶段在受限环境确认。现有硬件写入器绑定旧隔离身份及代次，B 阶段须按新批次卡验收正式配置写入路径。 [离线打包器](../../tools/b5_sector3_package.py) · [旧写入器](../../tools/b5_sector3_write.py)

```text
python -X utf8 node-b/tools/b5_sector3_package.py --formal-cloud --current-full <EFS当前整片备份> --mqtt-private-json <EFS正式MQTT配置> --out <EFS输出目录>
```

正式 MQTT JSON 的字段为 `gateway_id`、`username`、`client_id`、`port`、`host`、`password`。正式云后端升级、令牌轮换、旧模拟停用属于后续 S。正式链路实收和 sector3／应用写入读回属于后续 B。
