# G3 入口上下文档案（静态只读）

证据基线：`01864fb4c1ea35c9da38aa98b1e85790d2ed5415`。下文行号均指该基线，不指后续候选补丁。范围仅为入口上下文及调用方假设；不评价漏洞等级，不代表任何现场准入。

执行方法：使用 Python AST 和逐段文本阅读分析源码，未 import 业务模块，未执行 G3 命令，未构造 COM、SDK、网络客户端。分析所得结论为 `STATIC_CONTEXT_ONLY`。

## 1. 调用关系

```text
b5_g3_joint.main
  默认无执行旗标 -> 输出 disabled 计划/criteria/工具字节哈希
  --ack-c-reset -> load -> g.validate(G3) -> 阶段文件存在性 -> 写负责人复位确认记录
  --joint-worker / --c-worker
    -> load -> g.validate(G3/HW) -> 父 .used 存在性
    -> joint_worker / devices.c_preflight
  --execute / --c-check -> supervise
    -> load -> g.validate(G3/HW)
    -> 一次性写 .used -> 新 worker 进程 -> main 再次验证

g.validate(G3)
  已登记分路 scope -> channel_profiles.validate
  否则 -> 旧 G3 自身 scope / 全套绑定验证

joint_worker
  -> serial.Serial/open
  -> 新 B-worker 进程 -> devices.main -> g.validate -> 父 .used -> b_worker
  -> cloud.run 线程 -> asyncio.run(observe)
  -> READY / reset intent / reset确认 / ARM基线齐备
  -> start_once -> 先写 ARM_ATTEMPT -> 串口写8字节
```

证据：`node-b/tools/b5_g3_joint.py:237-307`、`:109-166`；`node-b/tools/b5_g3_contract.py:116-127`；`node-b/tools/b5_g3_devices.py:213-219`；`node-b/tools/b5_g3_cloud.py:191`。

## 2. 入口与函数契约

| 函数/入口 | 已建立的前置条件及保证 | 调用方承担的假设/未建立项 | 分类 |
|---|---|---|---|
| `joint.main` 默认分支，282-288 | 无执行旗标时只打印计划和哈希；不调用 supervise | `g.bindings()` 读取工具文件，依赖工作树字节；它不是固定Git树证明 | SAFE_OFFLINE（本轮仍仅静态阅读） |
| `joint.main --ack-c-reset`，291-296 | 先验证G3；要求 `.used`、SERIAL_READY、RESET_REQUESTED存在且ARM尚不存在 | 确认文本是操作者上报，非真实复位电气证据；入口仅检查父标记存在，不解析其身份内容 | FIELD_DENIED |
| `joint.main --joint-worker/--c-worker`，297-304 | 先 `g.validate`，再检查父 `.used`，再进入工人 | CLI flags未互斥；多个flags时按代码分支顺序优先；父标记内容/nonce与本次auth之间的匹配在此未找到 | FIELD_DENIED |
| `joint.supervise`，237-279 | 验证后要求输出路径不存在；先独占写 `.used` 再创建worker；监督主机/串口期限 | 停止进程不等于MCU停止；成功依赖工人的回执真实性。真正目标动作权限来自验证链，不来自函数名 | FIELD_DENIED |
| `joint.joint_worker`，109-234 | 仅使用传入auth/bundle；事务文件独占创建；记录原串口和各级回执 | 函数体未重新验证auth，也未独立检查Mock/Field驱动模式；直接Python调用依赖调用方已验证 | REQUIRES_SANDBOX（无设备Mock）/ FIELD_DENIED |
| `joint.start_once`，54-65 | 要求允许START和owner标志、六份前置记录及新鲜banner；先写尝试再写串口，短写失败不重试 | 依赖传入串口属于已授权实例；未在该函数验证Git、板卡、签署、nonce；8字节返回不等于MCU接受 | REQUIRES_SANDBOX / FIELD_DENIED |
| `contract.validate`，116-189 | 按scope分派，绑定工具、环境、候选、原件、site、时效；私有引用经EFS约束 | 旧分派列表止于R5，R6只在Profile登记，导致联合入口与单函数的准入域不同 | SAFE_OFFLINE仅限内存合成原件及文件替身 |
| `profiles.validate`，79-175 | 分离B40928/B41012；绑定profile/card/criteria/B/C/云包及C预检时效 | R6 `OFFLINE_MOCK`跳过freeze分支；非Mock下`pi_signature`仅检查真值。未建立可验证的PI签署或现场驱动隔离 | REQUIRES_SANDBOX；FIELD_DENIED |
| `devices.main --b-worker`，213-219 | 先G3验证、父标记存在性，再b_worker | 父标记同样只检查存在；无独立nonce身份验证 | FIELD_DENIED |
| `devices.b_worker`，149-210 | 按bundle读身份、全Flash/options，比较指纹；有限采集；记录失败 | 自身未检查现场授权；调用方需已保证a/bundle/target对应。正常close前显式设置resume-on-close | FIELD_DENIED |
| `devices.c_preflight`，121-146 | 读取C身份、全Flash/options、冻结4字节flags；要求DISARMED | 自身未重新验证授权，依赖bundle和冻结flags地址。成功路径`set_close_resume(True)`，不能称“无任何CPU状态副作用” | FIELD_DENIED |
| `cloud.run/observe`，69-191 | 仅观察MQTT/WSS/health，不发布业务遥测 | 无独立auth验证，调用方需已核验；observe会建立真实SSH转发、MQTT连接和WSS认证，不是纯离线函数 | FIELD_DENIED |

## 3. 副作用边界

1. `joint_worker`先创建私有输出文件（109-124），然后创建`serial.Serial`并`open`（126-130）。设置DTR/RTS为False只是请求，不证明开口时无物理脉冲。
2. 串口已打开后才创建B工人（133-134）和云线程（135）。因此“后续B身份失败”不证明之前未影响C串口。
3. B工人构造`BLink`（156附近）经继承最终到`readback_b.Link.__init__`；后者先打开日志、设置DLL目录并`ctypes.CDLL`（45-57）。目标身份在SDK open/connect之后读取，不能作为连接之前的身份担保。
4. `readback_b.Link.open`先下发策略，再选USB/OpenEx，检查VTref、SWD速度及Device/Connect（115-137）；源码说明Device选择可能自动连接。
5. `cloud.observe`先读取外部连接配置（70-71），再选择本地端口（73）并启动SSH转发（81-84）；随后本地socket探测（89）、MQTT连接/订阅（108-113）、WSS连接与令牌首帧（114-117）。没有业务publish不等于没有网络副作用。
6. 正常B工人通过末次核验后允许Close恢复（194附近）；C预检也在成功路径允许Close恢复（138）。异常路径调用Close与关闭主机进程都不能证明目标最终仍运行或未运行。

## 4. import上下文

对四个入口模块的本地顶层import闭包作AST递归检查，共25个本地模块。忽略函数体、lambda体和`if __name__ == '__main__'`分支，未发现模块顶层直接构造DLL、COM、socket连接、子进程或文件写入。仅观察到常量、地址字典、Path构造及`sys.path.insert`。

闭包包括：`b4_recovery`、`b4_runtime`、`b4_swd_install`、`b5_b_temp_readonly`、`b5_b_temp_update`、`b5_channel_profiles`、`b5_g0_readonly`、`b5_g1_cloud`、`b5_g1_smoke`、`b5_g2_site`、`b5_g2ro`、`b5_g3_cloud`、`b5_g3_contract`、`b5_g3_devices`、`b5_g3_joint`、`b5_sector3_plan`、`b5_sector3_write`、`b5_sector3_write_protocol`、`b5_sector3_write_supervisor`、`c_b4_closeout_readonly`、`c_b4_readonly`、`live_state_b`、`readback_b`、`resp_exploratory`、`runtime_state_b`。

这只覆盖本地源码静态结构，不证明第三方包、Python导入钩子或SDK自身无副作用；任何测试仍需预先安装无设备/无网络的替身，不能用“import看来安全”替代隔离。

## 5. 文件、标记与身份假设

- `.used`由`g.save -> write_private`使用`xb`独占创建，且要求私有根和EFS属性；已有标记会阻止同一路径复用（`b5_g0_readonly.py:186-190`）。
- worker只检查`.used`文件存在，未在入口重新核对其`authorization_sha256`、scope或nonce内容（`joint:299`、`devices:218`）。
- `g.private.read`要求Windows及EFS私有根（`b4_recovery.py:33-49`）；合成测试不应从EFS伪造现场许可，而应在内存中替换该边界。
- `g.bindings()`覆盖既有工具集，依赖修改后的工作树；不等同验证某个Git提交，也不主动校验可执行nonce来源。
- `g.validate`读取完整外部bundle，其中存在凭据引用。本报告仅列字段名和调用关系，未输出任何真实身份、凭据或端点。

## 6. Open questions / 未建立的保证

1. PI签署的可验证凭据根、签署载荷、签署范围及撤销策略：当前基线未找到实现；不能把任意非空字符串当作签署。
2. Mock与Field之间是否有不依赖调用方自填字段的驱动隔离：当前基线入口未找到；本轮只能Mock验证拒止，不能尝试真实设备路径。
3. 单次nonce/父标记对授权、板卡与事务的唯一绑定：当前入口未找到完整内容验证；`.used`路径独占只证明同路径不可重写。
4. SDK Open/Device/Connect/Close的原生隐式CPU行为及真正的退出后状态：需独立SDK审查及未来有界板卡授权，本报告不推断。
5. 函数直接调用绕过main或supervisor时，由谁保证先验证：目前依赖调用方，内部工人函数未自证。

以上为上下文开放项，供候选补丁阶段定位最小修改；不是授权新增签名系统、重造整套工具或开展实板验证。

## 7. 本轮状态

`STATIC_ENTRY_CONTEXT = COMPLETE`；`FIELD_EXECUTION = NOT_EXECUTED`；`SDK_LOAD = NOT_EXECUTED`；`COM_OPEN = NOT_EXECUTED`；`CLOUD_CONNECT = NOT_EXECUTED`。后续候选补丁与Mock回执由主执行者单独归档，本文不将静态阅读记为测试通过。
