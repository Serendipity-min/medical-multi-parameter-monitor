# R83–R96 ECG/RESP 离线分析：脚本与结果

R83–R96 复核文档所用的离线分析脚本和计算结果。工程口径，不是临床结论。

## 数据不入库
真人 MQTT 原始录制含志愿者的生理信号，按项目约定**不进版本库**。原件保存在受限 EFS 和采集服务器的受限目录中。要复跑时，把下表文件放到本目录的 `r83-capture/`（已被 `.gitignore` 忽略）。

| 文件 | 内容 | SHA-256 |
|---|---|---|
| `r83-20261118T065234Z-node-b.jsonl` | 模拟器、导联断开、踝部（C1） | `4f35c5e5c7de273ece0c2c604e0c1f1351932a4f3955c265ad637ca1f85d5756` |
| `r85-20261118T074904Z-node-ab.jsonl` | 腕部 P1 | `805e3a2a82ddf8f6d02c5989e061ccca934b6bcd145fa27fcceeb75c5916a5d7` |
| `r87-20261118T083445Z-node-ab.jsonl` | 胸部 P2（C1） | `d7ea581282bceb22ad6ea38d9e2e500e049440a7475f2371d1cd4f0814d78f82` |
| `r89sim-20261118T093511Z-node-ab.jsonl` | C2 模拟器验收 | `d9fb397545ca3636f38f8f6cf14399a8fb81cf2a582723e61c5ea71eb751d193` |
| `r89cal-20261118T100701Z-node-ab.jsonl` | RESP 模拟器定标 | `0c0ca99a1943c3205c4df55c07d3e7e5e7a44fc21431f34a19ef03a169918317` |
| `r89human-20261118T102758Z-node-ab.jsonl` | P2 复测（C2） | `d79a836bae533a8b1683b46764209c5d577691b614d2a60284601ab873a544b7` |
| `r91human-20261119T072140Z-node-ab.jsonl` | P2 复测（两次贴片） | `f6bfe1d30a92e74641886a979d869677300d9462f54c9e41e0e218f0d2cd1904` |
| `r92sim-20261119T082651Z-node-ab.jsonl` | 模拟器链路自检 | `3b3ec69a535296dd0e720ab5cbfad780c641ce926d911d0ada64b389ffd0b524` |
| `r94human-20261119T090428Z-node-ab.jsonl` | P2 复测（志愿者乙） | `eee4fa8fc5161f5c1d6fe81de94cb1ed2237808a0fed7b4fafdddb8634bdd2fd` |
| `r100rr-20261119T112442Z-node-ab.jsonl` | RR 真值采集（节拍 10、15、20 次/分） | `0734d690ad5cc0fa7ae46999b7b1815a5a19a131bed31f27cc54e7483f6c696e` |

## 目录
- `scripts/`：R83–R88 的基础脚本，入口是 `load.py`（MQTT 解析与量纲换算）。
- `scripts/r89/`：R89–R94 的分析。
  - C1、C2 源码：`src/bio_v2_c1.c`、`src/bio_v2_c2.c`，以及两者的差异 `c1_to_c2.diff`；
  - `replay_drv.c`：把真实 C 代码编进重放夹具；
  - `run_host_c2.py`：主机用例，含 57 例。
- `scripts/c3/`：R95、R96 的 C3 研究。
  - `drv.c`：直接调用 C2 的 C 代码，作为基线；
  - 候选的浮点原型：`algos.py`（A、B、C）、`algo_d.py` 和 `algo_d2.py`（D）；
  - 评测：`evalc3*.py`、`eval_*.py`。
- `results/`：上述脚本在 2026-11-19 的输出（文本），以及 C1、C2 源码的主机用例回执 JSON。

## 复跑
- 环境：Linux，gcc，Python 3.12。`c3/` 和部分 `r89/` 脚本需要 numpy。
- 在 `scripts/` 或其子目录下运行 `python3 -s -E <脚本>`。不能用 `-I`，否则本地模块导入会失败。
- `r89/`：先编译重放库：
  ```
  gcc -std=c99 -O2 -ffp-contract=off -shared -fPIC -Isrc -DBIO_SRC='"bio_v2_c2.c"' replay_drv.c -o replay_c2.so -lm
  ```
  c1 同理，把 `c2` 换成 `c1`。
- `c3/`：先编译基线库：
  ```
  gcc -std=c99 -O2 -ffp-contract=off -shared -fPIC -I. drv.c -o drv.so -lm
  ```
- 主机用例：
  ```
  NODE_B_TEST_OUT=<新目录> python3 r89/run_host_c2.py --source r89/src/bio_v2_c2.c --c1-cases --c2-cases
  ```

## 结果与文档的对应
| 结果文件 | 对应文档 |
|---|---|
| `r89_replay_rec.txt`、`r89_agree.txt`、`r89_noise_sweep40.txt`、`host_receipt_*.json` | R89 §2.2 |
| `r89_artifact_mc.txt` | R90 §2 |
| `r89_cal*.txt`、`r89_human_cmp.txt`、`r89_noise_src.txt`、`r89_rounds.txt` | R91 |
| `r89_r91_min.txt` | R92 |
| `r89_r92_sim.txt` | R93 |
| `r89_r94_snap.txt` | R95 §2 |
| `c3_*.txt` | R96 |
| `r98_*.txt`（脚本在 `scripts/r98/`；`load2.py` 已按批末时间戳修正时间轴） | R99 |
| `r100_synthetic_controls.txt`（冻结版 PPG-RR：`scripts/r98/rr_frozen.py`） | R100 |
| `r100_eval.txt`、`r100_diag.txt`、`r100_resp_explore.txt` | R101 |
| `r102_resp_r1.txt`、`r102_resp_r1_amended.txt`；`r102_resp_qsens.txt`（q 敏感性，`scripts/r98/resp_qsens.py`） | R102；q 敏感性见 R103 §1 |
| `r103_clock_beat.txt`（`clock_beat.py`）、`r103_alc_equiv.txt`（`alc_equiv.py` + `drv_alc.c`）、`r103_alc_host_noise.txt`（`alc_host_noise.py`） | R103 |
| `r106_polarity_existing.txt`（`qrs_polarity.py`，QRS 主峰极性） | R106 |
| `r107_polarity_r106sim.txt`（`qrs_polarity.py`，R106 模拟器换色各段） | R107 |
| `r109_eval.txt`（`r109_eval.py`：RESP 重新定标、真人 HR/极性/集合平均/分带、RR） | R109 |
| `r111_eval.txt`（`r111_eval.py`，复用 r109_eval：志愿者丙） | R111 |
| `r113_eval.txt`（`r113_eval.py`，复用 r109_eval、r111_eval：志愿者丁，RR 首次有人工计数） | R113 |
| `r117_eval.txt`（`r117_eval.py`，复用 r109_eval、r111_eval：志愿者甲，含坐—躺—坐与 R87 对照） | R117 |
| `r118_c4.txt`（`c4/eval4.py` + `c4/drv4.c`：C2 门限口径预注册比较）、`r118_c4_explore.txt`（`c4/explore4.py`：k 扫描，探索） | R118 |

**注意**：`r89_rounds.txt` 用的是 R91 时的 PPG 去趋势方法，滑动均值在两端补零。R92 起改为按实际点数归一。两种方法对 R87 的结果分别为 588 µV 和 601 µV，结论不受影响；R91 那份录制只能用修正后的方法（见 `r91_min.py`）。
