# AUTH-B5-G1-RESUME-001 R2｜仅恢复既有测试Backend/TLS，待独立批准

`enabled=false; owner_approved=false; executions=0`。G2-B实际写入已PASS。本卡单独批准服务启动，不包括G3、AT/B5START、实板接线或恢复；此前配置写入许可不能借用。

采用新入口 `node-b/tools/b5_g1_resume.py`，SHA256 `73c0d4c7fba45f61414053f6c651435201bbc7014e4d4de6eb8df3b9bea5ba2f`，scope=`B5_G1_RESUME_EXISTING_TEST_UNITS_ONLY`。仅使用既有受限EFS部署包SHA `dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0`；实际两个unit、正式PID、全部正式配置/测试源码/测试配置/ACL/password SHA、私有文件模式与身份、CA/SNI目标均绑定私有inputs及授权SHA。精确依赖见 `../evidence/B5-G1-RESUME-PREP/bindings.json`。

2026-10-27北京时间11:06:48的新鲜只读查询确认：两个测试unit仍因原6小时驻留超时停止、MainPID=0，18775和8884未监听，测试账号/规则仍在，正式服务活跃且PID与配置SHA不变。这是启动前检查点，不当未来在线状态；启用时再只读核对同一组文件/权限/状态，漂移即停。

负责人另批本卡后独占生成一次EFS启用授权，有效期、输出目录、输入SHA、工具SHA、卡SHA、G2-B实测回执SHA全部固定。开始前消费一次`.used`，一次SSH，300秒总硬限；远端独立timeout280秒，重试0。当前只有disabled模板，未生成.used。

唯一写操作：对既有独立backend、tls两个unit按此顺序各`systemctl start`最多一次。正式unit、Broker、ACL/password、Nginx主站、正式Hub/AI、测试代码/配置均不修改；不HUP/reload/restart、daemon-reload，不新建unit、不开放8884或公网端口。旧 `b5_g1_cloud.apply` 禁用作恢复入口。

启动前两服务必须保持停止且18775空闲。任何首项start失败立即停，不启动第二项；第二项失败不回滚第一项。启动后只读TLS/CA/SNI验证及GET隔离Backend健康端点；健康轮询90秒内、服务启动预算60秒内，均受300秒总限约束。Backend按已有配置自主订阅测试命名空间，不能声称MQTT连接数为0；本卡不发布测试消息、不建立WSS业务会话、不发送B5START。

成功要求两测试unit均active、非零PID、Restart=no、RuntimeMax=6h；所有冻结源码/配置/权限通过，正式服务及PID不变、ACL/password不变、8884不监听，loopback18775 TLS及Backend状态/mqtt_connected为真。访问仍经已有SSH转发，不公开主机/令牌。不重跑人工MOCK正负例、七页UI或旧Host/ARM矩阵。

任何异常、超时、日志缺失即停且保留真实退出码；不重连重试、不修改配置绕过、不自动stop/回退。已start的测试服务可能继续受原6h上限管理，异常不能声称已清理。R-CLOUD单独批准。真实G3仍须独立批准及工具/现场附件齐备。
