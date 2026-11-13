# AUTH-B5-G2A-APPLICATION-001 R1｜42552B三扇区安装一次，禁用

`enabled=false; owner_approved=false; phase=install; executions=0`。[共同绑定](B5-G0-SPLIT-AUTHORIZATIONS.md)适用。本卡不授权sector3、任何云修改/B5START、恢复或重装。

前置：G2-RO新鲜双读通过、与当前C24104身份/镜像一致，B5候选42552B/SHA精确匹配。应用工具scope为`B5_C_SECTOR012_MOCK_INSTALL_OR_RESTORE_NO_CONFIG_WRITE`，在私有授权记录中进一步固定`phase=install`、`board=C`、`nonhuman_mock=true`。安装前再次只读核对目标完整Flash/options/UID为同一包的before状态。绑定真实工具/DLL/manifest/现场SHA及单次使用标记，禁止使用历史C24104B安装卡。

ESP保持经批准的电气隔离；若需要改变B/C供电或调试器位置，必须在本次批准附件逐项列出，不隐含授权。没有明确断电/停机方式不能开始。

擦写仅sector0、1、2：每扇区16384B，总范围`[0x08000000,0x0800C000)`49152B。候选42552B后剩余6600B取本次before原字节；不能填FF、擦sector3或整片擦除。options、sector3/7/11及所有其他字节保持原件。

一次连接，180秒硬限，halt/download/reset/go各≤1，失败不重试。下载后读回完整1MiB、16Boptions、身份/保护，与包expected-full逐字节相同；先核对新Flash向量，再允许一次正常器件reset。按冻结策略读取复位后的真实PC/MSP，与新向量匹配且VTOR/Fault合格才允许Go≤1；无法取得匹配证据则停，不强设PC/MSP/VTOR。保持运行退出并确认B5 DISARMED、MOCK、B_ONLY；此时旧sector3身份不匹配必须拒绝联网，不能绕过CRC/身份。

候选无运行Flash写入口。完整readback、向量、保护区或运行状态任一异常立即停，无自动回滚。**安装通过不等于恢复演练通过**。R-APP、R-CFG、未来重装各须新的单次批准。
