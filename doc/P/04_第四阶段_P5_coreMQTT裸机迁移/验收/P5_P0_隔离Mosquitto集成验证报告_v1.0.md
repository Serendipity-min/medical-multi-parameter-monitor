# P5 P0 隔离 Mosquitto 集成验证报告 v1.0

日期：2026-10-08；受测代码：`e598fc63719acdf49a99c6da46c656dc8c607782`。
本轮已完成真实 Broker 普通验证，30/30 PASS；结果、源输入摘要、实际版本和进程清理见
[p0-broker-summary.json](evidence/p0-broker-summary.json)。

环境：已有 HERA-C3 / Debian / GCC14.2.0，Mosquitto 2.0.21（Debian 2.0.21-1）。
6 个官方 Debian 包总计748788字节；按既有 apt 索引固定 Version/Size/SHA256，经 Windows
`E:/Server_file/P5-isolated-mosquitto-20261008` 下载、核验、中转再核验，仅解压至任务运行时目录。
未运行包安装脚本、修改包源或启动系统服务。[包身份](evidence/p0-broker-packages.json)记录实际值。
暂存清理两次被自动审批策略拒绝（blocked by policy），6 个暂存包保留；不记作清理成功。

Broker 仅绑定127.0.0.1临时端口，禁匿名、使用固定合成身份/密码，persistence=false。
配置依据 [Mosquitto 官方手册](https://mosquitto.org/man/mosquitto-conf-5.html) 的 listener/password_file/retain 行为；
测试 observer 只处理有限的标准 MQTT311 观察报文，不进入 Gateway 业务实现。

P4：从固定 `8dee339` 提取真实 gateway_transport.c，仅将 Flash 配置指针换成合成配置；
原始文件摘要与唯一 shim 描述在结果 JSON 中。编译未改的 Hardened Paho 源。
P5：编译当前真实 Gateway、coreMQTT、Adapter、Model、Router。
两者仅把 ESP/AT/TLS 字节 I/O 换为本机 POSIX TCP；Gateway 仍 publish-only。

| 验证内容 | 真实观察结果 |
|---|---|
| 基本认证 | P4/P5使用同一合法合成身份连接；错误密码的观察客户端被 Broker 拒绝 |
| 状态/retained | ONLINE以QoS1到达；新订阅者得到 retained ONLINE |
| 标量/波形/REPLAY | 实际Broker分别交付QoS1/QoS0/QoS1；PUBACK ID与本次发布一致 |
| 载荷等价 | P4/P5正常状态、标量、波形、REPLAY和Will JSON逐项一致 |
| 保活 | 两个客户端真实空闲16秒，至少发出一次15秒机制的PINGREQ，随后仍可成功发布 |
| 异常断连 | 仅终止本工具持有的Gateway host进程；Broker发布QoS1 OFFLINE Will |
| Will/retained | 异常断连后的新订阅者得到 retained OFFLINE，JSON与真实Will一致 |
| 延迟正常PUBACK | 本机代理仅延迟Broker正常ACK 700ms；帧已到Broker但Router未提前成功；匹配ACK后成功 |
| 丢失正常PUBACK | 帧已到Broker，代理丢弃正常ACK；5000ms预算后P5失败，Router离线回存，seq/时间不变 |
| 资源清理 | 4个本工具Broker进程全部结束；只按持有PID处理，无生产服务操作 |

边界：这是 Broker/MQTT311 与真实客户端的对照，不是 ESP8266 AT/TLS 或 F407 的实测。
代理只延迟/丢弃正常PUBACK，没有改造畸形报文、随机输入、Fuzzing或公共目标测试。
真实TLS重连、CAN协作延迟、CPU/Stack以及全片Flash恢复仍待硬件窗口；安全门仍未授权。

执行入口：`python gateway/mqtt/tests/run_broker_integration.py --runtime <已核验运行时目录>`。
各轮原始编译/运行与Broker日志在忽略的 `gateway/mqtt/build/p0-broker/<UTC时间>/`。
早期P4编译的POSIX特性宏位置问题、目录/可执行文件同名问题均有失败记录；修正后最终整轮通过。
冻结P4 host对照仍有合成外部配置的GCC格式长度提示，没有回写或修改历史P4源码。
