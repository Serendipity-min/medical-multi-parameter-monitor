# M1逐次执行卡模板：全部禁用

本目录24个 `.disabled.json` 与[唯一拟议矩阵](../MULTIRATE-MATRIX.proposed.json)逐一对应。每个条件3次、run_id不重名，当前实际采集次数均0。它们是供评审的文档数据，没有CLI/真实执行入口，未向任何旧worker输入，不是可自填启用的凭证。

每卡现场权限/次数为0；`enabled=false`、`execute=false`、`execution_entrypoint=null`、`allowed_actions=[]`。签署、固定信任根、nonce、token、有效期、实际现场确认、SDK/DLL/工具哈希及原生Open/Close策略、完整会话预算均null；actual_menu及实际BOOT/目录也null，目标值只在proposed字段。

未来签发须在独立权限包中绑定B41012原一致构建调试制品、真实身份/全片/options参考（受限EFS）、签署者固定信任根、工具及DLL/新Scope哈希、逐次run_id/时限/次数、不可复用nonce及消耗记录、当前供电/接线/源确认、人工停止与异常处置责任。默认关闭不能通过OFFLINE_MOCK、非空签名、自填owner_approved、改布尔值或旧G3卡绕过。

当前P1-B生产CLI仍禁用且历史B目标为B40928，旧E3入口固定137s/旧ABI，旧G3固定业务范围；都不能直接接收本卡或用于B41012新165s矩阵。下一轮先审查最小薄适配/独立评测器及Mock，再由PI逐块独立授权现场；不在本轮重写整套工具链，也不把签JSON当可信执行器已经落地。
