# FIELD01 R5 WP-M 主机验证回执

2026-11-09 · **待 PI 书面放行**。镜像 2 沿用 R5 的既定版本。负责人已确认 §6，确认语句已收入 EFS 台账。[R5 任务卡](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/3aa71bc/node-b/docs/PI-REVIEW/R5-20261109.md)

## 启动绑定

- 新增显式 `--no-banner`，默认保持原有横幅触发方式。无横幅模式在 COM15 已枚举时可先打开串口，DTR、RTS 均置低。
- `POWER_ALLOWED` 启动主机观察时限；`PRE_ALLOWED` 由现场协调器在确认本次上电或受控 Reset/Go 完成后创建。备份、安装和写后核验期间只采集串口。两道标记使用全新的 EFS 事务目录，且同一上电会话的总时限从第一次上电算起。
- 发送前归档已排队的字节并清空缓冲，先写 `PRE_SENT.json` 再发送一次固定 PRE。无横幅模式只接受目标一致且 `boot_ms < 45000` 的 `PRE BEGIN` 作为绑定依据。短写、畸形回执、重复记录或发送后的新横幅均结束本次事务。
- 回执新增 `banner_seen` 和 `bound_by`。横幅模式为 `BANNER`，无横幅模式在有效 BEGIN 后为 `BOOT_MS`，缺少绑定证据时为 `null`。原始串口保留在 EFS。[主机入口](../../tools/field01_preflight.py) · [测试夹具](../../tests/test_field01_preflight.py)

## Host 与 Windows 构建

| 项 | 结果 |
| --- | --- |
| Host C | `gateway/microphone/test_unified.py` 原生退出 0，14 组通过。 |
| Host Python | `node-b/tests/test_field01*.py` 原生退出 0，61 项及 8 子例通过。覆盖无横幅、boot_ms 边界、晚到横幅、单发、停止、旧模式和旧 115200 回执。 |
| Windows ARM | Arm GNU 14.2.Rel1 构建退出 0，IRQ 向量核验通过，boot/code/HEX 与镜像 2 的 R4 回执一致。sector4 为 61,948 B，余 3,588 B。 |

| 制品 | SHA-256 |
| --- | --- |
| boot | `e827961fa85f3c492ebef7874137e3c1216bc88d8cb167780bd4fa2c906209e5` |
| code | `7cfb0805021046c77cd98ef5c087a9558e868fd3eabbd4ffe816b5b015aad251` |
| HEX | `89b344c1574861c30453b07e263be1fed1957f97619179a15c52bdfe75554484` |

## 实板状态

WP-N 接线基线和 WP-O 会话 A/B 均为 **NOT_RUN**。Windows 仅枚举到 COM15，开关位置及灯态尚未作为 BP 证据采集。本轮的上电、安装、回退、纯复位和 PRE 计数均为 0。PI 书面放行本次主机版本后，按 CFG-U 从 BP-1 开始。
