# B 恢复批次卡 · WP-AY0：步骤 3′ 补写提交字 + 原步骤 4–6（无真人）

**状态：待负责人另行放行。** 放行须写明日期与"放行 WP-AY0-B 恢复"。R48 批次卡的一次性授权已在 R49 用掉，不能复用；本卡取代 R48 卡的步骤 3，步骤 4–6 照 R48 卡执行，只是绑定的数值按下表更新。执行者：Codex（现场）。依据：R49 停止回执、R50 审查、R51 的 F2c 复核。凭据只在 EFS，不进入仓库、回执和聊天。

## 绑定对象
| 对象 | 值 |
| --- | --- |
| 工具源码 | `codex/field01-preflight@cb7788915f62329c0a2d8d8fec8fac985f4cf635` |
| `b5_sector3_write.py` | `ac6a4ea63d30067f50d9a1ebc15d0a81ddf4f19c5dca43af05ddb2580e064a17` |
| `b5_sector3_write_protocol.py` | `42a01dab9f3767d21f121ea08c571958e221dcd57342688b5595d16c02a8c2b6` |
| `b5_sector3_write_supervisor.py` | `423ce3e6bca5b6871b53eb9adfdf40702f9f3f0fee5708f454907719a78d2b25` |
| 其余 10 项工具 | 与 R48 卡 / F2b 回执相同（PI 已复算） |
| J-Link DLL | `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff` |
| 正式包 manifest | `3489afc17a6415422c33bd3b4a9cdefd946d40468d09fb5527e466209209443c`（R49 已由 PI 核对 host） |
| R49 写入器停止回执 | `97a0d55335a2083010032e4a535cc72011c240c0f3b2d892f17412285617f9ed` |
| 步骤 1 隔离态备份 | 整片 `b898db74fb8dc26cab3635d0b81079a5bfd8d4fff82c207d4c6ea7d253052a3b`，Options `52d5979d…` |
| 写前（未提交态）整片 | `bddbf3cb585314b4564b1878ca72703f2310799d55891a0205d7cc52f88298af` |
| 写后（已提交态）整片 | `1808eebf84c763697d731ef5095055c394ca6d74920e89441c3d0fd9d11740b6` |
| 正式镜像 | boot `c9caa44f…`，code `125c4b61a48a72dc2348aacb868ce31f8b5bd79cc3c26286b2508fac317c85d2`，HEX `fed83d65…` |
| 回退镜像 | WP-AX code `0fa2e77469ba02d213541118219f15cd285536edfe45575cf3518f42d2aab922` |

## 步骤（失败即停，不重试，不自行恢复）
0′. **现场记录（新）**：scope 写 `WP_AY0_FORMAL_SECTOR3_COMMIT_RESUME`；其他四板与热点关闭，无真人，J-Link 只接 C 的 SWD/GND；USB/CAN 冻结，BOOT/RESET 不动；C 已上电就绪。给出 SHA。
3′. **补写提交字**：生成一次性授权（scope `WP_AY0_FORMAL_SECTOR3_COMMIT_RESUME`、phase `commit_resume`，绑定本卡 SHA、0′ 现场记录、上表 manifest、停止回执、备份、`before`=`bddbf3cb…`、`after`=`1808eebf…`，有效期不超过当次窗口），然后执行 `b5_sector3_write_supervisor.py --formal-cloud --commit-resume --execute`。
   - 期望状态 `FORMAL_SECTOR3_COMMIT_RESUME_VERIFY_PASS`，擦除 0 次，数据字 0 个，提交字 1 次；写后双读整片 = `1808eebf…`；保持 Halt。
   - 回执须附上 `prewrite_budget`（已用时间、所需时间、实测整片读速），以及每次整片读的完成时刻。
   - **若写前整片 ≠ `bddbf3cb…`**（零写入停止）：保持现状、断电，报 PI，不做其他尝试。
4. **装正式镜像**：以 3′ 读回的整片（`1808eebf…`）作为保护区基线，执行 `unified_install.py --phase install --cold-boot`，读回核对 sector0/4，并确认其他扇区（含 sector3）不变。
5. **断电**，五板按常规上电，无真人。
6. **验收**（正式页面，新令牌）：a. ≤90 s 网关 ONLINE，至少一个节点出现 LIVE 实时数据；b. 断电后回到"等待设备上电"；c. 再上电，≤90 s 自动恢复。记录时间点并截图。

## 回退（R47 §6）
- 3′ 在写入前停止：C 保持未提交态并断电，等 PI。
- 3′ 写入后读回不符：保留失败证据，不 Reset、不 Go，断电，等 PI。
- 4–6：正式链路异常时保留正式 sector3，必要时重装正式镜像；固件异常时装回 WP-AX（只做本地监护，云端离线）。sector3 不回退。

## 回执要求
步骤 0′–6 每一步给出 PASS/STOP 及证据 SHA；不含口令、令牌和 Wi-Fi 信息。实板结果与 VPS 检查分开写。
