# R47 WP-AY0 F2b 离线交付回执

2026-11-12。依据 `claude/project-review-v1@b4b759a` 的 R47 §6。源码提交 `7748471622a71b370e73d13c81e33e1a326c9314`。

## F2b 正式 sector3 工具

`WP_AY0_FORMAL_SECTOR3_OFFLINE_V1` 的 manifest 新增明文 `host`，与待写记录中的 ASCII 主机名一致。校验逐个 DNS 标签并遵守 Flash 字段的 64 字节上限。空值、非 ASCII、IP、`localhost` 及其下级名称、端口和 URL 均拒绝。合成夹具确认 manifest 不含 Wi-Fi 或 MQTT 口令。

`load_formal_package()` 从待写记录重建 manifest 和所有二进制文件，逐字节核对。改写 manifest 的主机名或仅改动 JSON 字节并更新外层 SHA，均被拒绝。F2 的准入条件继续适用。必须先确认新鲜整片读回 SHA 与打包输入一致，只写 sector3，提交后整片读回须等于 `expected-full-committed-private.bin`。

Windows 定向 pytest 通过 135 项、61 个子例，覆盖 sector3 规划和写入、FIELD01、传输台架、统一安装和 S1 采集工具。本次使用合成配置，实板写入为 NOT_RUN。

B 批次卡应绑定以下 `tools_sha256` 和既有 DLL SHA，并使用正式工具重新生成的包及其 manifest SHA。现场操作仍需 B 批次卡单独放行。

| 文件 | SHA-256 |
| --- | --- |
| `b5_sector3_write.py` | `4ec6c6add9c9240840138b2d09054107078bb90c9679c3fb2b496b4f8fffb575` |
| `b5_sector3_write_protocol.py` | `5ba52cb575781b1ad8709d53385aad1ff90c620c910b8e36848c132b1145dbaf` |
| `b5_sector3_write_supervisor.py` | `12270733444be81e8c6868a66c65be65c4714cc06a366479077d61609c3a68be` |
| `b5_sector3_plan.py` | `707a4901dd0fd318df06cbb79e29c4561a61b07ecea76b555bc0dde692f9b254` |
| `b5_g2ro.py` | `e37944f04d35e24496215ac23021355811ef6af8e9fb7a4e4c6c15c4ae1ed0d3` |
| `b5_g2ro_supervisor.py` | `07c72f280fc0f3860132765f04204965b53ca76f62420d65cc26821449d09347` |
| `c_b4_closeout_readonly.py` | `407102391e3319d4bddf5d6d34a5a0a1a69ddc4a4490096865bd06e6dd2eaaf7` |
| `readback_b.py` | `a095665739454398e359accca3cf67e885de1fa51bff756b7f6b5192b0c00116` |
| `runtime_state_b.py` | `39554d2292b50a604c2b28c7aaa31b442a348e2ab65a77f281ae0b56b3b8ad46` |
| `live_state_b.py` | `bdf04c16f74e93028a55a7db244f0a2b6f683dfb987e61d41470f2bf3debde6c` |
| `resp_exploratory.py` | `2b6a176b3568403fc8ba2e8ede92f537833d654112603a0b221e00e775762d77` |
| `b4_recovery.py` | `fa93222b833f2f010d068b0cac97c73db7430c7eb68316d84441d60539c76213` |
| `b5_sector3_package.py` | `ba2e1dfb4c2bed39a30985a4a93d1d9361d5a3547be8aff27cb193d65923ce64` |
| J-Link DLL | `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff` |

## WebAI 只读核对

| 项目 | 实测 |
| --- | --- |
| 数据入口 | `medical-monitor-h3-webai` 的运行配置为 `P6_SNAPSHOT_MODE=MONITOR`。每次请求从监护后端的 WebSocket 读取一次快照。生理数据由后端接入 MQTT。WebAI 当前未启用隔离 MQTT 发布模式。 |
| 网关 ID | WebAI 的请求参数选择网关。部署代码允许 `GW-C-001` 与旧演示 ID `GW-DEV-001`。当前后端的准入列表只有 `GW-C-001`。 |
| 节点档位 | 后端有效配置为 `five`。WebAI 当前运行的事实提取代码没有节点档位开关，按旧版流归属校验。 |
| 轮换后的只读令牌 | WebAI 进程的 `P6_MONITOR_VIEW_TOKEN` 与后端当前值不同。用 WebAI 部署的读取器按实际配置请求 `GW-C-001`，WebSocket 以 1008 关闭。 |
| 当前能否取得快照 | 当前配置不能。仅在同一读取器的独立探测进程中使用轮换后的令牌，保持 URL 和 Origin 不变，成功取得 `node_profile=five`、`gateway_id=GW-C-001` 的快照。该快照网关为 `OFFLINE`，四个节点条目，零数据流。正式遥测仍未验证。 |
| 五节点事实提取 | 用部署版本的提取器分别输入 `TEMP/NODE-D`、`NIBP/NODE-E` 合成快照，均报 `FACT_IDENTITY`。部署代码预期的归属分别是 `NODE-B` 和 `NODE-A`。 |

待单独放行的方案是更新 WebAI 受限配置中的 `P6_MONITOR_VIEW_TOKEN`，更新部署版本对 `five` 的事实映射，保留 `GW-C-001` 接入，验证五节点快照和合成事实后只重启 WebAI。生产服务器配置和服务状态本轮仅只读核对。令牌、口令、真实服务器地址和原始记录均未收入回执。

## S 阶段后端包复现

在项目仓库执行以下命令。

```text
git archive --format=tar.gz --output=wp-ay0-s-79143ba.tar.gz 79143ba cloud/backend
```

复现为 17,736 字节，SHA-256 `6ba7a78bf8d8d692efc7e7479c72e1ef318a9543bf1a2d60ca8a7254776bec3b`，与 S 阶段回执一致。

## B 阶段回退

依 R47 §6 保留正式 sector3。正式链路异常时，必要时重装正式 `125c4b61…`。固件本身异常时装回 WP-AX `0fa2e774…`，C 回到本地监护。本批不开放 F3。五板全程断电，未连接 J-Link 或 USB。
