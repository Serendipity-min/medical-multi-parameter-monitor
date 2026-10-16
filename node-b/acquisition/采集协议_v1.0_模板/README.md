# 采集数据协议 v1.0 填写模板

对应设计：`../通用多样本采集工具与数据协议设计_v1.0_20261013.md`。

这些文件是设计模板，不是已实现的采集工具、不包含真实采集结果，也不是硬件操作授权。

## 使用步骤

1. 为数据集复制 `dataset_index.template.csv` 为 `dataset_index.csv`，保持表头，不写虚构样本行。
2. 每轮新建唯一 `runs/run_id/`，复制 session/channels 模板并去掉 `.template`。采集条件未满足时停止在准备状态，不靠填表代替核验。
3. 填写 dataset/sample/condition/run 标识、匿名操作者、实际输入、设备、固件、工具、时基与参考。`null` 是未知；不能默填 0 或 PASS。sensor_model 和通道映射是当前 ADS1292R 工程的起始示例，接入其它传感器须改成真实定义。
4. 保存单独核对的 adapter_profile，绑定实际 BIN、ELF 与符号。不能从昨日地址表自动迁移到新固件。
5. 原件及采集回执在唯一目录封存。分析新建 analysis_id；协议与分析版本分开记录。采集失败仍在数据集索引保留一行并记录原因。
6. 索引状态使用明确枚举：身份 `VERIFIED/UNKNOWN/MISMATCH`；完整性 `PASS/LIMITED/INCOMPLETE/FAIL/NOT_EVALUATED`；参考 `SETPOINT/INDEPENDENT/NONE/UNKNOWN`；用途 `INCLUDE_FOR_STATED_PURPOSE/OBSERVATIONAL_ONLY/EXCLUDE_FOR_STATED_PURPOSE`。PASS 必须同时说明适配器的实际证据范围。

模板的 record_status 在填完准备材料后可记 `PREPARED`；实际执行情况由 acquisition_receipt 单独记录，不能把准备状态改成采集成功掩盖失败。JSON 模板均为标准 JSON，无注释；填写说明放本文。

## 固定 CSV 表头

以下表头是拟定数据接口，不能据此假定现有程序已经支持导出：

样本：

```csv
run_id,boot_id,segment_id,source_seq,device_tick_raw,device_time_us,irq_cycles_raw,channel_id,raw_code,adc_status_raw,source_flags_raw,integrity,provenance,observation_count,source_ref
```

实机状态：

```csv
run_id,boot_id,segment_id,observation_id,module,field,value,value_type,unit,valid,sample_seq,sample_tick_raw,read_start_host_ns,read_end_host_ns,coherence,source_ref
```

参考：

```csv
run_id,reference_id,reference_time_us,device_time_us,sync_uncertainty_us,channel_id,metric,value,unit,reference_kind,source_ref
```

观察与样本映射：

```csv
run_id,boot_id,segment_id,source_seq,observation_id,source_path,byte_offset,byte_length,record_sha256,validation_status,selection_status,reason
```

没有可靠归属的 boot/segment/seq 留空并解释，不得把它们合并进稳定样本。observation_id 每次实际读取分配，重复解析不增加观察次数。source_path 是采集包内相对路径；外部本地原件通过清单明确关联。

## 状态与哈希规则

每个质量字段必须包含 status、证据范围与原因，不能只有布尔 PASS。禁止自动填充参考值、补点获得完整、清零设备计数或移除失败轮次。manifest 不包含自身；大整数的 JSON 表达规则见设计第 4 节。

默认新采集准入仍需：完成现有工具剩余项、通过离线负向用例、核对适配器，并在明确批准的台架窗口验证。没有真值时可以分析表征，不能把“格式统一”写成“心率呼吸准确”。
