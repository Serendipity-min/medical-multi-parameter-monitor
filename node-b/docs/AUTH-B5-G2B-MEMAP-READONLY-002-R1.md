# MEM-AP修正版第二窗口｜只读，待批准

`enabled=false; owner_approved=false; executions=0`。第一次窗口已因SDK读错误停止；本卡不自动重试、不重复G2-A，不授权写配置。

## 固定前提与绑定

- C42552B唯一BIN SHA `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；当前预期整片 `3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c`；options `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`；原sector3 SHA `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313`。UID只与受限原件比较。
- G2-A真实安装已PASS；第一次桥失败原件和源码不覆盖。错误后的CPU实际状态尚未重读；不能预填为正常Flash。
- 修正仅 `b5_g2_site.py` 只读分支，冻结依赖/DLL/源码SHA见 `SDK-context-audit-bindings.json` 和 `MEMAP-next-readonly-disabled-plan.json`。私有授权必须新的唯一目录/nonce、有效期、对应G2-A实际回执及准确现场附件，旧`.used`不可重用。
- 沿用负责人已经批准的ESP在板供电豁免，如实记录未隔离、自主联网未知；不重新拔模块、改供电或发送AT。此卡不延伸该豁免到sector3写入或云窗。J-Link在C、C原J5、USB断开、B/源/CAN/地等现状均不操作；现场有变化先补附件，不索要重复型号。

## 一次180秒窗口

1. 独立监督器消费一次许可，单会话、重试0；错误或预算不足即停，超时不另连清理。
2. 仅SDK只读核对C UID/保护、VTOR/DWT采样/Fault、整片/options及B5状态4B全零。ROM/HALT/新复位、身份或字节漂移立即停止，不按RESET、不Go或重刷。运行态真实PC/MSP仍不强取。
3. SDK必须仍Connected。**Configure禁止调用**，不输出新的接口切换序列、不为通过门禁重连接。先冻结SDK CPUID/Flash前64B/CR/SR基准，再读取原始AP IDR、CPUID、向量及控制状态作比较。
4. 原始AP操作只允许DP SELECT=0/F0及AP0 CSW/TAR传输设置，正常完成才恢复可读CSW/TAR、SELECT规范化0。任一原生AP/DP错误立即锁死后续AP/DP调用，不执行追加的finally原生恢复请求、不重连；传输状态保留UNKNOWN。DRW写、KEYR/CR/SR/ACR目标写、Flash/option写、halt/reset/go及强设寄存器均0；只读地址白名单不变。
5. 完成后SDK回读、全片/options、UID/保护、DISARMED及运行状态全部相符才判只读桥PASS。成功后才使用已审正常退出续跑；失败保持禁止续跑，不自动Go/恢复。SDK内部行为不能以显式调用0冒称绝无状态影响；新增回调按在途API和单调时间留证。

缺一项即失败；尤其负SDK返回和正不足长度分别记录，原生错误不重试。只读PASS不等于sector3编程、独立冷启动、ROM根因、CAN/生理或上云通过。完成后停止，G2-B配置写入、G1服务恢复、G3和实际回滚仍未授权。
