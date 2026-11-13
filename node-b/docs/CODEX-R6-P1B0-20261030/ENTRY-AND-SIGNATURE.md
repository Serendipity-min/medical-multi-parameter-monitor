# P1-B 薄入口、信任根与复用审查

## 路径表

| 路径 | DLL / 目标 | nonce / worker | 放行状态 |
|---|---|---|---|
| `b5_codex_p1b_readonly.py` 无参数、`--plan --board B/C` | 无；只读本机源码计算 SHA | 不创建 | `enabled=false`，历史目标定义，不声称当前实装 |
| `--execute`，含任意 `--authorization` | 在读申请、导入 SDK、枚举、COM、child 前拒止 | 不创建 | 无条件 `P1B_FIELD_NOT_AUTHORIZED / 1` |
| `verify_mock_authorization` | 数学 Ed25519 验签；不加载目标 DLL | 不消耗、不建 worker | 离线辅助函数，不连接到 CLI 放行 |
| `consume_mock_nonce` | 无目标 | 测试调用方固定 `execution_context=OFFLINE_MOCK`；独占创建 `.used` | 仅 Mock；JSON 不能选择生产执行上下文 |
| `validate_worker_marker` | 无目标 | 比对完整授权 SHA、nonce SHA、board、scope，非仅文件存在 | 未来 worker 绑定原型 |
| `capture(link, board, reference, save)` | 仅通过调用方传入适配器；函数会 open/read/close | 不接收授权 JSON，不创建 worker | 低层库函数，**不自带授权能力**；本轮经明确负责人直接指令调用过真实适配器 |
| 本轮临时交互 dispatcher | B/C 只读、安装、RR 的实际路径，详见现场日志 | 新事务、独立一次性记录；不是可复用生产 PI token | 仅当期直接授权；不作为后续可调用的默认 CLI 发布 |
| 旧 G3 CLI / 旧 disabled 卡 | FIELD 对 R6 拒止逻辑不变 | 不将旧 `.used` 或 G3 卡移用为本轮权限 | 未启用；旧 G3 业务 JSON 不能打开 P1-B CLI |

整个工作轮发生过真实目标调用；“Mock 原生调用 0”仅限对应隔离进程。不得把这份交付标为纯离线现场零调用。

## 签名设计

采用 Ed25519 对**确切 UTF-8 授权字节**签名，公钥 SHA256 由可信外部渠道钉住，私钥由 PI 在仓库外管理。当前生产公钥/指纹 `NOT_CONFIGURED`、现场签名 `NOT_CREATED`、Gate F `NOT_SIGNED`。测试中的确定性种子只在内存生成明确合成私钥，没有生成实际 PI 私钥、实际可接受签署文件或有效生产 nonce。

待签对象至少绑定：B/C 各自 scope、board、完整 repo commit/tree、全部工具 SHA、DLL SHA、身份/Options 引用 SHA、完整 Flash SHA、精确地址/长度/次数、时限、当期接线与供电记录 SHA、异常人工责任、SDK 策略、有效期、nonce 及风险确认。`expected` 的完整字段集合在入口校验，不能通过缺字段退化成只验一个布尔值。数学验签成功不能证明调用方提供的公钥/expected 来源可信，故该辅助函数没有生产准入效力。

签名/时间/板卡/哈希/地址全匹配后，未来父进程才可在各自受保护目录中 `open('x')` 原子消费 nonce；`.used` 存授权 SHA、board、scope、nonce SHA；worker 须核对内容与原始字节。本轮仅测试该设计，不承诺跨主机、网络文件系统或崩溃持久化语义已经验证。不创建多板共用 token，不接受非空字符串签名、`owner_approved=true`、自填字段作为生产信任根。

## 复用和差异

| 组件 | 复用方式 / 限制 |
|---|---|
| `b5_g3_devices.BLink/CLink` 与父类 | 固定读方法、真实返回日志、既有策略及 Close；未重写驱动；风险见 SDK 表 |
| `readback_b.identity` | 只复用精确身份读取；没有调用含 Halt/Go 的 `acquire` |
| `b5_sector3_write_supervisor.watch` | 只复用主机进程/原生心跳监督；不调用 sector3 写路径 |
| `b4_recovery.make_plan`、`b4_swd_install` | 根据当期追加安装授权复用原安装器，未修改安装器源码 |
| `b5_g3_joint.joint_worker` | 只加 keyword-only `b_worker_command=None`；默认子命令不变；由直接调用方提供当前一次 B41012 worker，申请 JSON 无此覆盖字段 |
| `b5_g3_devices.b_worker`、cloud/collector | 本轮交互包装传入已核对的真实 B41012 profile/引用，复用采集实现；没有 monkeypatch `g.validate` |
| `b5_channel_review.py` / R5 criteria | 原字节冻结；本轮仅评新 RR15 一次，无旧 R5 回放 |

P1-A 登记 37 项源码中 36 项不变，唯一差异是 joint 的上述参数；见 [accepted-source-preservation.json](../../evidence/CODEX-R6-P1B0-20261030/accepted-source-preservation.json)。静态 AST 检查证明默认参数为 None、默认命令来自原表达式；这不是全量旧业务运行集成测试。旧 R1–R5 默认路径未改，本轮不重复旧 151 项矩阵。

B/C 现场执行的薄入口源码 SHA 是 `79b59e21e4fff1b055af3faccb5eb9c7c111e7fb806890a180e224056e536021`。随后完善了离线签名绑定/plan 文案；最终源码不冒称全部曾现场运行。`capture/read_state/killed_receipt` 的执行快照与最终版 AST 相同，核对见 [executed-vs-final-source.json](../../evidence/CODEX-R6-P1B0-20261030/executed-vs-final-source.json)。RR 自己冻结了 joint 与两份临时 worker 的源码快照/输入 SHA，私有原件未入库。

## CPU 复现

在仓库根目录运行：

```powershell
python -X utf8 node-b/tests/run_codex_p1b_mock.py
$mockExit=$LASTEXITCODE
exit $mockExit
```

runner 使用假 serial 模块，audit hook 拒绝 DLL 加载、subprocess、socket 连接/绑定，Serial 入口也拒止；不会连接目标。已存在的 `cryptography` 用于数学签名，未新增安装依赖。最终 16 项、0 失败/错误，真实 shell 0；先前 12/15 项及收尾 guard 初始化失败保留，未覆盖为 PASS。测试单独临时目录消费的是合成 nonce，不是生产授权。
