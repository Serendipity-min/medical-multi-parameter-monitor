# P5-00 / P5-01 / P5-02 基线冻结

日期：2026-10-08（Asia/Shanghai）。正式合同 v1.0 为唯一 P5 执行合同。
用户裁定：允许保留原 P4 脏工作区，另建干净 worktree；允许在 P5 最小调整 CI，
切换完整性检查并跳过未授权 ASan/UBSan。原工作区的 10 份修改文档和未跟踪资料未带入。

- P4：`8dee339491cfd4edc468bb9451511d421f26db5e`，远端复核一致。
- P5：`P5-coremqtt-baremetal`，从同一 P4 创建，仅复制正式合同。
- P4 独立对照 worktree：`E:/medical-monitor-docs/p4-baseline-refresh`，detached HEAD；tracked 工作树干净。
- 本轮重建命令：`python gateway/mqtt/build.py`，退出 0；无烧录。
- 工具链：Arm GNU 14.2.Rel1 / GCC 14.2.1，Cortex-M4 hard-float、HSI16MHz、`-Os`，ST 标准库 V1.4.0。
- P4 size：text=30084，data=88，size 汇总 bss=120072。
- 实际 `.bss`=87300；`._user_heap_stack`=32772（24KiB heap、8KiB stack 和对齐）；RAM 总计=120160/131072。
- ELF SHA256：`1b3d646fdf72603cb3455be4a9f34b04b9b5c9ea35902740a856a59ea490a5b7`。
- BIN SHA256：`5fd386b8bfe0bcf54d4f53ffb1ec6483d086a1c3287b4fe6c37a3ddeacd90547`。
- 本机原始构建日志：`E:/medical-monitor-p5/evidence-20261008/P4/build.log`；固件在对照 worktree 的被忽略 build 目录。

P4 行为差异：MQTTPublish 等待并解析 PUBACK，但没有比较返回 packet ID；
P5 按正式合同补足匹配校验，不把 P4 此处写成已证明正确。
现行 v1.1 手册的 verifier 子目录路径有误，实际为 `gateway/third_party/verify_paho_integrity.py`。
历史手册保留，以当前代码及本合同确定迁移路径。

coreMQTT v2.3.1 的 tag 对象及 peeled commit 与合同一致；9 个文件经过官方 Git Blob
SHA-1 和本机 SHA-256 双重来源核对。raw 域名 DNS 不可用，改用官方 GitHub Git Blob API，
没有使用镜像或浮动分支。`--vendor-only` 离线核验 PASS。

CPU、CAN 最大协作延迟、stack high-water、真实 TLS 重连耗时尚未测量；
硬件窗口与安全门未授权，均不得由基线历史结果代填。
