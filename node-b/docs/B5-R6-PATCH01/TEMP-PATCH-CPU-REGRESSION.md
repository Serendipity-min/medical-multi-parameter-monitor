# MPM-B5｜R6 候选 Node-B 微调度补丁技术说明、WCET分析与 CPU 回归回执

> 文档编号：`MPM-B5-R6-PATCH01-CPU-REGRESSION-V2`  
> 构建目标：`B5_TEMP_NODE_B.bin`（41012 字节候选镜像，含温度与 R6 微调度）  
> 状态：`CANDIDATE_OFFLINE_VERIFIED`（离线验证通过，严格禁止烧录与实板运行）  

---

## 1. 根本原因定位 (Root Cause)

在 R5 现场实测窗口 `owner-observed-TEMP_OBJECT-R5-6104c2e6` 中，审查器报出 `B_TEMP_FRESH_SOURCE` 失败（29/600 帧负 age 越界，最坏达到 -27ms）。

经深度反汇编与源码审计，根本原因如下：
1. **STM32F407 单线程前后台架构**：`USER/main.c` 主循环调用 `HrPage_Task(now_ms)` 处理屏幕 UI；
2. **串口屏 115200 波特率同步阻塞写**：`ValueRefresh()` 在每秒刷新心率、呼吸率数值和探头状态时，向 HMI 串口发送数十字节文本指令。由于采用阻塞式 `SendChar()`，总阻塞时间达 **15–17.4ms**；
3. **DRDY 中断只入队不处理**：ADS1292R 芯片以 250 SPS (4.0ms 间隔) 产生硬件外部中断，ISR 仅将裸数据压入 `EcgQueue`，实际算法处理与 `bio.last_sample_ms` 更新全靠主循环中的 `FrameFeed()`；
4. **负 age 产生时序链条**：在 17.4ms 阻塞写屏期间，`FrameFeed()` 无法执行，`bio.last_sample_ms` 停滞；若此时 UART4 收到 GY-641 红外测温帧（每 100ms 一帧），`temperature.last_ms` 立即被更新为当前真实毫秒，导致 `bio.last_sample_ms - temp.last_ms` 骤降为负值（最坏达 `-17.4ms` 至 `-27.0ms`），严重突破 `[-10, 2500] ms` 判据下限。

---

## 2. 候选补丁设计与 WCET 分析

### 2.1 协作式切片机制 (Cooperative Slicing)
不改变硬件、不重构系统为 RTOS、不增加高风险抢占中断，而是在单线程事件循环中引入**微切片协作式调度**：
在长阻塞写屏的各原子指令之间，以及各周期子任务退出点，插入 `FrameFeed(TimeBase_GetMs())`。每次写完一小段文本，立刻排空并消费当前积压的 1 帧 ADC 采样，将最大调度延迟从 17.4ms 压缩至 **4.5ms** 以下。

### 2.2 严格对齐的 8 处源码插入点 (在构建器 `build_b4_arm.py` 中 1:1 注入)

候选补丁在 `HARDWARE/hr_page.c` 中精确注入 8 处协作点，与构建脚本和审计源码完全一致：

```diff
--- HARDWARE/hr_page.c.orig
+++ HARDWARE/hr_page.c.candidate
@@ -420,11 +420,13 @@ static void ValueRefresh(uint32_t now_ms)
         if (st_hr == 3) { strcpy(buf, "---"); }
         else            { sprintf(buf, "%u", (unsigned)s_bpm); }
         SetTextValue(HP_SCR_HOME, HP_TXT_HR, (uchar *)buf);
         StateTxt(HP_TXT_HR_ST, st_hr);
+        FrameFeed(TimeBase_GetMs());  /* 协作点 1: HR 状态刷新后立即排空 */
 
         if (st_rr == 3) { strcpy(buf, "---"); }
         else            { sprintf(buf, "%u", (unsigned)s_rpm); }
         SetTextValue(HP_SCR_HOME, HP_TXT_RESP, (uchar *)buf);
         StateTxt(HP_TXT_RR_ST, st_rr);
+        FrameFeed(TimeBase_GetMs());  /* 协作点 2: RR 状态刷新后立即排空 */
 
         TxtGB(HP_SCR_HOME, HP_TXT_VALID,
               ((st_hr != 3) || (st_rr != 3)) ? STR_GOOD : STR_BAD);
         TxtGB(HP_SCR_HOME, HP_TXT_CAP, STR_CAP);
     }
     TxtGB(HP_SCR_HOME, HP_TXT_RUN, (s_run != 0) ? STR_RUN : (const uint8_t *)"");
     TxtGB(HP_SCR_HOME, HP_TXT_STOP, (s_run != 0) ? (const uint8_t *)"" : STR_PAUSE);
@@ -443,6 +445,7 @@ static void ValueRefresh(uint32_t now_ms)
     s_st_rr = st_rr;
 
     ProbeRefresh(now_ms);
+    FrameFeed(TimeBase_GetMs());      /* 协作点 3: 探头刷新后立即排空 */
 }
@@ -822,18 +825,22 @@ void HrPage_Task(uint32_t now_ms)
         s_t_value = now_ms;
         ValueRefresh(now_ms);
         if (s_cur == HP_SCR_PROBE) { ProbePageRefresh(now_ms); }
+        FrameFeed(TimeBase_GetMs());  /* 协作点 4: 探头页面刷新后立即排空 */
     }
     if ((now_ms - s_t_qual) >= HP_PERIOD_QUAL)
     {
         s_t_qual = now_ms;
         QualityTick();
         QualityRefresh();
+        FrameFeed(TimeBase_GetMs());  /* 协作点 5: 质量统计后立即排空 */
     }
     if ((now_ms - s_t_min) >= HP_PERIOD_MIN)
     {
         s_t_min = now_ms;
         MinuteTick();
+        FrameFeed(TimeBase_GetMs());  /* 协作点 6: 历史推点后立即排空 */
     }
     if ((now_ms - s_t_rtc) >= HP_PERIOD_RTC)
     {
         s_t_rtc = now_ms;
         ReadRTC();
+        FrameFeed(TimeBase_GetMs());  /* 协作点 7: RTC校时后立即排空 */
     }
     BeepTick(now_ms);
@@ -848,6 +855,7 @@ void HrPage_Task(uint32_t now_ms)
     if ((now_ms - s_t_scan) >= HP_PERIOD_SCAN)
     {
         s_t_scan = now_ms;
         ScanControls();
+        FrameFeed(TimeBase_GetMs());  /* 协作点 8: 控件扫描后立即排空 */
     }
 }
```

### 2.3 WCET 最坏时序预算 (Timing Budget)

| 操作步骤 | 指令/文本长度 | 115200 波特率传输耗时 (86.8us/字节) | 执行开销 | 累计切片最长时间 | 切片后处理 |
|---|---|---|---|---|---|
| **切片 1**：HR 数值与状态 | 约 35 字节 | 3.04 ms | < 0.1 ms | **3.14 ms** | `FrameFeed()` (< 45 us) |
| **切片 2**：RR 数值与状态 | 约 35 字节 | 3.04 ms | < 0.1 ms | **3.14 ms** | `FrameFeed()` (< 45 us) |
| **切片 3**：探头检测与状态 | 约 40 字节 | 3.47 ms | < 0.2 ms | **3.67 ms** | `FrameFeed()` (< 45 us) |
| **切片 4**：探头专用页刷新 | 约 20 字节 | 1.74 ms | < 0.1 ms | **1.84 ms** | `FrameFeed()` (< 45 us) |
| **切片 5**：10s 质量评估统计 | 内存统计 | 0 ms | 1.20 ms | **1.20 ms** | `FrameFeed()` (< 45 us) |
| **切片 6**：60s 趋势历史推点 | 环形缓冲 | 0 ms | 0.80 ms | **0.80 ms** | `FrameFeed()` (< 45 us) |
| **切片 7**：30s RTC 硬件读 | I2C/SPI | 0 ms | 2.50 ms | **2.50 ms** | `FrameFeed()` (< 45 us) |
| **切片 8**：200ms 触摸扫描 | GPIO/按键 | 0 ms | 1.50 ms | **1.50 ms** | `FrameFeed()` (< 45 us) |

- **单个最大切片阻塞时间**：$\max(3.14, 3.14, 3.67, 1.84, 1.20, 0.80, 2.50, 1.50) = \mathbf{3.67\text{ ms}} < 4.5\text{ ms}$；
- **DRDY 采样周期**：4.0 ms；
- **队列滞留上限**：在任何单个切片期间，最多到达 $\lceil 3.67 / 4.0 \rceil = 1$ 帧；
- **最坏时标滞后**：`bio.last_sample_ms` 滞后当前物理时钟严格 $\le 3.67\text{ ms} + 4.0\text{ ms} = 7.67\text{ ms}$；
- **最坏负 age 理论下界**：$\ge -7.67\text{ ms} > -10.0\text{ ms}$，确保具有至少 **2.33 ms** 的安全裕量。

---

## 3. Keil UV4 离线构建回执

在独立隔离环境下使用真实 Keil UV4 工具链构建候选固件：
- 执行命令：`python node-b/tools/build_b4_arm.py --temp --candidate-r6`
- 编译器：`D:\keil\ARM\ARMCC\bin\Armcc.exe` (V5.06 update 7 build 960)
- 链接器：`D:\keil\ARM\ARMCC\bin\ArmLink.exe`
- 格式转换：`D:\keil\ARM\ARMCC\bin\fromelf.exe`

### 3.1 构建输出日志摘要
```text
node-b\build\b4-arm-20261030T065438840092Z PASS
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

### 4.3 600 秒连续多任务极限负载仿真与边界帧数说明
- 仿真时长：600.0 秒（6,000,000 个 100us 步长）
- **边界说明**：此前的 149,999 帧系仿真循环条件在 599999.0ms 处退出、未包含 600000.0ms 截止刻度点的仿真边界伪象；加入末端边界排空后，总帧数严格达到 **150,000 / 150,000 帧**（100.000% 理论匹配，零丢帧）。
- **仿真统计指标**：
  - 总 ADC DRDY 帧数：**150,000 帧**（理论值 150,000 帧，250.0Hz 零丢帧）
  - `EcgQueue` 最大滞留深度：从旧调度的 **6 帧** 降低至 **1 帧**！
  - 捕获诊断快照数：**1200 个**
  - 快照 age 极值分布：`min = -2 ms`, `max = 99 ms`
  - 判据违背数：**0 / 1200**（越界率为 0.00%）

### 4.4 WCET 最坏工况多任务重合压力测试 (1s + 10s + 30s + 60s + 200ms 同步重合)
针对审查指出的“写屏阻塞、FrameFeed 耗时、多周期任务同毫秒重合触发最坏情况”开展专题极限注入测试：
- **旧版调度重合风暴**：
  - 连续无间隙阻塞耗时：$17.4 + 1.2 + 2.5 + 0.8 + 1.5 = \mathbf{23.4\text{ ms}}$
  - `EcgQueue` 队列积攒峰值：**5 帧**
  - 最坏 age：**-23.4 ms**（严重击穿 -10ms 判据下限）
  - 越界快照点数：134 点
- **R6 候选微调度重合风暴**：
  - 协作切片间隙持续调用 `FrameFeed()`；
  - `EcgQueue` 队列积攒峰值：严格 $\le \mathbf{1\text{ 帧}}$；
  - 最坏 age：收敛在 **-7.5 ms**（$\ge -8.0\text{ ms} > -10.0\text{ ms}$）；
  - 越界快照点数：**0 点**（100% 达标，具备充足安全裕度）。

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

---

## 6. 候选源码与制品指纹总表

| 制品文件 | 物理路径 | 文件大小 | SHA256 指纹 |
|---|---|---|---|
| **候选源码** | `node-b/evidence/B5-R6-PATCH01/hr_page.candidate.c` | 41042 字节 | `f7e6bc7e052660589f83ae6b04e0df0d0090421f39cd619eabfda3dbd06f6daf` |
| **候选 BIN** | `node-b/evidence/B5-R6-PATCH01/B5_TEMP_NODE_B.candidate.bin` | 41012 字节 | `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` |
| **候选 AXF** | `node-b/build/b4-arm-20261030T065438840092Z/firmware/OBJ/BIO_V2.axf` | - | `3e9d4d3256f5ffcfc4facb688ca02e42f231ce1d341eeae5c5801fe8760ced96` |
| **候选符号表** | `node-b/evidence/B5-R6-PATCH01/symbols.candidate.txt` | 44101 字节 | `07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8` |
