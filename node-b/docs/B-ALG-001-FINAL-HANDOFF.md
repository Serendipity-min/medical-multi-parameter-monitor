# MPM-B-ALG-001 阶段交接

日期：2026-10-22，Asia/Shanghai。唯一权威裁定：**B1_SOFTWARE_PASS / B2_B3_BLOCKED_SOURCE**。
当前只完成B0软件审计与B1离线验证，不能宣称Node-B真实ECG/HR或阻抗RESP/RR算法闭环。
负责人说明模块尚未连接、B未与C相连；本轮未操作开发板、源板S、模拟器、A/C或云服务。

## 1. 版本与变更边界

| 对象 | 实际身份 |
|---|---|
| 受审基线，开工远端重新核对 | B@f8c99433561b2e110c04ba9fb33c30235910a3e9 |
| 独立工作区 | E:/medical-monitor-node-b-bio-v2 |
| 本轮唯一写分支 | codex/node-b-bio-v2-test-20261022 |
| 已停止语音提交 | ba61ae2c97204f240d8fa6f316eb700aff70d29e；写入锁已释放 |
| 算法源bio_v2.c | 3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7 |
| 当前B实际运行镜像/UID/全Flash | NOT_OBSERVED，不能用重建BIN替代 |

仅新增离线测试run_pretest.py、离线身份审计audit_biov2_identity.py、脱敏证据和文档；固件、驱动、BIO_V2参数/阈值、UI、CAN、旧profile均未改。
不改B/B2/A/P4/main/H3/P6/语音保护分支，不合并、不创建PR/tag，不运行Security Gate，不上传原码/UID/完整Flash或DSP库。
最终准确提交SHA由Git元数据、推送后远端取回核验及仓库外DELIVERY-RECEIPT.json/最终答复提供，避免本文件的commit自引用。

完整身份/接线/手册审计见[B0-base-and-risk.md](B0-base-and-risk.md)，它是本报告支持证据，不是第二份阶段裁定。

## 2. 阶段门

| 阶段 | 实际裁定 | 依据/限制 |
|---|---|---|
| B0软件基线 | PASS_WITH_NOT_OBSERVED_HARDWARE | 指定远端/源码/工具/手册已核；B板和电气路径未观测 |
| B1 | B1_HOST_ARM_PASS_WITH_LIMITS | 新跑Host/ARM、旧共同削顶失败重现、8412历史回放 |
| B2 ECG/HR | BLOCKED_SOURCE_AND_FIELD_PERMISSION | 无今天实物身份、I导联幅值/频率、接线及专项卡 |
| B3 RESP/RR | RR_ACCURACY_NOT_TESTABLE / BLOCKED_SOURCE | 1K/变化量为手册声明，作用电极对与实测未明 |
| B4修复/候选准出 | NOT_STARTED | 未取得合格真实输入下的算法误检/漏检失败，不改算法凑PASS |
| 三板CAN | NOT_AUTHORIZED / NOT_CONNECTED | 本轮不接A/C；当前B代码Node-ID3/1Mbps与未来H3 Node-ID2规划另行处理 |

ECG_CANDIDATE_PASS、RESP_CANDIDATE_PASS均未签发。没有当前真实波形、逐峰误差或RR准确度结果，表中不填样例数字。

## 3. 本轮真实软件测试

| 检查 | 实际结果 | 退出码 |
|---|---|---:|
| python node-b/tools/run_host.py | 全部7个子进程成功 | 0 |
| BIO_V2常规合成 | 27/27 | 0 |
| 通道隔离合成 | 28/28，含旧共同失效复现和健康路逐帧等价 | 0 |
| FIFO C测试 | 2561断言、0失败，不是并发实板压力证明 | 0 |
| 采集工具 | 27/27，含冲突/重复、暂停尾段、篡改/身份、复位和signed24 | 0 |
| S控制台、ROM、BIAS Host模型 | 34/34、19/19、9/9，仅模型 | 各0 |
| 新增pretest | 13/13（10项合成/边界、3项历史条件检查） | 0 |
| ARM | 0 errors、0 warnings；无旧算法符号 | 0 |
| ARM offsetof/Host及旧profile | 31个布局常量相同；真实新BIN被旧profile精确拒绝 | 0 |
| 原归档字节检查verify_bundle.py | 266文件、0失败 | 0 |

不把case、unittest和C断言相加成“算法准确率”。合成Gaussian/正弦是软件输入，不是mV/Ω标定或模拟器实测。
预热5s/10s、至少3个新间隔、断流100/101ms边界、初始化/旧周期不续活、源flags/序号/时间回退、tick与序号双uint32回绕均由实际C算法执行。
50/100/25Hz及其它非QRS正弦、白噪声检查在原27项内；不把MAINS指标解释为真实50Hz频谱占比或唯一硬件根因。

原始日志/回执分别保留于../evidence/B-ALG-001/{host,arm,pretest,abi}/，命令、UTC/平台见commands-and-environment.json。
原run_host回执明确跳过私有回放；随后新增入口单独重放8412帧，不改原回执为通过，也不修改原始输入文件。
历史首次公开测试私有身份文件缺失的FAIL仍在既有evidence/first-public-host-failure.json；本轮没有重认领其修复。
本轮离线ARM布局探针首次解析额外VFE DCD而失败（退出1，编译本身0），限定导出数组后重新核验通过；两个轮次/原因保留preparation-failures.json与原本地构建目录。
私有空目录ACL初始化曾因SID格式失败（退出1），未写私有内容，修正后再建租约。没有覆盖功能FAIL或修改固件。
全暂存diff格式检查退出2，仅原始ARM build.log/symbols.txt的尾随空格/末空行；原日志逐字节保留，未归一化或改属性掩盖。新写工具/文档聚焦格式检查退出0，完整诊断和分类见format-check-raw.log、format-check.json。

## 4. 历史失败回放

| 冻结输入 | 本轮结果 |
|---|---|
| 8412×24B开放输入 | 实际访问/只读回放；201888B，SHA256 2dc6b0ac56c5d6901abfda4c0ea851b28d54e2c55b02b2d760740c43ad2b7ccf |
| 来源/参考 | 历史正常配置、外部开放输入；CH1全部正轨；无ECG/RESP真值 |
| 旧共同削顶C | samples=0、last_sequence=0、clipped=8412，HR/RR有效帧均0；旧FAIL确实重现 |
| 当前C | samples=8412、last_sequence=8412、clipped=8412，HR/RR有效帧均0；末HR原因66、RR34 |
| 结论 | 修复保留帧证据且不连带重置健康路；此历史源依然不合格，不认证精度 |
| 37169帧外部CSV | NOT_RUN_EXACT_SHA_NOT_FOUND；指定SHA943d59b3dc723820a0d287b06534c4be31fd91442977f978a2e38d8422b3ce53未找到 |

准确完整性统计见historical-input-integrity.json。原帧不改flags/时间、不补样、不入Git；没有凭旧报告重造37169帧或抄写旧857帧有效作为本轮结果。
该原码回放只作表征，未计算基于未知参考的HR偏差、漏检/误检，也没有呼吸准确度。

## 5. 构建身份与资源冻结

本地已核DSP=13294064B，SHA256 ba416f23efb992105c36b67d9002d8142e38877d1010c0e0a1d0f74b83325ab7。
Keil/ARMCC5.06u7，在独立ignored build目录复制构建，无下载/烧录。

| 产物 | 字节 | SHA256 |
|---|---:|---|
| BIO_V2.bin | 25284 | 438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae |
| 本轮BIO_V2.axf | 576180 | 6c3f9497d821df82c07bc499b6ced7d96fe1d5d0a6283dbb6fa18c14e081f580 |
| 本轮symbols.txt | 91767 | 62d191709b0eec491cf66f4accd6c96ddc8701f86ad2c05c6dd8a7feb38bf6dc |

BIN与合同候选相同；ELF/符号表含路径等构建信息，分别记新SHA，不冒充历史ELF。
Code24232、RO968、RW332、ZI11748B；RW+ZI=12080B；静态资源相对历史同候选无变化，未测动态CPU/栈高水位。
BIN映射从0x08000000至0x080062C4（末端不含）是构建信息，不是今天的板上地址/擦写授权。
ARM确认BioV2Diag120B、tag/ABI2及精确字段偏移；离线布局缺UID/完整Flash绑定，不能直接用于SWD运行态采集。

## 6. 模拟源与现场下一步

SKX-2000D+手册12页已全部渲染查看，SHA256 27fe9e4a37a761ab7df939bf49693942dbf3e5692f09e2e10311106053503cc8。
资料支持I=RA–LA、II=RA–LL及呼吸基础1K/可调变化量，但没有证明今天实物输出、I幅度精度、RL主动反馈兼容或呼吸变化电极对。
手册列正常ECG同步20bpm呼吸，未来ECG与RESP测试必须明确这种耦合，不能把呼吸菜单/电压波形自动当已知阻抗。
本轮B/C未连不阻碍B0/B1，也无需为独立算法测试提前连CAN。

下一次先收集实物型号、非人体源/模式、可用幅值/频率参考及呼吸电极资料，再提交精确AUTH-B-ECG-01。
该现场卡必须绑定今天B角色/UID、双读完整Flash与受限恢复、候选BIN/ELF、实际导联触点/PG15/PA3/SPI、寄存器回读、供电/仪器、profile、时长、停止条件和当次许可；未填项不启动。
本合同不授权现在读UID、接J-Link/电极、上源、烧录或采样；不把准备卡当授权。
建议ECG60/90/120bpm每档≥60s×2、RESP12/18/24次/分每档≥90s×2仅为合同建议工程矩阵，待PI确认；没有实际执行。
ECG合格后RESP另获AUTH-B-RESP-01，先证实动态阻抗作用于CH1所测电极路径；人体采集始终不在范围。

## 7. 保存、推送与停止

源、工具、原始退出码/失败和脱敏摘要在新实验分支；本地受限E:/medical-monitor-node-b-bio-v2-private保存输入路径清单/租约/交付回执。
历史原码原件仍在原位置且SHA前后核对；BIN/AXF/DSP仅本地ignored构建目录，不随本次提交。没有新全Flash或设备回滚，因为没有读写任何硬件。
原工程88份源文件、既有266份归档校验未变。无新云上传、真实人体记录或正式Broker接入。
正常提交推送本独立分支，独立取回校验后释放B软件写入锁；停止于B0/B1交付，等待实际硬件/信号源条件与现场卡。
