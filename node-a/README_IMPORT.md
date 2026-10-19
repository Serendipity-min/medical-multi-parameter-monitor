# Node-A STM32F407ZGT6 source-only import (unmodified)

- 来源：用户上传的 `STM32F407_HOSPITAL.rar`，保留其 164 个文本源码/头文件/Keil 项目/许可文件。
- 本快照 **不是** CANopen A→C 真机已验收版本；原始业务源码字节未经改动。
- 排除 `OBJ/`、`Listings/`、J-Link 日志、Keil 用户偏好 `.uvoptx/.uvguix.*` 和已有 HEX/AXF/BIN。
- `USER/STM32F407_Template.uvprojx` 是原始工程；外部 UNO(血氧采集子控制器)固件和串口屏工程没有包含在本次 RAR 内。
- **已知 P0：** `canopen_app_process()` 将 `CO_RESET_NOT` 误当重置；`OD.c` 的 `0x1017` 为 0、`0x1014` 为 0x80；时钟锚点契约与 Gateway-C 不一致。具体见随附审查合同。
- **禁止**直接用此快照覆盖 P4/Gateway 或在未核验跳帽、实物收发器和编译输出时烧录。
