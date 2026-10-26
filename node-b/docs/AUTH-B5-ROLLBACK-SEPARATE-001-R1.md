# B5回滚｜三个独立批准对象，当前全部禁用

本文件是索引式列举，**不是一张三合一执行批准**。每项`enabled=false; owner_approved=false; executions=0`；批准必须明确下面唯一卡号及私有事务绑定。[共同绑定](B5-G0-SPLIT-AUTHORIZATIONS.md)适用。失败停，不自动进入下一项。

## AUTH-B5-R-APP-001 R1

仅C应用回滚一次，默认恢复**G2-RO新鲜读回的C24104B应用扇区原件**，不是H3。先获单独批准隔离ESP，防止被恢复固件自动入正式网络；确认当前B5应用/配置/身份/全片为预期。只擦写sector0/1/2 `[0x08000000,0x0800C000)`，恢复原49152B含尾部，180秒、halt/download/reset/go各≤1、无重试。若sector3仍为B5测试配置，恢复后全片预期为“原24104应用＋当前测试配置”，不是原1MiB，必须单列并禁止联网；不能把哈希不等解释为成功全片恢复。

完成全片/options/sector3/7/11/身份核验、真实Flash启动后停止。只在R-CFG另批恢复原sector3且全片等于新鲜before时，才可签完整恢复PASS。若要恢复H3，需另立目标、匹配H3 app/config、重新审查范围和ESP隔离；本卡无此许可。恢复正式联网始终另批。

## AUTH-B5-R-CFG-001 R1

仅原sector3回滚一次。前置为本次G2-RO两个独立16384B原件逐字节一致，原SHA与当前阶段绑定；ESP隔离。只擦sector3 `[0x0800C000,0x08010000)`一次，恢复整16384B、原记录committed最后写并核对原generation/CRC/身份。180秒、halt/reset/go各≤1、无重试，options及应用/sector7/11不动。新鲜双全片/options复核与预期一致才完成；不只比较336B。

可在R-APP之前或之后，但必须在批准附件明确顺序及该阶段完整expected-full SHA，不能把应用/配置中间组合冒称完整恢复。部分写失败停并保留原件，不自动重试。

## AUTH-B5-R-CLOUD-001 R1

仅撤销G1专用资源，一次事务，300秒上限。先确认C已STOP且测试ESP隔离；保存测试记录和前后SHA。只停独立B5服务、关闭测试会话/隧道、撤销b5-gateway/b5-observer新角色与相应ACL增量；不删除原始日志，不影响正式角色。恢复前比较G1后文件SHA，遇到第三方并发改动停止，不整体覆盖后来变更。

方案A关闭独立TLS反代进程，正式nginx不reload、无防火墙动作。方案B仅撤销该次准确绑定的测试SNI站点，语法通过后一次nginx reload；DNS/证书清理也只能撤销本次专属资源，保留原件。Broker沿已核验包装器至多转发一次HUP，先重核MainPID/脚本/SHA；无支持不擅自restart。不得停止正式Broker/Backend/AI、修改正式网络规则或开放8884。验证正式服务健康及未授权B5连接被拒绝，结束；凭据撤销证据与完整Flash恢复独立裁定，不把一项PASS顶替另一项。
