# ECG60单次负责人授权工程试验

基线cba0bcfeead7c0c0c38dd4046538b82ddf151722。负责人在本次聊天明确答复：

> 明确修订门禁，由我直接授权一次ECG60工程试验

并确认“只读取B，C保持J5供电及CAN连接作背景”，由其本人负责现场STOP、保全和断电，知情接受J-Link原生连接/关闭的隐式副作用风险。其更正的当前刺激为L→LA、R→RA、F→RL，正常ECG60/1mV，SKX电池供电。

这是对本次授权来源的明确修订，不是PI独立签署。首个现场冻结版本595c5e21保留原PI信任根None及原禁用卡/21项回归/评测器/采集器；不称B/C电气隔离，不获得PI合同验收资格。C供电及CAN作为已获负责人批准的背景，不打开C串口，不操作云端或发B5START。现场失败后仅离线追加一项FLASH_CR只读白名单，见ROOT-CAUSE-AND-RESULT.md，未补跑实板。

## 最小入口与单次性

`b5_m1_owner_once.py`只负责本次签名/现场事实绑定、原子claim及父/worker调度，复用原 `capture_window`、`watch_worker`、`seal_capture`、`verify_signed_card`、`consume_nonce` 和原BLink。公钥pin及nonce的SHA固定在独立入口，真实私钥只在Host内存存在，签一张卡后释放，不冒用PI身份。只接受M1-E60-R1和OWNER_DIRECT_ECG60_ONCE_20261031，其他run/nonce/PI身份标记拒止。首次父claim后次数不退还，worker只能原子claim一次，不自动重试。

实板前冻结本分支commit/tree、入口/原依赖/DLL、同次B41012制品及历史参考；真实卡在批准的新冷启动事实形成后绑定其SHA并短期签署。源代码和现场卡执行中不修改。停止时不Reset/Go/Flash/重连。

## 本次物理准备与待记录事实

由现场负责人按已采用的冷态规则关闭B/C原开发板J5供电、拔C USB及J-Link电脑端USB，确认板卡及外围全暗至少10s；保持J-Link板端在B、CAN与导联不动，不动屏背J5。随后恢复B/C各原J5供电，再接J-Link电脑端USB；本次C USB保持拔出。不按RESET，不换BOOT跳帽，不调整刺激。两板电源输出不互并。

现场回复实际B上电电脑时间HH:mm:ss及完成状态、C USB已拔、B无USB、J-Link在B、SKX充电USB断开、非人体。独立BOOT epoch来自本次现场冷启动记录，并用原始MCU时间作附加检查；不由目录/nonce虚构物理事实。上述步骤需由人完成并报告后才能形成实际site/cold记录。

120s门保留：签署/搬运/worker预检均应在新鲜度内完成；不得回填时间。若超时，保持现场NOT_RUN/拒止，不自动再做冷启动或第二场。

## 采集、评价和结果标签

只读B当前身份、完整Flash/options及同次映射，随后一次45s预热+120s评价；原ADC CH1/CH2 250Hz、seq/IRQ/status/flags保留，RESP50只按原seq派生。原120槽/至少118正确有效/每条有效HR 60±2及完整性要求不变。75s预检、165s采集、20s收尾、260s会话、265s监督及原生超时预算不改。

旧评测器正常执行并保留真实退出码，`PI_trust_root_verified=false`、`field_scope_PASS=false`必须如实保留。若原工程数值通过，只能另报OWNER_AUTHORIZED_ECG60_ENGINEERING_METRICS_PASS，不能改写评测器结果或称M1_E60_R1的PI工程验收通过。SDK原生副作用仍UNRESOLVED，Close后态仍UNKNOWN；故障后保存失败而停止，无补跑。

ECG90仅准备既有M0禁用卡，不在本次现场授权。其余23场、C设备控制、三板联动、Flash、RESET/Go与云端均不开放。

## 实际停止结果

父/worker真实退出1，预检G3_B_READ_SCOPE，review真实退出2。身份/full/options比对通过；没有原码采集块和165s窗口，没有ECG60准确性结论。Close返回，关闭后态UNKNOWN。原nonce父/worker均已消耗，私钥未导出且已释放内存引用；没有新的现场卡。用户要求先分析再决定是否重采，最终断电状态未确认。
