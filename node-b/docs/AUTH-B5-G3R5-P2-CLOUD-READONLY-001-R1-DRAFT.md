# AUTH-B5-G3R5-P2-CLOUD-READONLY-001 R1｜测试服务新鲜状态草案

DRAFT_DISABLED / NOT_RUN。P0/P1未完成，不自动执行或恢复服务。仅准备一次既有SSH别名连接，远端45秒/本地55秒硬限、重试0；精确unit、配置路径及旧引用取受限G1部署包，不在源码/卡中写真实服务器地址或凭据。

只读systemctl show两个独立测试Backend/TLS实例及已记录正式unit的ActiveState/SubState/Result/MainPID/RuntimeMax/Restart/ActiveEnter/Exit，ss读取loopback18775/8884监听，比较批准配置/ACL的来源摘要，报告测试账户残留。不得输出ACL/password_file内容、令牌、私钥或UID。留意原625秒驻留余量门禁；active/PID不等于TLS/Backend业务可用。

复用b5_g1_lifecycle_readonly.py中的只读函数并冻结新scope/监督；旧脚本直接运行main会SSH查询，不能当“本地准备命令”误运行。本卡尚未形成有效私有执行许可，不调用SSH，不启服务、HUP、改ACL、Broker、Backend、Hub、Nginx或正式环境，不发送MQTT/WSS测试。真实TLS/健康/订阅核验、G1-RESUME、PC防护修复和G3都另列批准。

历史预期2026-10-27 17:15:45六小时到期已过，当前真实状态UNKNOWN；测试账号/ACL不会自动撤销，不能声称已经清理。若到期，先形成只有两个测试unit各start≤1的新恢复卡，不重跑含ACL/HUP的G1 apply，不延长6小时策略。
