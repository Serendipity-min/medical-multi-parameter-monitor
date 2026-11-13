# RR15 源端事实矩阵（A0，仅离线）

结论：**SOURCE_UNKNOWN / ROOT_CAUSE_UNRESOLVED**。两版说明书都在呼吸章节列有心率60bpm，不能将RESP15当作“厂家保证没有QRS”。实际机器在历史RESP15/1.5R/周期30工况下是否携带QRS，仍没有独立端子参考证据。

基线 `eda6e24a8eedcfe0b50416390022db0c187550af`。本矩阵分别标记文档、当时负责人自述、板端采集、A0磁盘复核和未知物理事实。以下“历史”均不构成当前接线/上电许可。

## 来源登记

| ID | 来源与A0处理 | SHA256 / 定位 |
|---|---|---|
| M12 | 用户给定《SKX2000D+说明书.pdf》，12页，629590字节；提取全文，目视P3/P5/P6/P11 | `27fe9e4a37a761ab7df939bf49693942dbf3e5692f09e2e10311106053503cc8` |
| M22 | 仓库历史审查所指《操作手册.pdf》，21页、V2.2、1258901字节；A0重新核对原件及P4/P5/P9/P11/P20，目视P20 | `8b264906747e76336e7a7221ab77b76e3697078f794b064e77081e7e56fc48aa` |
| P1 | 历史负责人照片 simulator-and-boards.jpg；A0重开图像并匹配旧登记 | `95fdda225ce2578b798564cc2b69626f4330aa43514a343b4bb85bf22af4395c` |
| P2 | 历史 lead-clips.jpg；A0重开图像并匹配旧登记 | `dc4643bc8c463a1e2b2e81368c70d490c954b613285149c2434b3b3bf408a208` |
| D1 | RESP-SOURCE-MENU-REVIEW-R1.md；旧呼吸工况中仍观察到CH2约120次/分节律的记录 | 本轮完整路径/大小/SHA见 source-review-provenance.json；历史事件，非当前六簇真值 |
| D2 | RESP-MANUAL-V22-REVIEW-R1.md、RESP-SOURCE-PATH-REVIEW-R1.md | 既有模块网络/接法审查和历史仪器自述，不等同于实物认证 |
| W1 | 已验收当前R6 RR15原始槽、index及6套波形 | 原始blocks `e8cbb06f2af82b5de373ea289df0a0b9c24ef3010366db28d651308d9804f923`；A0只验hash/阅旧图，不回放 |
| W2 | 已通过当前ECG60原始槽及波形 | blocks `acea4fd11750626ffcfd34a2476d5bb24a48563b7a34770ce1ad6dd63932ab4f`；A0只验hash/阅旧图 |
| C1 | 已验收C因果结果、真实/合成/留出结果 | eda6e24的24项manifest重新复算全部一致；不重跑65/17或语料回放 |

原PDF、旧照片/采集文件没有改写；新增手册渲染/提取仅存本次新EFS目录，不入Git。P1/P2不显示可核定RESP15生效状态的完整菜单，也没有可认证的隔离参考仪器信息。器件/夹头可见不等于端到端线缆通断、极性和RLD稳定性认证。

## 菜单、端子和证据强度

| ID / 项目 | 已知内容与来源 | 状态 | 不能推出 / 当前未知 |
|---|---|---|---|
| F01 / 呼吸章节心率 | M12 P11、M22 P20均写“心率范围：60 bpm” | MANUAL_DOCUMENTED | 说明书列有配套心率；不是已测得本台机器端子QRS，也未解释周期30与心率60控制关系 |
| F02 / 呼吸率 | M12 P5/P11与M22 P11/P20为5–120；默认15 | MANUAL_DOCUMENTED | 历史负责人曾报告最低20，后来R6报告15已设定；分别保留，不回填旧菜单，不操作本机验证 |
| F03 / 幅度1.5R | 范围0.3R–3R，默认1.5R，说明“改变呼吸阻抗大小” | MANUAL_DOCUMENTED | 1.5R实际是峰值/峰峰值/其它定义、误差及实物ΔΩ均UNKNOWN，不自行换算为±1.5Ω或已校准幅值 |
| F04 / 波形周期 | M12 P5为20–120bpm；M22 P11/P20为20–120bpm、默认30 | MANUAL_DOCUMENTED | 不等于呼吸率，不当作载波频率，也不直接认定它控制ECG心率；旧注释里的“阻抗基准心率”等称呼不当作厂家定义 |
| F05 / 窒息0s | M12/M22范围0–120s，M22默认0 | MANUAL_DOCUMENTED | 不是“关闭ECG”；内部0值语义未单独证实，不由此标ECG_ABSENT |
| F06 / 基线阻抗 | 两手册呼吸章节写“1K” | NOMINAL_MANUAL_ONLY | 不是本次实测1kΩ；不等于ECG源端Thevenin输出阻抗，不给探头加载/RLD安全自动背书 |
| F07 / RESP端子对 | M22 P20明确呼吸导联II、RA–LL | MANUAL_DOCUMENTED | M12 P1的II导联ECG定标不能独自代替RESP说明；当前实物兼容/实际动态阻抗仍未独立标定 |
| F08 / ECG一般端子 | M12 P1、M22 P5：I为RA–LA，II为RA–LL，RL为反馈参考 | MANUAL_DOCUMENTED | 不能把RL当保护地或示波器地，不能按颜色把主动RLD接地 |
| F09 / ECG幅值说明 | II导联幅值定标及一般ECG固定幅度有文档说明；两手册I导联“定标”接法文字并不完全相同 | DOCUMENT_VERSION_DIFFERENCE | 不据校准章节重新安排RESP接法；本台版本/固件和幅值校准UNKNOWN |
| F10 / 真正ECG OFF | 查两手册菜单表/呼吸章节，未见明确“RESP继续而ECG关闭”的操作定义 | CAPABILITY_UNKNOWN | “未见说明”不等于不存在；禁止编造HR=0、Lead-Off、开路、关机为同工况无QRS控制 |
| F11 / 参数生效 | M12 P3、M22 P9需在参数层确认；浏览页面不等于输出已按设置改变 | MANUAL_DOCUMENTED | 没有完整当时菜单/按键/输出同步记录就不能确认历史内部模式；不归咎负责人操作 |
| F12 / 普通ECG附带RESP | M12 P6说明普通ECG同步产生20bpm呼吸 | MANUAL_DOCUMENTED | 表明两种分量未必互斥；不是“RESP模式必定只含阻抗”的证明 |
| F13 / R6实际工况报告 | 负责人当时确认RESP15、1.5R、周期30、apnea0，R→RA/L→LL/F→RL/N | HISTORICAL_OWNER_REPORT | 是当时菜单/接线报告，不是独立端子波形或绝对阻抗参考 |
| F14 / CH1与CH2 | 档案CH1有RESP15；CH2经原C产生六簇HR，600/600评价期HR/valid可重现 | ARCHIVED_TARGET_EVIDENCE | BioV2是被测对象，不是独立QRS标注器；HR=0/INVALID同样不等于没有QRS |
| F15 / 工频与耦合 | 已验收分解统计及六套原波形支持干扰/共享扰动假设 | OBSERVATION_NOT_CAUSATION | 不能排除弱QRS，不能因CH2幅度较小或接L到LL就判无QRS |
| F16 / 模块RLD | D2按V2.0原理图说明RLD为主动输出、非差分测量端；线色→模块网是历史设计解释 | DESIGN_DOCUMENTED_PHYSICAL_MAPPING_UNKNOWN | 不能将F绿或RL写成已实测地；本轮不新增线缆测阻，不恢复曾取消的九格测量要求 |
| F17 / 历史参考仪器 | 2026-10-22 D2登记仅有电池万用表DLX-YQ2915 | HISTORICAL_REPORT | 当前仪器清单UNKNOWN；该登记不提供独立QRS原始波形、隔离差分/输入Z/带宽/噪声/同钟能力证明 |
| F18 / 照片 | P1可见电极标记及板；P2可见夹头色标 | ARCHIVED_IMAGE_RECHECKED | 非当前接线照；没有已核定参考仪器型号/校准证书，也不能认证夹头至模块网 |
| F19 / 最新接线记录 | R6 RR时L在LL；后ECG/温度窗口冷改L到LA，收尾负责人确认断电、L留LA | LAST_REPORTED_STATE | 不能用旧LL记录当成未来A1现状。A0不要求移动L、插USB或开机拍照 |
| F20 / 当前电源 | 最近用户报告未上电；A0没有新物理操作 | OWNER_REPORTED_NOT_REMEASURED | 不声称仪表证实无反供电；不拿历史照片亮灯判断当前上电 |

## 独立真值标签规则（供未来A1冻结，当前均未满足）

| 标签 | 必要证据 | 不合格替代 |
|---|---|---|
| ECG_PRESENT_CONFIRMED | 合格独立参考记录同一端子对、已知加载/模式下的原始差分电信号；电压/时基/带宽/噪声性能可核验；冻结QRS形态/节律标注与正控制一致，区别于50/100Hz及RESP；标注不依赖BioV2 HR | 菜单心率60、B报HR、单个尖峰、厂家示意图 |
| ECG_ABSENT_CONFIRMED_WITHIN_BOUNDS | 参考链通过前后正控制及已知无QRS控制/噪声底验证；足够检出力覆盖预注册最小QRS幅度与形态；同端子、同加载、同工况完整记录，在已声明幅值/带宽/时段域内没有QRS；外部参考与B同期时标明确 | 绝对“电信号为零”、DMM读0、开路/关机/Lead-Off、肉眼没看见、算法HR=0 |
| SOURCE_UNKNOWN | 仪器/加载/同步/带宽/检出下限未确认，控制失败，参考冲突，或参考只覆盖未加载/其它时段 | 不以“应当没有ECG”补齐UNKNOWN |

有限测量不能证明所有幅度、所有未来时刻绝对没有QRS。`ECG_ABSENT_CONFIRMED`在分流表中的含义必须携带上述检测域与时间范围；未覆盖能触发被测算法的弱信号，不足以给其输入贴无QRS标签。源端未加载时的阴性也不能自动代表RLD连接后的CH2阴性；新A1不能回溯替代历史六事件当时缺失的参考。
