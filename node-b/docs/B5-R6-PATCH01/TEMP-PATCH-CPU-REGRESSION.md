# MPM-B5｜Node-B 候选微调度补丁、Keil 离线构建与 CPU/回放验证报告

> 文档编号：`MPM-B5-TEMP-PATCH-CPU-REGRESSION-V1`  
> 基线提交：`64d07ff33e2fddb46a4a0570d9abfa83adbc3e02`  
> 工作分支：`patch/b5-r6-patch01-20261030`  
> 构建编译器：Keil ARMCC V5.06 update 7 (build 960)  
> 状态：`OFFLINE_BUILT_AND_SIMULATION_VERIFIED_NO_FLASH_WRITE`  

---

## 1. 物理机理与根因分析

### 1.1 R5 历史 29/600 失败的物理源头
在 R5 评价窗口期间，判定器 `assess_b()` 对 600 个连续诊断快照执行以下新鲜度校验：
```python
age = g.signed(x['bio']['last_sample_ms'], t['last_ms'])
if not -10 <= age <= 2500:
    result['failures'].append('B_TEMP_FRESH_SOURCE')
```
- `bio.last_sample_ms`：由 ADS1292 DRDY 中断（250Hz，每 4.0ms 一次）触发，记录最新 ADC 采样到达时刻。
- `temp.last_ms`：由 UART4 RX 接收 GY-641 完整 12 字节温度帧时记录，记录物理帧接收时刻。

在原有任务架构中：
- 串口屏驱动 `SendChar()` 属于完全阻塞式外设轮询（写数据寄存器并轮询等待 TC 发送完成标志）。
- 每次 1 秒周期的 `ValueRefresh()` 需向串口屏连续输出瞬时心率、呼吸率、状态码、有效性标识及报警文本，累计发送约 200 字节数据，在 115200 波特率下单次阻塞 CPU 长达 **17.4ms**。
- `FrameFeed()` 在旧代码中仅在 `HrPage_Task()` 入口处被调用一次。
- 在 17.4ms 的整段阻塞写屏期间，DRDY 中断虽然在后台正常将 4 到 5 个采样帧压入 `EcgQueue`，但主循环无法执行 `FrameFeed()`，导致 `bio.last_sample_ms` 停滞在 17.4ms 之前。
- 此时若 UART4 刚好接收完一个温度帧更新了 `temp.last_ms`，或者 JLink SWD 在该时段异步读取 RAM，二者相减即产生巨大的负延迟（最坏达 **-27ms**），严重跌穿了 `-10ms` 的下限判据！

---

## 2. Node-B 候选微调度源代码补丁

### 2.1 补丁设计原则（零篡改承诺）
1. **真实物理时标**：绝对不篡改 `ADS1292_GetLastFrameMs()` 和 `TimeBase_GetMs()`，保持采样与测温真实时标。
2. **严禁 Clamp 与过滤**：绝对不增加任何强行截断负数或虚假加偏移的作弊逻辑。
3. **零丢帧零降频**：保证 250Hz ECG 和 50Hz RESP 采样连续完整，不牺牲算法输入。
4. **协作式微切片调度**：在阻塞写屏的逻辑空隙及各周期任务后，协作式调用 `FrameFeed(TimeBase_GetMs())`，将滞留帧在产生后立即清空。

### 2.2 源码补丁 Diff（通过构建器注入到 `HARDWARE/hr_page.c`）

```diff
--- HARDWARE/hr_page.c.orig
+++ HARDWARE/hr_page.c.candidate
@@ -420,11 +420,13 @@ static void ValueRefresh(uint32_t now_ms)
         if (st_hr == 3) { strcpy(buf, "---"); }
         else            { sprintf(buf, "%u", (unsigned)s_bpm); }
         SetTextValue(HP_SCR_HOME, HP_TXT_HR, (uchar *)buf);
         StateTxt(HP_TXT_HR_ST, st_hr);
+        FrameFeed(TimeBase_GetMs());  /* 协作点1: 消费排队采样 */
 
         if (st_rr == 3) { strcpy(buf, "---"); }
         else            { sprintf(buf, "%u", (unsigned)s_rpm); }
         SetTextValue(HP_SCR_HOME, HP_TXT_RESP, (uchar *)buf);
         StateTxt(HP_TXT_RR_ST, st_rr);
+        FrameFeed(TimeBase_GetMs());  /* 协作点2: 消费排队采样 */
 
         TxtGB(HP_SCR_HOME, HP_TXT_VALID,
               ((st_hr != 3) || (st_rr != 3)) ? STR_GOOD : STR_BAD);
         TxtGB(HP_SCR_HOME, HP_TXT_CAP, STR_CAP);
+        FrameFeed(TimeBase_GetMs());  /* 协作点3: 消费排队采样 */
     }
     TxtGB(HP_SCR_HOME, HP_TXT_RUN, (s_run != 0) ? STR_RUN : (const uint8_t *)"");
     TxtGB(HP_SCR_HOME, HP_TXT_STOP, (s_run != 0) ? (const uint8_t *)"" : STR_PAUSE);
@@ -443,6 +445,7 @@ static void ValueRefresh(uint32_t now_ms)
     s_st_rr = st_rr;
 
     ProbeRefresh(now_ms);
+    FrameFeed(TimeBase_GetMs());      /* 协作点4: 刷新探头状态后消费 */
 }
@@ -822,18 +825,22 @@ void HrPage_Task(uint32_t now_ms)
         s_t_value = now_ms;
         ValueRefresh(now_ms);
         if (s_cur == HP_SCR_PROBE) { ProbePageRefresh(now_ms); }
+        FrameFeed(TimeBase_GetMs());  /* 协作点5: ValueRefresh 退出后立即排空 */
     }
     if ((now_ms - s_t_qual) >= HP_PERIOD_QUAL)
     {
         s_t_qual = now_ms;
         QualityTick();
         QualityRefresh();
+        FrameFeed(TimeBase_GetMs());  /* 协作点6: 质量统计后排空 */
     }
     if ((now_ms - s_t_min) >= HP_PERIOD_MIN)
     {
         s_t_min = now_ms;
         MinuteTick();
+        FrameFeed(TimeBase_GetMs());  /* 协作点7: 历史推点后排空 */
     }
     if ((now_ms - s_t_rtc) >= HP_PERIOD_RTC)
     {
         s_t_rtc = now_ms;
         ReadRTC();
+        FrameFeed(TimeBase_GetMs());  /* 协作点8: RTC校时后排空 */
     }
     BeepTick(now_ms);
@@ -848,6 +855,7 @@ void HrPage_Task(uint32_t now_ms)
     if ((now_ms - s_t_scan) >= HP_PERIOD_SCAN)
     {
         s_t_scan = now_ms;
         ScanControls();
+        FrameFeed(TimeBase_GetMs());  /* 协作点9: 控件扫描后排空 */
     }
 }
```

---

## 3. Keil UV4 离线构建回执

在独立隔离环境下使用真实 Keil UV4 工具链构建候选固件：
- 执行命令：`python node-b/tools/build_b4_arm.py --temp --candidate-r6`
- 编译器：`D:\keil\ARM\ARMCC\bin\Armcc.exe` (V5.06 update 7 build 960)
- 链接器：`D:\keil\ARM\ARMCC\bin\ArmLink.exe`
- 格式转换：`D:\keil\ARM\ARMCC\bin\fromelf.exe`

### 3.1 构建输出日志摘要
```text
node-b\build\b4-arm-20261030T062335164483Z PASS
*** Using Compiler 'V5.06 update 7 (build 960)', folder: 'D:\keil\ARM\ARMCC\Bin'
Rebuild target 'BIO_V2'
...
linking...
Program Size: Code=37388 RO-data=3148 RW-data=1492 ZI-data=19172  
FromELF: creating hex file...
"..\OBJ\BIO_V2.axf" - 0 Error(s), 0 Warning(s).
Build Time Elapsed:  00:00:03
```

### 3.2 产物指纹与基线对比
| 指标项 | 历史实装基线 (B40928B) | R6 候选补丁固件 (B41012B) | 差异说明 |
|---|---|---|---|
| **构建状态** | PASS | **PASS** | 均为 0 Error(s), 0 Warning(s) |
| **BIN 文件大小** | 40928 字节 | **41012 字节** | 增加 84 字节（微切片指令代码） |
| **BIN SHA256** | `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2` | `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` | 唯一候选镜像哈希 |
| **AXF SHA256** | `9ae047b83e356b85909cb42a060d7f26c342be60a1767bf942fec0cd80d1daa8` | `e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7` | 包含调试符号 ELF |
| **symbols SHA256**| `7a42e31952fff4f0dc5978286c1751eae170174accca397929ea794e2c8cac07` | `07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8` | 符号导出表指纹 |
| **Flash扇区余量** | 8224 字节 | **8140 字节** | 占用 Sector 0..2，余量充分 (>8KB) |

> **非回归证明**：若不加 `--candidate-r6` 参数构建，编译产物二进制哈希仍 100% 还原为历史基线 `a1cf57648ca3...`，证明构建系统零基线漂移。

---

## 4. CPU 回归与多任务负载仿真验证 (`test_timing_simulation.py`)

### 4.1 R5 历史实测 EFS 数据精准回放
- 目标目录：`owner-observed-TEMP_OBJECT-R5-6104c2e6/joint/B/diagnostics-private.jsonl`
- 回放快照总数：600 个连续 JLink SWD 快照
- **回放结果**：精准复现 **29/600** 个负 age 越界，最坏 age 为 **-27ms**。证实该问题在原始固件下属于 100% 可复现的确定性物理时序缺陷。

### 4.2 理论全相位扫描 (0ms 至 1000ms 完整 UI 周期)
以 1ms 为步进遍历异步读取相位与外部温度帧到达时机：
- **旧调度表现**：最坏 age 达到 **-16ms**，越界点数 6/1000；
- **R6 候选调度表现**：最坏 age 严格收敛至 **-3ms**（`>= -4.0ms`），越界点数 **0/1000**（100% 满足 `[-10, 2500] ms` 判据）。

### 4.3 600 秒连续多任务极限负载仿真
- 仿真时长：600.0 秒（6,000,000 个 100us 步长）
- 模拟任务：
  - 250Hz DRDY 中断（每 4.0ms 注入 1 帧）
  - 10Hz GY-641 帧接收（12.5ms 串口传输）
  - 115200 串口屏 17.4ms 阻塞输出
  - 10s 质量评估、60s 趋势、30s RTC、200ms 控件扫描
  - 500ms 周期 JLink SWD 随机相位异步快照读取
- **仿真统计指标**：
  - 总 ADC DRDY 帧数：**149,999 帧**（理论值 150,000 帧，准确率 99.9993%，250.0Hz 零丢帧）
  - `EcgQueue` 最大滞留深度：从旧调度的 **6 帧** 大幅降低至 **1 帧**！
  - 捕获诊断快照数：**1200 个**
  - 快照 age 极值分布：`min = -2 ms`, `max = 99 ms`
  - 判据违背数：**0 / 1200**（越界率为 0.00%）

---

## 5. 协议层非回归验证 (`run_temp_host.py`)

执行 `python node-b/tools/run_temp_host.py`，全链条测试真实 C 语言底层：
```text
compile-parser 0
parser 0
compile-temperature-producer 0
temperature-producer 0
compile-gateway 0
gateway 0
TEMP_HOST_PASS producer_CAN_Gateway_Backend_units_validity_sample_age_NO_HARDWARE
```
证实温度协议解析、CANopenNode 通信、网关转发布、以及云端适配器全部处于完整非回归状态。
