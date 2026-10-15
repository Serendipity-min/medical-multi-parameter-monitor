# Node-A 资料导入记录 v0.1

日期：2026-10-15  
分支：`dev/node-a-v07`  
来源：`F:\多参数心电监护仪系统-样机开发\代码资料\STM32F407_HOSPITAL`、`NodeA项目书.md`

## 本次里程碑

将 STM32F407 工程源文件导入 `node_a/STM32F407_HOSPITAL/`，将项目书作为来源快照导入 `doc/A/NodeA项目书.md`。工程相对层级保持为 `CORE/`、`FWLIB/`、`HARDWARE/`、`USER/` 同级；Keil 工程定义 `USER/STM32F407_Template.uvprojx` 保留。

## 导入边界

- 保留源码、头文件、启动文件、当前 CANopen 源码、当前 OD 文件、协议资料和 Keil `.uvprojx`。
- 排除 `OBJ/`、`USER/Listings/`、`USER/.vscode/`、构建输出、构建日志、J-Link 本机配置/日志、Keil 用户布局文件和 `OD.*.bak` 历史备份。
- 没有运行 `keil_keil.bat`、`gen_od.py`、`debug_od.py`、编译、烧录或安全扫描。
- 没有提交凭据或本机私有烧录配置；`.uvprojx` 中仅保留工程元数据，不执行其烧录设置。

## 只读核对

- 本地源目录共枚举 386 个文件；按上述边界导入可跟踪源文件，生成物和本机配置由仓库忽略规则排除。
- Keil XML 的工程文件和包含路径均为工程内相对引用；未执行编译。
- Node-ID、PDO COB-ID、OD 索引和单位没有因本次导入被修改。项目书中的实现陈述不视为硬件实测证据。
- 只读对照发现来源 `OD.c` 与 P 冻结基线存在待评审项：TPDO1 事件周期、validity 保留位、epoch/anchor tick 配对、Producer Heartbeat 与 EMCY inhibit 默认值，以及 P 字典预留的 `2111` 记录未在来源 OD 中出现。未自行修改。

## 待 P 决策/待实测

- AFE4490 SPI/DRDY/Red/IR 真实链路、HKB-08 完整测量链、双屏和 CAN 收发器均未在本次导入中实测。
- 需按 P 阶段数据字典继续核对来源固件的 validity、synthetic、heartbeat、anchor tick 和 PDO 周期；发现差异时提交接口变更申请，不自行改字典或协议。
- 项目书 §4 描述 UNO 中转和 §1 的 PPG 125Hz 需与合同及 P 冻结的 50Hz PDO 基线核对，当前不作验收结论。
- 项目书不同章节对 `2111` 预留和 TPDO 数量的叙述也需 P 统一口径；当前不据此改变 OD/PDO。

本记录只说明资料边界和只读核对结果，不替代阶段验收报告。
