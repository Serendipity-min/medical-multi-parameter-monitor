# AUTH-B5-G2B-SCHEME-BOUND-001 R1｜sector3方案绑定，尚不可写

`enabled=false; owner_approved=false; executions=0`。本轮只准备方案和纯离线规划器，**未用真实口令生成336B配置记录，更未写入**。物理配置写入器仍`NOT_IMPLEMENTED_NOT_AUTHORIZED`，不能把本卡视为可立即执行的烧录许可。

## 已绑定输入

- 原件：G2-RO第二窗口真实独立双读，C全片`b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98`；完整sector3的16384B SHA `1698c8783b4fbdd1bc7fc5a8641babc7b499b58a65be54e7b36c65c6c5b88313`。新鲜来源绑定`f614271c83b8b6f11992531537ea49ab6434f6f2a7c2481f1cced7ae55f1cad1`。
- 应用前提：G2-A42552B独立通过，安装后全片`3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c`。配置改变后该SHA必须重算，不能继续称写后全片预期。
- 云身份：G1-A事务`g1a-1ceb665360`已受控验证；Gateway `GW-B5-001`、username `b5-gateway`、client `b5-c-isolated`、TLS8883；主机/口令只引用G1受限EFS真实配置与`test-credentials-private.json`。输入文件SHA/来源见[方案输入回执](../evidence/B5-G1-G2RO/next-sector3-scheme.json)，原值不填Git。
- 纯离线规划器`node-b/tools/b5_sector3_plan.py` SHA `ff9118d3b6303bc8bd15b64cd5203339c8abff778d33e4d19cfe69e2d0962ef1`，14项合成检查通过；该程序没有DLL/实板写入入口。

## 下一轮必须先完成的离线准出

PI批准配置编制范围后，从新鲜原记录仅在内存复用适用的WiFi字段，全量重建312B payload和24B头，不直接改旧H3几个字符。代次从3推进到4；最低纪元不低于新鲜原记录并在编制时冻结，不能把此下界冒称实时SNTP。字段长度/NUL/AT字符约束、唯一B5身份、CA/域名/SNI关联及CRC必须通过。

记录总336B，magic/version/header/payload与H3协议一致；CRC跳字节16–23；committed=`0x54494D43`最后写。完整sector3其余16048B逐字节取原件。生成未提交/已提交sector、两阶段完整预期、原sector恢复包、R-APP先或R-CFG先两种中间全片及最终恢复SHA。真实配置输出只在EFS，**当前这些输出SHA为null，因为尚未获编制/写入许可**。

另须实现并离线审查专用sector3写入器/监督器、固定其SHA与一次性权限拒绝负例；不能放宽G2-A工具的sector0/1/2范围。准备完成后再提交包含精确新记录/整sector/全片SHA和工具绑定的配置写入授权附件。缺任一项不得启用。

## 待另批的物理写入范围

仅sector3 `[0x0800C000,0x08010000)`，先双备整16384B，并核实当次OPTCR的sector3写保护位允许编程、RDP及Flash状态合格；受保护即停，不解除保护。erase≤1、commit标记≤1、halt/reset/go各≤1、180秒硬限、重试0；ESP隔离、B不动。先写未提交记录与保留尾部，核对后最后写20–23的4B提交标记；再双读整sector及全片/options。应用、sector7/11及options不得变。

失败留下未提交/部分写状态并停止，不自动再写、不运行B5START、不自动回滚。R-CFG与R-APP恢复分开批准，默认回到本次新鲜C24104＋原sector3；H3恢复/正式联网均不包含。ESP AT/证书存储/SNI实物适用性仍是G3独立门禁，不能由配置CRC通过代替。
