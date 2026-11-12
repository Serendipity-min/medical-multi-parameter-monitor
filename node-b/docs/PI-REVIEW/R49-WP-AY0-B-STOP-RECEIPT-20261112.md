# R49 · WP-AY0-B 步骤 3 停止回执

2026-11-12。依据 [R49](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/7934a72/node-b/docs/PI-REVIEW/R49-20261112.md) 和 [R48 批次卡](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/1f07bcd/node-b/docs/PI-REVIEW/R48-B-CARD-WP-AY0-20261112.md)。步骤 0–2 的首次回执见 [R48 交接](R48-WP-AY0-B-PREWRITE-S2-RECEIPT-20261112.md)。

| 步骤 | 状态 | 证据 |
| --- | --- | --- |
| 0 现场重新确认 | PASS | 五板最初断电。仅 C 由 USB_UART 上电，其他四板及热点关闭，无人体参与，J-Link 只接 C 的 SWD/GND。原现场 SHA 和重新确认后的现场 SHA 均绑定。 |
| 1 双读备份 | PASS（既有） | 此次写入器又在 Halt 前双读整片和 Options，均与备份一致，Halt 后再次读回整片并匹配源 SHA。 |
| 2 正式配置包 | PASS（PI 已复核） | 加载时重建 manifest 和包内文件，完整匹配 R49 固定 SHA。 |
| 3 写 sector3 | **STOP** | 擦除一次，第一阶段计划的 83 个字均发起写入，未提交态整扇区读回和 CRC 通过。提交前预算门槛触发 `SECTOR3_SESSION_TIMEOUT`，提交字写入 0 次。 |
| 4 安装正式镜像 | NOT_RUN | 未写 sector0/4。 |
| 5 五板冷启动 | NOT_RUN | 负责人已确认 C OFF、灯灭，其他四板及热点关闭。 |
| 6 页面验收 | NOT_RUN | 只在步骤 3 前观察到正式 HTTPS 页面和 `five / GW-C-001 / OFFLINE`，页面显示“等待设备上电”。≤90 秒 LIVE、断电回待机和再次上电恢复均未执行。 |

## 步骤 3 绑定与停止位置

| 绑定 | SHA-256 |
| --- | --- |
| 批次卡 | `43bb0919876f315db69fa4f6a64ec0cf15ffbc64ec089f4167976aa80843fadc` |
| 原现场记录 | `c1ca9d29f2dd802f2ec50315da2d06dbfd5188ddc99ebb7f95ce09851dec2102` |
| 本次现场记录 | `f5fccccb778607f239db6709182e6c0ede3d3701922f79a19498fcce2a696cb9` |
| 本次一次性授权 | `360dad394e6fd8f4ece6f9561d26542f91ca245c4ccf6381394034539f7fb89f` |
| 正式包 manifest | `3489afc17a6415422c33bd3b4a9cdefd946d40468d09fb5527e466209209443c` |
| 备份整片 | `b898db74fb8dc26cab3635d0b81079a5bfd8d4fff82c207d4c6ea7d253052a3b` |
| 写后整片预期值（未达到读回阶段） | `1808eebf84c763697d731ef5095055c394ca6d74920e89441c3d0fd9d11740b6` |

以监督器启动为零点，原生读取记录如下。

| 操作 | 完成时刻 |
| --- | ---: |
| 第一遍整片读回（1 MiB） | 26.500 s |
| 第二遍整片读回（1 MiB） | 52.469 s |
| 显式 Halt（返回 0） | 52.516 s |
| Halt 后整片核验（1 MiB） | 78.594 s |
| 擦除后空扇区读回（16 KiB） | 79.844 s |
| 第一阶段未提交态扇区读回（16 KiB） | 82.813 s |
| 失败清理的末次原生调用 | 83.016 s |

`b5_sector3_write_protocol.py` 的 `STAGE_VERIFY` 在扇区逐字节比较和 CRC 核验通过后执行 `deadline(110)`。180 s 总预算要求此处用时不超过 70 s，三次规定的整片读回本身已到 78.594 s。失败阶段是 `STAGE_VERIFY`，监督器未触发强杀。故障回执记录 `PG_CLEARED_CR_LOCKED_ACR_RESTORED_NO_NVM_WRITE`，`close_resume=false`，无 Reset/Go 调用。现场弹窗最初把预留门槛说成达到 180 秒，实际停止原因与时刻以上述原生记录为准。

此次只读回到未提交态，尚无写后整片或正式镜像读回。原 sector3 已擦除，工具的一次性授权已消费，原写入流程的初始整片 SHA 准入条件已不再满足。C 保持断电，待 PI 审查并另行放行恢复流程。未重连、重试、补写提交字或执行回退。

| 本机 EFS 证据 | SHA-256 |
| --- | --- |
| 写入器回执 | `97a0d55335a2083010032e4a535cc72011c240c0f3b2d892f17412285617f9ed` |
| 写入器原生 I/O 记录 | `1d5910fb7c35c3c5100b29786d450416947812370db76b5a660382c9fa37418f` |
| 监督器回执 | `e4ccb6e36c390951f926d30f927ef5bcf02317c1fbcc6e261c241a1c0a017e9d` |
| 失败原因记录 | `8de1bb5ae9e11985146529ef08e1ed797c998b3d55ba9a7f6e0e314e9ef03283` |
| DAP 混合读前置检查 | `86a9105569ea9a4c6c3d6ba44f32c1f70fd5853e9e54e78ebeeb7b8615efec19` |

## S 后端原部署归档的 15 文件 SHA

以下从腾讯保留的 S 原归档按文件字节重算。与 `79143ba` 的 Git blob 比较，4 个文件逐字节相同，另外 11 个仅有 LF 到 CRLF 转换。路径键排序后的紧凑 JSON 清单 SHA 为 `da62cf15ceb08d1770752baf8583dc3f96f2072fc0a5039712620bc63b758377`。

| 路径 | SHA-256 |
| --- | --- |
| `cloud/backend/README.md` | `d915c8e8afbc7fa2e8271ca013c7a968c7aab46fe8bc6d7743f119e5fd58187c` |
| `cloud/backend/app/__init__.py` | `44b7a1dd200886674507e014193cd2823f56a89d0dc88ad37535ce43f9596882` |
| `cloud/backend/app/adapters.py` | `b4b9993d234741edffa420b81f49478fb32dbab7d8ae156e53cae793083afcde` |
| `cloud/backend/app/diagnostics.py` | `5789b398732231f6c228b033da7023eb8e1909d5bbc92ed4e61b5c2a9644a461` |
| `cloud/backend/app/hub.py` | `affd1ef414d2bbac0a1331e6a6af51a62f8406143a3a53ed31971b497bb27334` |
| `cloud/backend/app/main.py` | `7f60e9d76c2dbc2404b4a37ecf0c1f35afd687f2b602077f0c8f81c13372017a` |
| `cloud/backend/app/models.py` | `6cb8fba5054c4bf3b0d7731545978fa7a54387778cff52e2eaebbc39b246afd7` |
| `cloud/backend/app/mqtt_adapter.py` | `4f523116332ca751c9b474ff2779521de89a5afca0ac6523cf4a20e9321b8ad7` |
| `cloud/backend/requirements-dev.txt` | `c48b12f123dd17090c559455e85a7f1720f0bab075be9270d0da99d97dfcea30` |
| `cloud/backend/requirements.lock` | `9953c1d6d23adf1008f13b49aa47788dce846c6cd13f43cb8f395e5d68275a69` |
| `cloud/backend/requirements.txt` | `b2ca09314707ed38ddf0ffa7509edb30b029a8fd3d940957e91c4fe9653d5f3a` |
| `cloud/backend/tests/test_ac_nibp.py` | `7c9f4cdcaed8125abe59b1783227a4de301b730380384107155f4fe386d581e2` |
| `cloud/backend/tests/test_five_node.py` | `5effc5e33ea485d4549e9cf5f8906e124891ab1ecc3fbe844aed0a737e2b341f` |
| `cloud/backend/tests/test_monitor.py` | `c3be11d90af67ecb25ebe751b0fb930e4ce5f668b530ae225bbda24efa78a433` |
| `cloud/backend/tests/test_operations.py` | `079be902f7459171c34fa0c700b1ddf1af1a63c850ebec80d3d284a9d33a9a7b` |
