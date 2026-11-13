# P1-B Gateway-C 单板授权申请（禁用）

`status=NOT_AUTHORIZED`；`enabled=false`；`token=NOT_CREATED`；`nonce=PI_TO_ISSUE_ONLY`；`execution=HALT_BEFORE_CONNECT`。

申请目标仅核对C49132B/gen5：BIN 49132B，SHA256 `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab`；历史1MiB全片 `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`。UID/options/sector3仅引用受限EFS，不公开。

## 待PI冻结的具体范围

- 一块C、一次独立新会话、零重试；提议整体90秒、全片原生调用45秒、其余5秒。完整Flash/options各一次，不用旧G2RO双读流程追加次数。
- 复用G3 CLink的只读方法及C49132实际flags地址绑定；仅允许身份/容量/状态、`0x08000000/1048576`、`0x1fffc000/16`、精确DISARMED flags读。flags数值地址须从既有C49132绑定复核冻结，不能猜测。应用外保护区由全片原件一致性判定，不写sector3/options/sector7/11。
- SWD提议1000kHz；DLL SHA `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`，所有继承层SHA见tool-registry.json；不是旧C24104工具的运行许可。
- 当前USB在C、J-Link板端在B、负责人称未上电。C接口类型/电脑端/ESP反供电/灯态未核验。未来如需转接，只能在另行明确的冷态方案获准后由负责人实施；本申请不授权转接、插拔、上电、COM探测或RESET。
- **前置阻断**：C49132专用只读入口/可信授权、Open/Close隐式控制政策、私有身份/flags绑定及现场事实需逐项冻结。不得经G3 HW scope或旧G2RO卡绕过本申请。
- 禁止B5START、AT/联网准备、CAN发送、Flash和云操作。任何不一致或原生异常立即STOP_TARGET_NO_RECOVERY，禁止自动重连/复位/刷回。负责人断电责任和保全步骤须在签发时明确。

PI须另行签发准确入口、全部哈希、唯一nonce、有效期、供电/接线许可及Close/异常政策。此文件未签署，不是现场执行卡。
