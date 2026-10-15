# MPM-ECG-SRC-001 独立源板工程（G1脱机交付）

仅非人体工程信号源。G0硬件准入BLOCKED，G2/G3未授权。这里不是B板固件。

## 固件结构

- 复用ST CMSIS启动与现有8MHz HSE时钟配置，168MHz HCLK、APB1/4、TIM6时钟84MHz。
- TIM6 PSC=83、ARR=999、MMS=更新TRGO，名义1kSPS；必须由G2实测真实节律。
- DMA1 Stream5/Channel7，将普通SRAM中的32位码缓冲送至DAC1 DHR12R1；DAC1=源板PA4。
- DAC2=源板PA5，保持2048码偏置；实际电压、共模和负载未知，不声明1.65V已核验。
- 60bpm表1000点、1秒1拍；90bpm表2000点、2秒3拍。1Hz正弦1000点。
- 上电OFF，DAC关闭。以后仅获授权源板窗口中可通过调试器写对齐32位 `g_source_requested_mode`：0 OFF、1 BIAS、2 SINE、3 ECG60、4 ECG90。
- 模式变更先停TRGO/DAC/DMA；UG装载分频在DAC触发启用之前。DHR预装第0点，DMA缓冲从第1点旋转，避免重复启动样本。
- DMA错误/欠载/异常锁存，停止动态输出后给两路相同偏置码；无自动恢复。DMA停用有界，必要时只复位源板DMA1，仍无法确认时DAC保持高阻并明确FAULT_HIGHZ，不谎称静态电压已成立。
- DMA完成统计为表/传输数，不是实测心拍数。计数uint32自然回绕。

源码中的限幅为1024～3328码，不夹掉超限输入来获得PASS。板载负载或电源变化不能由数字限幅保证电压；G2实测不可省略。

## 普通脱机命令

在B2工作区根目录执行：

```text
python -X utf8 ecg-source/tools/generate_tables.py
python -X utf8 ecg-source/tests/run_host.py
python -X utf8 ecg-source/tools/build_arm.py
python -X utf8 ecg-source/tests/test_ideal_transfer.py
```

工具不调用J-Link、串口或其它硬件。ARM工具为本地Keil ARMCC5.06u7；没有安装工具、改变系统环境或运行安全扫描。构建只用临时SUBST自有映射，应保留原始build记录。

Host测试使用真实驱动C＋寄存器模型，不模拟物理DMA仲裁/DAC电压/中断实时性。理想传递模型采用候选公式，电阻和参考值未测未批，不能升级成硬件通过证据。

## 原件与可公开材料

`platform/`保留ST原文件版权/许可头及准确SHA，来源见公开platform-provenance.json。本工程只基于CMSIS寄存器访问，不迁移HAL/RTOS。编译组选项关闭自动更新Flash；本轮没有运行IDE调试或烧录。

`build/`为每次独立运行的本地日志、失败输入、ELF/BIN/map，不进入拟推送范围。公开摘要在`artifacts/ecg-source/`。完整第三方PDF、图片和板卡实物照片不在本包，分享权限另核。
