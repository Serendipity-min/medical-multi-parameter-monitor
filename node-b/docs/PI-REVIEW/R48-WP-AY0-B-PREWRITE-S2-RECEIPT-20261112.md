# R48 · WP-AY0-B 步骤 0–2 与 S2 回执

2026-11-12 已收到负责人「放行 WP-AY0-B」及正式服务器 S2 放行。B 批次卡来自 `claude/project-review-v1@1f07bcd`，SHA-256 为 `43bb0919876f315db69fa4f6a64ec0cf15ffbc64ec089f4167976aa80843fadc`。本回执为 B 的 host 复核交接。

## WP-AY0-B

| 步骤 | 结果 | 核验 |
| --- | --- | --- |
| 0 现场记录 | PASS | 仅 C 在只读期间上电，其他四板与热点关闭，无人体参与。现场记录 SHA-256 `c1ca9d29f2dd802f2ec50315da2d06dbfd5188ddc99ebb7f95ce09851dec2102`。卡绑定的 13 项工具、J-Link DLL、正式和 WP-AX 制品均已复算。 |
| 1 双读备份 | PASS | 整片双读与 Options 双读分别逐字节一致，身份与 R42 的 C 一致，J-Link Close 成功。应用为 WP-AX，sector3 用户和 client ID 为 `b5-gateway` / `b5-c-isolated`。整片 SHA-256 `b898db74fb8dc26cab3635d0b81079a5bfd8d4fff82c207d4c6ea7d253052a3b`，Options SHA-256 `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。 |
| 2 正式包 | PASS，等待 PI | `source_full_sha256` 等于步骤 1，generation `6 → 7`。manifest 与所有数据文件通过写入器逐字节重建。原 host 与正式配置 host 相同，正式 Broker 的 8883 TLS 证书校验接受该主机名。 |
| 3 写 sector3 | NOT_RUN | 等 PI 核对步骤 2 的 host。 |
| 4 安装正式镜像 | NOT_RUN | 依赖步骤 3 完成及读回。 |
| 5 冷启动 | NOT_RUN | 依赖步骤 4 完成。 |
| 6 页面验收 | NOT_RUN | LIVE、断电离线、再上电恢复均待测。 |

- 正式 manifest SHA-256 `3489afc17a6415422c33bd3b4a9cdefd946d40468d09fb5527e466209209443c`。
- host 的 ASCII 原文 SHA-256 `c392c13e9fef9cbaedef8ab2a11a39eb5b1577533a611150ebb14778bbbce1f7`，按原文直接计算，无换行。PI 可用其已知正式域名复算。两份 host 原文以及完整绑定信息均在本机 EFS 的 `pi-host-review-private.json`，供受限复核。
- `expected-full-committed-private.bin` 的预期 SHA-256 `1808eebf84c763697d731ef5095055c394ca6d74920e89441c3d0fd9d11740b6`。这是离线预期值，写后读回尚未执行。

C 只读结束后已关机，负责人确认 C 灯灭，其余四板与热点关闭，接线原位。待 PI 明确确认 host 和本 manifest 后，从步骤 3 接续。保留 R47 两级回退，sector3 回退不在批次内。

## S2 正式 WebAI

结果为 **PASS**。用 `79143ba:cloud/ai/facts.py` 配置 `MPM_NODE_PROFILE=five`，WebAI 的查看令牌已与后端当前值一致。源制品为只含该文件的未压缩 tar，10,240 B，SHA-256 `b8124e47587343cc76a92deb7bbb76a67d2f755bf51a1144d6a5f3389de7e8bb`。文件 SHA-256 `df87c974f335bfe779bd7a570a6a5041cd5a45d260ccd9556344b47fc054ad14`。

R48 建议部署整个 `cloud/ai`。其中 `79143ba:cloud/ai/app.py` 的路由只接受隔离身份 `GW-B5-001`，整套替换会拒绝正式的 `GW-C-001`。实际部署只替换 `facts.py` 并改上述两项 env，继续使用既有正式路由和读取器。

- 重启前在副本中，重启后从部署目录以 WebAI 服务账户分别运行合成问答，原有 HTTP 路由对 `GW-C-001` 的 D 板 TEMP 与 E 板 NIBP 返回有效事实，两个阶段均通过。合成问答使用进程内应用，未调用真实模型或 MQTT 发布。
- 重启后实际进程健康检查通过，使用其有效环境的只读 WSS 探测返回 `five / GW-C-001`。真人或设备实时数据、设备音频下行均为 NOT_RUN。
- 仅重启 `medical-monitor-h3-webai.service`。正式后端、Broker、Nginx 及两项旧服务的 MainPID 前后相同。

管理员备份目录为 `/opt/medical-monitor/backups/wp-ay0-s2-79143ba/`，含原运行目录、env、单元和源码制品。回退命令为 `sudo -n python3 /opt/medical-monitor/backups/wp-ay0-s2-79143ba/rollback.py`，恢复旧 `facts.py` 和 env 后只重启 WebAI。回退脚本已解析，本轮未执行回退。回退旧 env 后 WebAI 的查看令牌会再次被当前后端拒绝。

## S 后端归档补记

腾讯保留的 S 原 gzip 解压后，tar SHA-256 为 `2cf13d49d32fbf076eafdc182c7d458cfff0eafaef472609e4b388666cd405e0`，与 Windows 的未压缩归档相同，与 R48 VPS 记录不同。跨环境可用内容清单核对。以 tar 中 15 个常规文件的路径为键、文件 SHA-256 为值，按键排序并用紧凑 UTF-8 JSON 编码，Windows 重建与腾讯原归档的清单 SHA-256 同为 `da62cf15ceb08d1770752baf8583dc3f96f2072fc0a5039712620bc63b758377`。VPS 的内容清单待 PI 独立复算。
