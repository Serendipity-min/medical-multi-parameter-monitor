# B2-0 当前板备份与恢复计划（未执行）

所有动作待精确现场卡批准；没有本轮全Flash备份。受限存储 `E:/medical-monitor-node-b-field-private`，ACL仅当前用户、Administrators及SYSTEM；真实UID、原码、完整Flash、可恢复镜像、原始调试日志均只放此处，不进Git。既有B1私有目录只核清单/租约，不搬移历史原件。

## 首次读取与备份

完整ECG卡要求当前备份SHA，而得到SHA又需要读板许可。不得循环假定已授权；R2已将首次窗口细化为 [AUTH-B-READBACK-001 R1](AUTH-B-READBACK-001-R1.md)，替代原AUTH-B-ECG-00泛化提案。先补齐现场信息与工具策略证据，绑定精确卡SHA。该窗口不含候选下载、源输出、导联接入或生理采集。批准后才能取得当次身份/备份，再补齐并提交AUTH-B-ECG-01。

1. 照片/板号与负责人口述绑定，确认完整芯片标识、供电和BOOT/SWD/CAN/模块当前状态。禁止工具自动连接、自动解锁或自动恢复。
2. 在批准的工具、SWD速度与halt政策下记录UID 12B（0x1FFF7A10）、DBGMCU_IDCODE（0xE0042000）、Flash容量字段（0x1FFF7A22起2B）、只读options及保护状态。R2细化options原件为[0x1FFFC000,0x1FFFC010)、FLASH_OPTCR为[0x40023C14,0x40023C18)，完整白名单及次数见新只读卡。器件型号/容量/RDP非预期立即STOP，不尝试解除保护或reset；不执行RDP/options写入。
3. 工程目标为STM32F407ZG/1MiB，**实际尚未证明**。只有容量确认为1024KiB，才把两次独立磁盘读取冻结为 `[0x08000000,0x08100000)`；非1MiB停止重审，不能截取伪装完整备份。
4. 两份读取分别独占创建flash-read-1/2，核对长度1048576、逐字节相同和SHA256相同，磁盘重开再核。记录工具EXE/DLL、读取起止、目标暂停状态、实际执行步骤和退出码。相等不代表必然可恢复；需再检查备份向量、当次身份和保护状态是否允许原范围恢复。
5. 备份与UID/options manifest放受限目录，manifest不含自身。另留同ACL独立恢复副本，核对副本SHA，备份成功回执才允许申请写板。没有双读及副本不烧录。历史备份不能充当今日原件。

## 条件性的候选写入范围

仅当实际为上述1MiB F407、当前完整备份已核验且新的ECG-01卡明确批准写入，才适用：

| 对象 | 精确范围（末端不含） |
|---|---|
| BIN载荷 | `[0x08000000,0x080062c4)`，25284B |
| 涉及擦除sector0 | `[0x08000000,0x08004000)`，16384B |
| 涉及擦除sector1 | `[0x08004000,0x08008000)`，16384B |
| 不得改变 | `[0x08008000,0x08100000)` |

扇区依据 [ST RM0090](https://www.st.com/resource/en/reference_manual/rm0090-stm32f4xx-reference-manual-stmicroelectronics.pdf)，不以BIN末地址代替擦除末地址。编程缓冲须保留sector1中BIN结束后至0x08008000的当次备份字节，不能擅自填FF。只有能证明仅操作sector0/1的精确下载工具/命令可进入卡；通用自动loadbin擦除范围未证实前保持 `WRITE_TOOL_NOT_APPROVED`。不生成可误执行的烧录脚本。

禁止 mass erase、chip erase、自动unlock、RDP/options/OTP写入。下载后应读回整个1MiB，与“当次备份覆盖候选有效字节”的预期镜像逐字节比较，所有非批准字节仍匹配。候选BIN只占Flash前缀，不能用BIN hash冒充全Flash hash。

## 恢复与停止

正常窗口结束，若写入卡已明确包括恢复动作，仅恢复原sector0/1的32768B，再完整读回1MiB与首次当次备份逐字节和SHA一致，并核options不变。若最终批准范围更大，必须重发卡，不能扩大到整片擦写。

UID/容量/options、双读、验证、供电或连接不符：STOP，保留全部失败文件和目标真实状态；不自动reset/go/擦除/重复下载。异常恢复只在原卡明确列明的失败分支范围内执行，否则重新申请。现场紧急断电/移线由负责人处理，软件不以STOP自动触发额外硬件动作。

当前状态：`BACKUP_NOT_RUN / RECOVERY_NOT_REQUIRED_NO_HARDWARE_TOUCHED`。本文件是恢复计划，不是“完整备份已完成”的回执。
