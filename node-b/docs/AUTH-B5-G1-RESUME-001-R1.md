# AUTH-B5-G1-RESUME-001 R1｜只恢复隔离测试服务，待批准

`enabled=false; owner_approved=false; executions=0`。本轮不启动、重启或恢复任何测试服务，不撤销账号。此卡与G2-A/G2-B/G3及R-CLOUD分别批准。

只读生命周期回执确认：原G1独立Backend/TLS于北京时间2026-10-27 01:59:19因6小时驻留上限停止，MainPID=0，18775与8884均不监听；测试发布/观察账号及ACL仍存在。原人工MOCK PASS保留，不代表入口当前在线或已清理。

未来只使用既有G1 EFS `deployment-package-r2-private.json`、`test-entry-and-lifetime-private.json` 中的准确两个独立unit、exec路径、权限和专属日志；包SHA `dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0`。正式服务/ACL/password_file、测试代码/配置与unit须先只读比较到已批准SHA；端口占用、正式服务变化、文件漂移或私有凭据权限不合格即停，不临时打补丁。

另批本卡后，最多对这两个既有独立unit各一次start，最多300秒准入监督、重试0，沿用原Restart=no及6小时RuntimeMax，不扩驻留。没有Broker HUP/restart、ACL/password修改、daemon-reload、正式Nginx reload、公开端口/8884或正式AI动作。若unit已不适用，停并重提交，不改正式站点绕过。

仅在原CA/SNI、loopback18775、独立Hub/身份和正式服务不变证据齐全后，裁定测试入口恢复；访问通过SSH转发，不公布主机/令牌。无需重复既有人工正负例/七页UI套件。G3真实订阅/Backend接受/WSS取证另批，此卡不发MQTT测试消息、不发AT或B5START、不碰实板。

服务与账号生命周期分开记账。失败按停止状态保留日志，不自动执行R-CLOUD；实际撤销/回退仍需原独立R-CLOUD批准。
