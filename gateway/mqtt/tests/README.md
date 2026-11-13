# P5 普通功能测试

`python gateway/mqtt/tests/run_p5_host_tests.py` 编译官方 coreMQTT v2.3.1、真实
Gateway Transport / Adapter / Canonical Model / Router，只有 ESP I/O 与配置是固定合成夹具。
42 项 C 用例覆盖 QoS0/1、PUBACK 匹配/迟到/缺失/重复/跨会话、部分 I/O、保活、publish-only
及有界 assert 诊断停机。新增故障用例仅替换寄存器动作和停机终点，不触发真机故障。
`python -m unittest discover -s gateway/mqtt/tests -p 'test_p5_integrity.py'` 为 6 项离线来源契约测试。

Linux 使用已有 GCC；Windows 通过已有 HERA-C3 WSL 运行同一入口，不安装工具或访问生产 Broker。
Windows Git 提交标识由父进程传给 WSL，解决 worktree `.git` 使用 Windows 绝对路径的问题。
各次编译和运行结果保存在忽略的 `build/p5-tests/<UTC时间>/`，摘要为 `latest.json`。
证据包含编译输入 SHA256；时间预算断言使用合成单调时钟，不能代替 F407 的 CPU/协作延迟实测。

全部为普通功能测试，不启用 ASan/UBSan、Fuzzing 或统一 Security Gate。
真实 ESP/TLS、硬件恢复及动态资源尚待独立窗口和证据。

## 隔离真实 Broker 对照

`python gateway/mqtt/tests/run_broker_integration.py --runtime <已核验Mosquitto运行时目录>`。
Windows 入口先由 Windows Git 提取固定 P4 Gateway 源，仅注入合成配置指针，然后在 HERA-C3
编译真实 P4/Paho 与 P5/coreMQTT。观察端为有限的 MQTT311 测试协议夹具；Gateway 仍 publish-only。
运行时须已有 Mosquitto 2.0.21，工具不安装系统包，不访问生产服务。

本轮已从官方 Debian 包经 E:/Server_file 中转核验后解压运行，30 项检查 PASS：正常遥测、
QoS0/1、LWT、retained、异常断连、真实15s保活、P4/P5载荷对照、正常PUBACK延迟/丢失和进程清理。
Broker 与受控代理只绑定 loopback、使用临时端口；所有客户端/服务 PID 由工具持有并结束。
输出在忽略的 `build/p0-broker/<UTC时间>/`，各次失败/成功均保留。

这是 POSIX TCP 与 MQTT311/Broker 层验证；AT/TLS 由测试 I/O 替换，不能代替 ESP8266 或 F407 验收。
P4/Paho 仅链接到 host 对照程序，不进入 P5 ARM ELF；旧 sanitizer 未执行。
