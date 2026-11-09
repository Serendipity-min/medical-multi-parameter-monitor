# FIELD01 PREFLIGHT R4 镜像 2 离线回执

2026-11-09 · **待 PI 复核，S0′ 尚未开始**。构建源码 `7635b48eab5e48379d24b995b092f2a5f5969dd2`。[R4 任务卡](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/6432bce/node-b/docs/PI-REVIEW/R4-20261109.md) · [镜像 1 整改回执](PREFLIGHT-R3-FIELD-SUMMARY-20261109.md)

## WP-J

- 初始 UART 门控接受 8N1、2% 链路速率容差和 flow 0/1。候选及恢复 setter 保留初始 flow，回读确认也要求 flow 相等。setter 以 `SYSSTORE=0` 成功为前置。
- 115200 路径在初始门控和同步通过后直接运行 50 次 GMR，setter 次数为零。门控不符报告 `UART_GATE`，`RESTORE=OK` 表示该路径无需恢复。仅在候选 setter 已确认或回复边界丢失、且有界恢复无法确认时锁定 `PRE_DIRTY`。ACK 丢失可能发生在 ESP 已切速之后，Host 有对应正反例。
- `PRE RETIME` 报告本端切速保护检查的实际结果。为避免控制台输出插入 RX 安静检查与 BRR 写入之间，固件在该原子步骤返回后、向 ESP 发送下一条候选速率验证命令前输出这行。保护间隔仍为 20 ms。主机只解析固定枚举。
- 原应用检查使用独立的被动记录器。R3 回退时的启动验证仍为 `NOT_RUN`。镜像 2 批次的回退与启动检查分开记录。

## 验证

| 入口 | 工具 | 结果 |
| --- | --- | --- |
| `python -X utf8 gateway/microphone/test_unified.py` | Python 3.11.9，MinGW-w64 GCC 8.1.0 | 原生退出 0，14 组 C 用例通过。PRE AT 夹具 31 个场景，覆盖 flow=1 的 S1 和 230400、flow 2/3、parity 拒绝、无 setter、恢复失败锁定。MMIO 夹具覆盖全部六个 RETIME 原因。 |
| `python -m pytest -q <4 个 test_field01*.py 加启动检查夹具>` | Windows Python 3.11.9 | 原生退出 0，46 项和 8 子例通过。包含被动启动观察器的限时、精确横幅及无写接口。 |
| Windows ARM | Arm GNU 14.2.Rel1 GCC 14.2.1，SPL V1.4.0 | 构建退出 0，IRQ 向量核验通过。sector4 **61,948 B**，余 **3,588 B**，较镜像 1 增加 332 B。 |
| VPS ARM | Arm GNU 14.2.Rel1 GCC 14.2.1，SPL V1.4.0，Python 3.12.3 | 构建退出 0，IRQ 向量核验通过。boot、code、HEX 与 Windows 逐位一致。 |

构建入口，两端相同。VPS 以 `git archive --format=tar.gz 7635b48e gateway` 的导出为输入，922,725 B，上传前后 SHA-256 同为 `874099f1a62e06ab91f02decc46b2267c04f0272bde57dcae0eb0853458deda8`。

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --field01
```

| 制品 | 字节 | Windows / VPS SHA-256 |
| --- | ---: | --- |
| `FIVE_FIELD01_C-boot.bin` | 392 | `e827961fa85f3c492ebef7874137e3c1216bc88d8cb167780bd4fa2c906209e5` |
| `FIVE_FIELD01_C-code.bin` | 61,948 | `7cfb0805021046c77cd98ef5c087a9558e868fd3eabbd4ffe816b5b015aad251` |
| `FIVE_FIELD01_C.hex` | 175,435 | `89b344c1574861c30453b07e263be1fed1957f97619179a15c52bdfe75554484` |

| 回执 | 构建目录（均在忽略的 `node-b/build/` 下） | `receipt.json` SHA-256 |
| --- | --- | --- |
| Windows Host | `unified-host-20261109T062854596324Z` | `310c9ea32c63dd07cc1641dda30de9398be0124e0e2e6ad5d5b4611780cba399` |
| Windows ARM | `b4-c-arm-20261109T063135009344Z` | `fd46f7b286c0896e5df4655b1f1307c54059d46a5557c284349404e2246cc236` |
| VPS ARM | `preflight-r4-7635b48e/source/node-b/build/b4-c-arm-20261109T063158816860Z` | `c7c3976473561b6f9da917bba6578f5d1efb481168996c30a88b63d262c62adc` |

## 复核后现场顺序

1. S0′ 先重新双读 C 的整片及 Options。以当前原应用整片为回退基准，其中 sector3 是另行授权的新热点记录。安装镜像 2 仅写 sector0/4，写后整片和 Options 核验。
2. S1′ 的 `NEGOTIATE=OK`、`STRESS n=50 fail=0 uart_err=0`、`RESTORE=OK` 齐全才进 S2。S2 全绿才进 S3。沿用 R3 的停止与复核规则。镜像 2 是最后一个候选，最多 8 次上电，每次至多 210 秒。
3. 批次结束用最后一次回退额度。恢复 S0′ 双读基准的 sector0/4，核对整片及 Options、保留现用 sector3。回退后独立冷启动一次，热点关闭，仅 J5 给 C 供电，被动观察原应用横幅，最多 60 秒。准确横幅和人工断电均已确认后才能标为启动通过。[现场启动检查](PREFLIGHT-R3-FIELD-SUMMARY-20261109.md#镜像-2-批次结束后的启动验证)
