# R64 · WP-AZ AZ-2 / AZ-3 回执

## AZ-2 云端

**部署及 C 断电验收 PASS。** 2026-11-12，依据 [R64 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/d6a5f29/node-b/docs/PI-REVIEW/R64-WP-AZ-AZ2-AZ3-CARD-20261112.md)。现场确认 C 与 TTS 断电，COM15 未枚举。

- 现网与仓库 ACL 的 `gateway-c` 写通配及 `backend-reader` 正式网关读通配一致。现网另有环境专用规则，逐字节保留。备份存于 `/opt/medical-monitor/backups/wp-az-2c97094-r64-qbmvvk8c`。ACL 原 SHA-256 `e7f4676b772f109d99844363e6e017db4f23e825a2cd73ad183e7332db56993f`，新 SHA-256 `bee2be2f28adc4bd531acaa885613925e63f35911a91615a1ff736c92fa3b03b`。把下列两条移除即可逐字节还原。
- 向 Mosquitto 子进程发送 SIGHUP。其 PID 3525 和包装器 PID 3253 均保持。现有日志未提供独立的 reload 确认行，实际设备收包与发声由 AZ-3 验证。
- 源码 `2c9709474d11d09d8538783d44aea189a1864af8`，release `wp-az-2c97094`。未压缩 tar 为 102,400 B，SHA-256 `e0b8f85b8e7b0309b324a4300a95a81b5a7313cecf1fd109386d09e6661811bd`。18 个归档成员与 Git blob 核对一致，服务器解包后逐文件重算通过。
- `backend.env` 以 S4 为基线仅追加 `MONITOR_BROADCAST_DEVICE=1`，文件和进程环境均已核对。保留 `MONITOR_BROADCAST=1`，HR 键未设置。服务器北京时间 18:00:14.561 完成部署核验。
- 健康接口 `ok`、MQTT 已连接。无令牌 WSS 为 `OFFLINE`，`broadcast:null`、`broadcast_history:[]`。Chrome 新上下文显示「等待设备上电」，P3 页面可用。受限截图 SHA-256 `c5a4fe147d6c2dc48a9685be458b583b2dc8d6f059b33b5aa68f8c2374898685`。

| ACL 账号 | 唯一增量 |
| --- | --- |
| `gateway-c` | `topic read mpm/v1/GW-C-001/voice/broadcast` |
| `backend-reader` | `topic write mpm/v1/GW-C-001/voice/broadcast` |

| 进程 | 部署前 PID | 部署后 PID |
| --- | ---: | ---: |
| webbackend | 1348667 | 1353672 |
| webai | 1244393 | 1244393 |
| Broker 包装器 | 3253 | 3253 |
| Mosquitto | 3525 | 3525 |
| Nginx | 3383 | 3383 |

AZ-2 回滚使用已备份 ACL 并向同一 broker 子进程发 SIGHUP。移除 webbackend 的 `80-wp-az.conf` 后执行 daemon-reload，仅重启 webbackend，回到原 `70-wp-ay-s4.conf` 指定的 S4 release 与 env。

## AZ-3 刷写与现场

AZ-2 回执提交时为 NOT_RUN。负责人已确认 R51 的哈希范围：`1808eebf…` 为配置提交后、正式固件安装前的整片 1 MiB SHA。R51 两份归档中的 16 KiB sector3 SHA 均为 `471baff4…`，AZ-3 使用后者核对 sector3，并要求写前、写后逐字节一致。候选与 WP-AY0 回退镜像的离线 SHA 均已核对。
