# AC-0 INPUT/NAT只读差异复核

本轮只读SSH查询退出0，未打开COM15，未修改规则、服务、配置或安全组。

历史filter全表SHA依次为`3c5a486467a9ea2ed4c7afeb3c8b45f1e9747cec67201f9b340a71d476f794b5`和`1fe2081c0f0cc04d56c8064144a11463bb03568c8c2b28524f755bacfeddbfd0`。本轮当前filter表SHA为`05f3c5952feb6301c951704f9d93e7788531c28696a5d407c8bea4e9a629a983`（395行），NAT为`96ba2354a7ee95379dbc8c4bc83f5c5d13ccc95d5367d69e3af1e6dec9ed3157`。原回执中的INPUT散列实际来自`iptables -S`整个filter表，不能误称仅INPUT链正文散列。

新快照保留filter/NAT的链/规则顺序、每条散列、端口和地址范围类别，地址正文不落公开记录。没有旧窗口前逐条原文，不能推出具体增删规则或归因于某进程。UFW active、Fail2ban inactive；所查历史时间窗口未找到Ban/Unban事件，不能据此证明无其他动态修改。未扩展扫描其他项目或还原整表。

当前自有MPH3R2C/MPH3R2N引用均0，8884和18775无监听；正式8883仍有监听。正式服务PID、旧配置/Web散列与历史正式计划一致。静态Nginx片段不含AI正式前缀；完整有效HTTPS访问/受众未独立验证，不能把片段缺少443监听误判为全站未启TLS。

云安全组未通过API读取，之前负责人反馈TCP8884广域规则保留仍只是历史反馈。本机CLI/配置可用性见风险登记；未取得可验证控制平面快照。**正式发布保持BLOCKED_SECURITY_REVIEW，AC-1离线软件继续。** 如需删除/收窄规则，须提交独立精确云变更申请，本轮未执行。

后续只读访问回执补充确认旧站HTTPS/8883 TLSv1.3主机名和证书校验通过、匿名静态HEAD200；没有验证带令牌公网API/WSS受众或publisher/subscriber ACL。INPUT默认策略ACCEPT不等于已经裁定完整有效访问路径。上述新事实不解决安全组和历史规则文本缺口，不解除正式发布阻断。
