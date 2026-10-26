# AUTH-B5-R-CLOUD-EMERGENCY-001 R1｜G1-A专属应急回退，禁用

`enabled=false; owner_approved=false; executions=0`。仅为G1执行前的恢复准备；本轮负责人明确未授权实际R-CLOUD恢复或撤销，失败后仅停止并报告状态，不自动执行。

仅对应`g1a-1ceb665360`与[准确G1-A卡](AUTH-B5-G1A-EXECUTION-001-R1.md)。原件位于本次独占本机EFS完整备份及服务器`/opt/medical-monitor-b5/g1a-1ceb665360/before-private`，metadata绑定源路径/完整SHA/mode/uid/gid。真实路径与敏感原件不打印，原始记录永不删除。

未来单独批准的最小回退事务：300秒硬限、一次，先确认没有B5实板业务/发布会话，保存G1全记录；只停两个专属unit并确认退出，正式Broker/Backend/nginx/AI/P6不停止或重启。读回当前ACL/password_file应恰为此次G1预期追加后的SHA；发现第三方并发更新即停，不整文件覆盖后来变更。

当前文件与已批准阶段完全相同时，才可恢复各自备份原字节、mode/uid/gid，逐字节校验；正式Broker仍通过已冻结MainPID/包装器的一次HUP重读，禁止restart或改变HUP目标。检查正式服务PID/健康及原身份权限保持，测试凭据拒绝；完整原件存在和回退包可重算**不等于已实测恢复**。

专属unit、服务账号和配置是否撤销必须在该次批准附件明确。可只禁用/锁定本次专属账号并保留文件，不删除日志/备份/历史失败；不要`userdel -r`、递归删除目录或改任何正式账户。方案A无正式nginx或防火墙改动，因此也无相应恢复动作。若G1在写ACL前失败，则不得盲目恢复尚未变化的文件或发送HUP。

审批附件须包含当前阶段、拟恢复文件精确SHA及原件SHA、工具/DLL无关说明、一次性标记、服务真实PID、明确停止条件。此卡不恢复C应用/sector3，不接实板，不恢复正式GW联网，不运行Security Gate。
