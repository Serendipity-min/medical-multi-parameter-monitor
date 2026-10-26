# AUTH-B5-G2B-SECTOR3-001 R1｜独立测试配置提交一次，禁用

`enabled=false; owner_approved=false; executions=0`。[共同绑定](B5-G0-SPLIT-AUTHORIZATIONS.md)适用。现有应用安装工具禁止sector3；**本卡尚缺专用配置写入器的离线验收与SHA绑定，当前不可执行**，不得扩大旧安装scope。

前置：G1独立测试身份已批准并创建；G2-A安装验证通过且C保持DISARMED；重新双读整片/options/完整sector3与当前阶段一致；ESP在配置期间隔离。地址/SSID/密码/CA关联只从仓库外受限配置读取，不把旧H3身份自动带入B5。

纯离线生成H3ConfigRecord：magic`0x32433348`、version1、header24、payload312、总336B；非零新generation，相对旧代次严格推进且无溢出；CRC32按`persistent_config.h`覆盖字节0–15和24–335，跳过CRC与committed。GatewayConfig字段长度、NUL终止、AT字符约束、minimum_epoch、TLS host和独立身份均校验，username必须`b5-gateway`、client_id必须`b5-c-isolated`。提交标记`0x54494D43`最后写。旧记录CRC有效不表示B5身份有效。

**提交预算仅一事务，180秒，erase sector3≤1、提交标记编程≤1、halt/reset/go各≤1、无重试。** 原16KiB sector3双份保留；新336B之外的16048B完全取原件。擦除范围只`[0x0800C000,0x08010000)`；先写不含committed的新记录及保留尾部，核对所有未提交字节，再单独写20–23字节的committed，之后双读完整sector3，核验记录/CRC/身份、全片及options。不能只读336B或只验CRC宣告成功。

离线负例至少覆盖：CRC错、未提交、旧身份、字段越界/AT非法字符、代次不推进、sector3尾部漂移、其他扇区/options变化、部分写入、禁用授权。未通过不下板。原始秘密不可写日志；中断留下未提交记录应拒绝联网，不自动再写。

写后生成新的完整expected-full及恢复manifest，原G2-A预期全片SHA因sector3改变即失效，不得忽略差异。应用sector0/1/2、sector7/11、options应不变。正常启动仍DISARMED；配置写入批准不授权恢复ESP供电、连接网络或发B5START。配置恢复仅R-CFG单独批准。
