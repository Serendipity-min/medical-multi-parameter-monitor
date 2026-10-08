# P5 普通功能测试

`python gateway/mqtt/tests/run_p5_host_tests.py` 编译官方 coreMQTT v2.3.1、真实
Gateway Transport / Adapter / Canonical Model / Router，只有 ESP I/O 与配置是固定合成夹具。
38 项 C 用例覆盖 QoS0/1、PUBACK 匹配/迟到/缺失/重复/跨会话、部分 I/O、保活和 publish-only。
`python -m unittest discover -s gateway/mqtt/tests -p 'test_p5_integrity.py'` 为 6 项离线来源契约测试。

Linux 使用已有 GCC；Windows 通过已有 HERA-C3 WSL 运行同一入口，不安装工具或访问生产 Broker。
Windows Git 提交标识由父进程传给 WSL，解决 worktree `.git` 使用 Windows 绝对路径的问题。
各次编译和运行结果保存在忽略的 `build/p5-tests/<UTC时间>/`，摘要为 `latest.json`。
证据包含编译输入 SHA256；时间预算断言使用合成单调时钟，不能代替 F407 的 CPU/协作延迟实测。

全部为普通功能测试，不启用 ASan/UBSan、Fuzzing 或统一 Security Gate。
真实 TLS、异常断连后的 Broker Will/retain、硬件恢复及动态资源尚待独立窗口和证据。
