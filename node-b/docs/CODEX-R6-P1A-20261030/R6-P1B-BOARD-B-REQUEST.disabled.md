# P1-B Node-B 单板授权申请（禁用）

`status=NOT_AUTHORIZED`；`enabled=false`；`token=NOT_CREATED`；`nonce=PI_TO_ISSUE_ONLY`；`execution=HALT_BEFORE_CONNECT`。

申请目标仅核对历史实装B40928B：BIN 40928B，SHA256 `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`；历史1MiB全片 `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae`；私有UID/options由既有EFS引用定位，不能写入申请。

## 待PI冻结的具体范围

- 只允许一块B、一次新会话、零重试；提议整体90秒、全片原生读上限45秒、其他单调用5秒。所有时限必须在未来专用入口/监督器落实，现有G3业务预算不能直接继承。
- 提议完整Flash `0x08000000/1048576` 一次、options `0x1fffc000/16` 一次；UID/容量/CPU及运行态只按已审白名单精确读取。身份及原件仅写独占EFS；不读UART数据寄存器、不做CAN输入或采集实验。
- SWD提议1000kHz，精确DLL SHA为 `632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`；候选复用BLink及所有父类SHA见tool-registry.json，最终可执行入口仍须另审冻结。
- 当前负责人报告J-Link板端在B、板卡未上电。探针电脑端、供电/USB反供电、JTAG方向、唯一探针和当前照片仍需在签发时确认；本申请不要求现在上电或枚举。
- **前置阻断**：专用P1-B入口、可信PI引用/nonce、Open/Close隐式副作用与异常Close策略未闭合，禁止直接调用readback_b.acquire、b5_g3_joint或旧温度worker。
- 无任何Reset/Halt/Go/Flash/options/配置写；发生ROM/HALT、负返回、短读、超时、身份漂移立即停止，零重连。断电/保全现场由PI指定负责人及明确步骤；不自行恢复。

PI应在另行签发时给出有效起止时间、唯一nonce、准确入口及全部哈希、私有身份引用、供电许可、Close政策及异常责任。此文件没有签署，不能被程序当授权。
