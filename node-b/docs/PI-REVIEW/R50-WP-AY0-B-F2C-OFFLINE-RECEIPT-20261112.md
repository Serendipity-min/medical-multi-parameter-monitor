# R50 · WP-AY0-B F2c 离线交付回执

2026-11-12。依据 [R50 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/90aa6fa/node-b/docs/PI-REVIEW/R50-20261112.md)。源码提交 `cb7788915f62329c0a2d8d8fec8fac985f4cf635`。C 保持断电，本轮未连接 J-Link、未加载 DLL、未写 Flash，未创建现场写入授权。

## 恢复范围与绑定

- 新入口是写入器及监督器的 `--formal-cloud --commit-resume`，独立 scope 为 `WP_AY0_FORMAL_SECTOR3_COMMIT_RESUME`，phase 为 `commit_resume`。绑定新恢复批次卡、独立一次性授权、新现场记录和 R49 包。新现场记录需包含本 scope，旧 R48 写入卡会被拒绝。
- manifest SHA-256 为 `3489afc17a6415422c33bd3b4a9cdefd946d40468d09fb5527e466209209443c`。`stop_receipt` 指向 R49 的 EFS 写入器原始回执，SHA-256 为 `97a0d55335a2083010032e4a535cc72011c240c0f3b2d892f17412285617f9ed`。包加载仍做 manifest 和全部产物的逐字节重建。
- `before_full_sha256` 对应未提交态 `bddbf3cb585314b4564b1878ca72703f2310799d55891a0205d7cc52f88298af`。`after_full_sha256` 对应已提交态 `1808eebf84c763697d731ef5095055c394ca6d74920e89441c3d0fd9d11740b6`。离线读取 EFS 产物，确认两份整片只在提交字处不同。步骤 1 的隔离态备份仍用于绑定原始输入、Options 和身份。
- 写入器在 Halt 前双读整片及 Options，确认身份和未提交态，Halt 后复读 sector3 的 16 KiB，并检查 CRC 和提交字为 `0xFFFFFFFF`。唯一允许的 NVM 写入是 `0x0800C014 = 0x54494D43`。擦除和数据字预算为 0。写后两次整片均须与已提交态一致，Options 和身份须不变，结束保持 Halt。
- 正式主路径也改为 Halt 后只复读 sector3。两条路径在修改 Flash 控制器前判定剩余时间。读取预算取 26.5 s/MiB 和本次两次整片读中较慢者的较大值，并为两次写后整片读、提交、核验和关闭预留时间。主路径再加擦除等待上限 45 s、两个扇区读和逐字开销。预算增加 20%，实际会话上限仍为 180 s。逐字估计取 50 ms，R49 第一阶段从空扇区读回到未提交态读回约 2.97 s，含 83 字及控制开销。
- 监督器输出 `stop_code` 和 `operator_message`，现场提示可区分写前预算不足、会话时限、J-Link 调用超时和人工停止。

## 验证

| 用例 | 结果 |
| --- | --- |
| 旧实现按 R49 停止时刻重放 | `STAGE_VERIFY` 返回 `SECTOR3_SESSION_TIMEOUT`，擦除 1 次、数据字 83、提交 0。 |
| 新正式主路径按 R49 读速重放 | 两次整片读完成后，只复读一次 sector3。预算门槛处模型时刻 52.875 s，剩 127.125 s，估计需 141.575 s。控制器及 NVM 写入均为 0。 |
| 单字恢复模型（26 s/MiB） | 全部核验在模型时刻 104.956 s 完成，距离 180 s 约 75 s。仅写指定提交字，擦除 0 次，写后双读相等且保持 Halt。模型耗时不作为实板实测。 |
| 已提交、擦空、数据漂移或 Halt 后扇区变化 | 全部零写入停止。 |
| 整片读明显变慢或写后第二份读回漂移 | 前者写前停止，后者保留失败证据且无 Reset/Go。 |
| 旧 scope、旧卡或现场记录、错误 manifest 或 R49 回执 | 准入拒绝。 |

定向 pytest **140 项、70 个子例通过**，包括 sector3、FIELD01、统一安装、S1 采集和传输台架。恢复的实板行为和耗时均为 `NOT_RUN`。下一步由 PI 复核 F2c、签发步骤 3′ 批次卡，再由负责人另行放行「WP-AY0-B 恢复」。C 继续保持断电。

## 工具 SHA-256

可用 `python -X utf8 node-b/tools/b5_sector3_write_supervisor.py --formal-cloud --commit-resume --plan` 离线复算以下绑定。

| 文件 | SHA-256 |
| --- | --- |
| `b5_sector3_write.py` | `ac6a4ea63d30067f50d9a1ebc15d0a81ddf4f19c5dca43af05ddb2580e064a17` |
| `b5_sector3_write_protocol.py` | `42a01dab9f3767d21f121ea08c571958e221dcd57342688b5595d16c02a8c2b6` |
| `b5_sector3_write_supervisor.py` | `423ce3e6bca5b6871b53eb9adfdf40702f9f3f0fee5708f454907719a78d2b25` |
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
