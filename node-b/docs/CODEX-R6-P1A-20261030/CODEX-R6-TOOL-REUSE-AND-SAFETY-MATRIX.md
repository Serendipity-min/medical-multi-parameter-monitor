# R6 工具复用及副作用矩阵

策略：REUSE_FIRST / AUDIT_BEFORE_USE。版本为固定基线与本次候选分支；逐文件基线/当前 SHA256 见证据目录 `tool-registry.json`。更完整的函数、API及源码行依据见 [入口上下文](audit-context/ENTRY-DOSSIER.md) 和 [SDK上下文](audit-context/SDK-DOSSIER.md)。

| 工具 | 裁定与实际副作用 | 本轮分类 |
|---|---|---|
| b5_channel_review.py | 原样复用；重建、匹配、联评历史原件。CLI的save使用EFS，故本轮只调用纯review并写新审计摘要 | SAFE_OFFLINE（纯回放）；源SHA冻结 |
| b5_channel_profiles.py | 复用；仅修R6调用上下文与无条件Field拒止；不改criteria/旧身份 | REQUIRES_SANDBOX；候选 |
| b5_g3_contract.py | 复用；增加R6分派和默认Field拒止；bindings读取源码，private.read读取EFS | REQUIRES_SANDBOX；候选 |
| b5_g3_joint.py / supervise | 原样复用源码；现场会打开COM、启动工人/云线程、写START及授权消费标记 | FIELD_DENIED；仅内存main负例 |
| b5_g3_devices.py | 原样复用；工人构造BLink/CLink后加载SDK，读取Flash/options/RAM，成功Close可能续跑 | FIELD_DENIED；FakeLink测试可隔离 |
| b5_g3_cloud.py | 原样复用；真实执行将建立SSH转发、MQTT与WSS/HTTP观察 | FIELD_DENIED；仅纯快照函数Mock |
| build_b4_arm.py | 复用Keil/FromELF和既有源码，8锚点必须各命中1次；新目录保存候选源、MAP及身份 | SAFE_OFFLINE构建；不带下载 |
| test_timing_simulation.py | 原样模型；零成本出队等假设不覆盖真实FrameFeed | SAFE_OFFLINE；WCET_MODEL_ONLY |
| readback_b.py | acquire明确Halt/Go，不能作P1-B零控制入口；只复用日志/身份格式和受限SDK层 | FIELD_DENIED |
| b5_b_temp_readonly.py | 历史B40928 ABI；连接/关闭副作用需审查，异常时取消续跑失败可跳过Close | FIELD_DENIED；问题保持OPEN |
| runtime_state_b.py / live_state_b.py / b4_runtime.py | 含旧ABI与API/地址限制；不能将旧PC范围当新身份；Close可隐式续跑 | FIELD_DENIED；仅父类设计参考 |
| b5_g2ro.py / c_b4_readonly.py | C24104/旧C身份；不可直接套C49132；有独立原生读次数和预算 | FIELD_DENIED |
| b5_g0_readonly.py | main会经SSH读取真实服务，不是离线；write_private独占EFS写法可参考 | FIELD_DENIED（main） |
| R6旧BIN、候选源、symbols、14项清单 | 仅核字节/引用，不覆盖，不更新旧清单来掩盖新补丁 | SAFE_OFFLINE不可变参考 |
| EFS原件、.used、R5三份criteria | 绝对只读，输出摘要/哈希，不能上传原件 | SAFE_OFFLINE只读 |
| 新 b5_codex_offline_tests.py | 仅测试护栏，阻断SDK加载/COM构造/网络/子进程；不是新G3控制链 | SAFE_OFFLINE审计工具 |
| 新 b5_codex_p1a_audit.py | 仅文件校验、复用review/模型；只读原件、写新摘要 | SAFE_OFFLINE审计工具 |

可回滚范围仅本次主机候选提交；使用后续revert保留审计，不执行设备恢复，不改保护分支、旧BIN或历史授权。
