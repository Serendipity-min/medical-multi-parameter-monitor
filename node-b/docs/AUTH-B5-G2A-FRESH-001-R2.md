# AUTH-B5-G2A-FRESH-001 R2｜仅应用安装，待批准

`enabled=false; owner_approved=false; executions=0`。本卡替代R1作为下一次申请；R1与历史回执保留。本轮禁止实板操作，不能由软件准备通过推导安装已授权。

## 固定对象

- 唯一C BIN：42552B，SHA256 `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`，实现源码 `c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`。不得改用24104B旧安装范围。
- 应用安装包manifest：`3782fc9caa0f921cc51001191df0ac90e2633710e89f56bae017d2e3d35e73fc`；来源双读绑定 `f614271c83b8b6f11992531537ea49ab6434f6f2a7c2481f1cced7ae55f1cad1`。位置由忽略指针 `node-b/build/b5-fresh-install-restore-pointer.json` 引用。
- before全片：`b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`；after：`3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c`；options：`52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。

## 启用条件与一次范围

1. 负责人另批本卡、一次性私有授权、有效期、唯一EFS输出和现场附件。当前上电/探针状态未核实，10月26日检查点不能当作今天运行证明。任何冷态ESP隔离、供电、JTAG/USB转接动作须单独明确批准；不得热插或把ESP隔离未知填为true。
2. 启用前核对已冻结应用安装器/监督器及DLL SHA（见本轮 `bindings.json`）、C私有UID/F407/1MiB/保护、实际Flash运行与完整before/options。ROM、HALT、意外复位、字节漂移即停止；不先复位“修好”再安装。B、源、电极不动，A段断开。
3. 仅sector0/1/2 `[0x08000000,0x0800C000)`，49152B；新BIN之后6600B保留。sector3/7/11、其余Flash及options不写，不解除保护、不整片擦除。scope仍为 `B5_C_SECTOR012_MOCK_INSTALL_OR_RESTORE_NO_CONFIG_WRITE`，phase=install。
4. 单连接180秒硬限，halt/download/reset/go各至多1、重试0。全片/options/身份逐字节符合after后，才正常器件reset≤1；真实PC/MSP匹配Flash启动向量、Fault合格才Go≤1。不得强设PC/MSP/VTOR。失败保持现场，不自动回滚或再次下载。
5. 完成后保持B5 DISARMED；旧sector3 CRC有效但旧身份应被B5拒绝。不联网、不发AT/B5START、不写新配置。安装不等于恢复演练、独立冷启动或云验证。

配置写入仅由[独立G2-B卡](AUTH-B5-G2B-SECTOR3-001-R2.md)批准；恢复仅由独立R-CFG/R-APP卡批准。
