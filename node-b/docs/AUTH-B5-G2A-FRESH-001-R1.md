# AUTH-B5-G2A-FRESH-001 R1｜新鲜原件绑定的应用安装卡，禁用

`enabled=false; owner_approved=false; phase=install; executions=0`。本轮G1/HW0/G2-RO及负责人手动复位后重读的授权，均不包含本卡。不得下载、改sector3、发B5START或顺带演练恢复/重装。

## 已绑定的字节与来源

| 对象 | 冻结值 |
|---|---|
| C新鲜独立双1MiB | `b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98` |
| C新鲜独立双16B options | `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| 唯一C候选 | 42552B，BIN `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；源码实现`c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5` |
| 三扇区安装/恢复manifest | `3782fc9caa0f921cc51001191df0ac90e2633710e89f56bae017d2e3d35e73fc` |
| 新鲜来源绑定 | `f614271c83b8b6f11992531537ea49ab6434f6f2a7c2481f1cced7ae55f1cad1`，关联本次第二个独立只读窗口的实际两次SDK返回/原件/监督器 |
| 仅安装应用后的完整预期 | `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c` |
| 默认完整恢复目标 | 本次新鲜C24104＋原sector3，完整SHA仍为`b460d917…`；不是默认H3 |

manifest与G0历史布局计算相同，是因为原件字节未变；新鲜证明来自单独来源绑定和不同路径的两次SDK读回，不来自manifest自身。私有包位置由忽略指针`node-b/build/b5-fresh-install-restore-pointer.json`引用，只能在受限EFS读取。

## 启用前条件与一次事务

1. PI明确批准本卡、有效期和唯一输出。安装工具scope必须为`B5_C_SECTOR012_MOCK_INSTALL_OR_RESTORE_NO_CONFIG_WRITE`，board=C、phase=install、nonhuman_mock=true，工具/依赖/DLL SHA与新鲜包绑定。旧24104B仅sector0/1卡不可用。安装前重新只读核当前运行/UID/完整Flash/options匹配，ROM/HALT/漂移立即停，不先恢复。
2. 当前实际为B断电、C由J5供电、C USB断开、J-Link在C、ESP装板且隔离未知。现有安装器要求`ESP_isolated=true`，**不能将未知填true**。下一轮须先批准明确的冷态ESP隔离方式与供电/调试器恢复动作，现场完成后才可启用；本卡不自动授权热拔模块、改EN或BOOT。B保持不烧录、不改算法/寄存器；A/INMP441/TTS仍断开。
3. 仅擦写sector0/1/2，`[0x08000000,0x0800C000)`，总49152B。新BIN之后6600B取新鲜before原件；sector3/7/11、options与其余所有字节保持。无解保护、mass erase或配置写入。
4. 单连接180秒，halt/download/reset/go各≤1，重试0。读回完整1MiB及options/身份和保护区，与完整预期逐字节一致才正常器件reset一次；按冻结工具读取真实PC/MSP及VTOR/Fault，匹配新Flash向量才Go≤1。不强设寄存器或绕过BOOT状态。
5. 安装后保持`B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE`；不发B5START、不启用ESP联网。原sector3 CRC仍有效但B5身份不匹配是预期，不能改宏绕过。按批准的非侵入观察方式取证，不临时接串口触发复位。

安装不等于恢复演练；应用恢复、sector3恢复及再次安装各自另批，分别保存原件/失败和真实返回。G2-RO运行态未读真实PC/MSP，不能用其DWT采样替代本卡复位后入口寄存器验收。ROM根因继续UNRESOLVED，遇异常即停、不自动复位或重刷掩盖。
