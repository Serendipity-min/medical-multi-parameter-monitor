# NODE_A_GIT_IMPORT_HANDOFF

A0 已实际完成并推送，不是预演命令。分支 A 的第一个新增提交：`2c4885404723a0a7c303c8c0184940e9ed188108`；父提交为固定 P4 `67f5f57bd82c6e326e9e78ec9540481c80105e5f`。导入 worktree 为 `E:/medical-monitor-node-a`，未覆盖用户原脏工作区，未修改 P4/main。

|输入|SHA-256|
|---|---|
|STM32F407_HOSPITAL.rar|`3d52a58f2a7f2cda9ae22f499def3aaa5fd8046be513eb060d012ee32bf89c35`|
|MPM_NodeA_CANopen_审查包.zip|`4c0bf4b8eb24a5650fbf909cbc1f98561bc9f3e226ebd3812e11cdf0d443be09`|

原 RAR 选择性解压的 164 个源码/头文件/Keil 项目/许可文件，与 ZIP 清单、工作区、Git 暂存区逐一核对 SHA-256 全部一致，合计 4,392,159 bytes。首提交共 169 文件：164 原件 + .gitignore、.gitattributes、README_IMPORT、源清单及 IMPORT_IDENTITY。`.gitattributes -text` 保证原件编码/换行不被 Git 转换；第三方原许可头和 LICENSE.CANopenNode 保留。原件源清单位于 node-a/NODE_A_SOURCE_MANIFEST.json，首提交可精确恢复。

没有导入 OBJ、Listings、bin/hex/axf/map、Keil 用户选项、调试日志或设备 UID/凭据。原 RAR 留在用户资料区，未上传整个归档。原双屏工程与依赖实际可用，原 uvprojx 用既有 ARMCC 5.06 update7 build960 完整 rebuild，原始退出码 0，0 Error/0 Warning；产物只在忽略目录，不烧录。

原件功能并非 CANopen PASS：原 Host 编译成功后，`init_count==1` 断言失败，原始进程退出码 3，复现 CO_RESET_NOT 被当作复位。该失败及 Keil 基础构建均见 evidence/baseline-*。Host 初次漏列原工程 LSS 源文件造成的链接失败退出码 1 也保留，并未误报成业务问题或 ARM 失败。

注意：本报告描述的是**首提交**。活动源码随后经 A1 修复，不再全部等于原件；后续身份及回归见 A_CANOPEN_RELIABILITY_HANDOFF.md。没有硬件/上电/生产 Broker/正式安全门/PR/合并行为。
