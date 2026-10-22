# VOICE-002 有界执行计划

负责人已明确“合同内所有步骤均授权，不需要单独提问授权”；本计划列精确范围，不再申请重复审批。
各窗口执行前绑定当次HEAD、文件SHA和UTC到仓库外卡；现场接线/听音仍须真实回报。

## AUTH-CVOICE-BOARD-01

唯一C、J-Link/SWD1000kHz，期望当前43172B应用 `b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe`。
先实读UID与私有参考匹配、RDP、完整64KiB双份及磁盘回读、generation3/336B配置、sector7/11/options、FLASH_SR/CR。
当前64KiB期望 `49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4`。
配置期望 `395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b`。

候选BIN 47324B SHA256 `ad51f436284b314c8287df8541a94e44ba581124521807be5a6df532a130af8d`，
ELF `c2a18b793bef6c329d29a619dec7f1b89b2b81c1e665688c3acb3d0874e512cf`，
MAP `d14e7f2fb5762e2f601f928f43f4fa3aedea1b7c9faf331b635153d08d15d8dc`。
实际加载 `[0x08000000,0x0800B8DC)`；完整48KiB FF补齐块只写sector0/1/2，止于0x0800C000。
sector3整16KiB及7/11/options不写，禁止mass erase、RDP变更、SetPC/MSP/VTOR/GO强启动。
程序写后整个64KiB应等于新48KiB块+原sector3；核对保护区及控制器状态。
失败停，不自动重试；本轮明确回退范围仅使用本窗口原48KiB恢复0–2，并重新核验64KiB与保护区。
临时调试IWDG冻结位只在halt维护期间置位，恢复原值并核验。程序退出不自动运行。

接线需先断电确认P3/PA2/PA3，ESP使用原USART3，正常运行BOOT0/1 GND、J5独立供电并拔除USB/J-Link。
8Ω1W仅v1一次短句（最多60UTF8字节），不循环、不自动重试；若仍为此负载，多条/连续声学工程测试保留BLOCKED_POWER。
STOP旧实板无4F，继续BLOCKED_STOP，不将按键取消标为已即时静音。
原业务先观察，按键只设置音量和60s单次许可；云消息过期/网络重连不会补播。
实际单次窗口最长2小时；单次下载与后续受限回退分别记动作卡，禁止借旧审批漂移镜像。

## AUTH-CVOICE-CLOUD-01

只通过现有SSH别名连接。新release内容逐文件SHA冻结后，经E:/Server_file上传并远端校验后清理本次暂存件。
生产Backend、Broker监听/TLS配置、Nginx其他站点、原H3 release和AI账本不改。
受限双份备份：现有ACL/password、medical-monitor Nginx snippet、H3 AI unit/env、当前Web定位；实际云操作卡绑定这些当前SHA。
只给当前C身份增加 `read mpm/v1/GW-C-001/voice/reply`；新独立短期publisher仅该topic write，口令服务器生成/私密注入。
Broker仅HUP重载ACL/password，先后核对原连接、8883 TLS、错误主题/反向读写/跨Gateway拒绝；不开放8884、不改安全组。
候选AI仅loopback高端口，候选Web保留原七页布局/鉴权/Origin，切换仅medical-monitor的AI路由和静态定位；旧Backend/WSS路由不动。
有界两小时窗口、默认voice OFF、页面每次发送后自动撤销勾选；C还需本地许可，浏览器Broker回执不冒充设备DONE。
测试模型仅 `doubao-seed-2-0-mini-260428`，最多3次/5000Token，不自动重试；专项持久预算窗口保留未知请求的预留量。
测试问题：请用一句不超过十二个字的中文给出一般健康提示，不含数字，不判断读数。来源仅现有非人体MOCK、无个人身份/原波形。
服务器原有账户/预算门禁继续生效；费用按UNKNOWN记录，不推断免费余额。
正式播报只取本轮审核后模型回答的完整短句≤60B；超长不截断、不替换示例、不下发。

阶段结束实际回退本轮AI路由/Web/ACL/password至双份备份并复核SHA；停新候选服务，删除精确临时规则/角色。
回退C仅上述0–2；分别验证HTTPS/WSS/8883，不能称全设备/云安全组回退。
不创建新tag；只有整项工程PASS且负责人核准才可冻结新tag。

云窗口细化：候选AI端口127.0.0.1:18796；原AI18786和Backend18785不停。两个既有宽C通配角色只对voice/reply新增精确deny，避免旧Backend收语音及旧publisher越权。准备双份原件后安装110分钟自动回退定时器，再变更ACL/password并HUP，候选健康通过才切medical-monitor snippet。A已移除，PPG300s与A/C新实板非回归标BLOCKED_SOURCE，本轮只争取一条可闻。
