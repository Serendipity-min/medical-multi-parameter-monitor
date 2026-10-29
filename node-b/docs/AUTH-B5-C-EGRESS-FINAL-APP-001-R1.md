# C出口最终候选应用对象｜R1（待PI批准，默认禁用）

本卡只申请C应用安装，不包含三个START、配置写入或任何自动回退。必须先有B5-C-EGRESS-FINAL-CLOSEOUT的软件门PASS及本次现场事实，物理断电当前NOT_CONFIRMED，不能从历史代填。

- 当前实板C43036B BIN `28af9628f428403cc479293adf748e57b68c82a8444458a5ca8de43f311f36d4`；完整Flash `3369c5de14c2f81b37a2ca3a684ac80c65a2b50c63aba9e3ee892a074bb84fbd`。
- 唯一新候选46456B，BIN `1771ee61bde1fda9543ff7d056311d1602719d842552ce09dd7dece4aa19937e`；ELF `e618de6a266f3527fb2089b698a1c54d5f47c2b3be9444bc5a19f389bcbf3807`；符号 `ab7e41ae2881c7bc507661d4b191200db1c7ce2117e0642ed5541c304fc96090`。
- 安装预期完整Flash `b9e7518ec2af1b780534a97e769054630e19b6a4600800a6db2dea98b8f675ea`；options `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。
- 受限应用包manifest `fca23d45a29cb0725599a4675c9c1266e39d39f74976550f8ac1bacf6ec4f607`；绑定 `67ddb7a9f444fab70f40e8473bdaadae5ac0c9771fc4281bb8c54718c8a6092b`，原件只在EFS，不含云凭据公开内容。

## APP-INSTALL独立对象

scope `B5_C_EGRESS_APP012_UPDATE`，一个新私有授权文件/输出目录/.used；会话≤1、180秒硬限、Halt/正常器件Reset/Go各≤1。执行前冻结DLL及工具SHA、C私有UID引用、保护位、双完整1MiB和双16B options、运行Flash及DISARMED。只擦写sector0/1/2（0x08000000–0x0800BFFF），sector3和0x0800C000以后所有字节、options严格不写；写后双全片/options逐字节匹配新预期，正常Flash运行且DISARMED再关闭。既有B40928B不烧录、不复位或Go，不发ESP命令/B5START。

现场附件必须由负责人本次确认：B/C实际电源/USB/J-Link路径、全部熄灭10秒的冷态转C、B断电、C J5及USB_UART断开、ESP在板供电例外明确批准、CAN/独立GND/BOOT/源不变、无人/其他占用。当前均不能填写true；只在另批冷态操作后冻结。ROM/HALT、身份/Flash/options/保护漂移或原生错误即STOP_TARGET，不以重刷/强设PC继续。

## APP-RESTORE独立对象

scope `B5_C_EGRESS_APP012_RESTORE`，单独批准后才启用，不与安装或失败自动绑定。同样一次≤180秒，只用上述包的完整原sector0/1/2，恢复后全片必须精确回到 `3369c5de14c2f81b37a2ca3a684ac80c65a2b50c63aba9e3ee892a074bb84fbd`。新候选和旧C43036各自四标志地址按冻结符号绑定；保护/配置/options及尾部不变，双全片/options核验。此处回退到本轮C43036+gen5，**不是**自动恢复C24104/H3。恢复包离线重建已核验，物理恢复演练NOT_RUN。

原R-CFG/R-CLOUD、正式Broker/Backend、Security Gate及保护分支未包含；本卡发布不代表获准。
