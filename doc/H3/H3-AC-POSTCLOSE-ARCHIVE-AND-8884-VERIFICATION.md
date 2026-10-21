# H3 A→C 结项后归档与8884验证交接

合同：MPM-H3-005 R1.0。执行日期：2026-10-21（北京时间），唯一执行者Codex。继承 `1878994f57a4c07263b4898d223ba810aa88210a` 的 `H3_AC_FINAL_PASS`，仅非人体MOCK工程链路。**本轮最终裁定为 `H3_AC_POSTCLOSE_ARCHIVED_PARTIAL`（`POSTCLOSE_PARTIAL`）：固件与恢复原件归档/回读完成，8884对外关闭尚缺独立证据；不能升级为全面安全PASS。** 原H3总报告及矩阵逐字节保持不变。

## 1. 开工身份、范围和时间

本地独立工作区沿用原H3工作区，本地分支 `codex/h3-ac-closeout`，只正常推送既有 `dev/h3-nodea-cloud-ai-integration`。本地/远端开工HEAD均为 `1878994f57a4c07263b4898d223ba810aa88210a`，工作树洁净，仓库PRIVATE，目标标签不存在。上一窗口lease的active=false、released和post-push回执明确已停止，但旧write_lease_active残留true；保留旧登记后，同一唯一执行者按本合同重获lease，结束时两个标志均解除。未发现其他引用本工作区的执行写入进程；不声称能证明所有编辑器绝对无人打开。

基线祖先核验：P4…H3为0/60，B…H3为2/60；这是归档前起点的图关系。本轮只添加应用归档、限定attributes与新交接/证据，没有合并或移植运行代码。旧H3 worktree及其未跟踪build保持原样。

| 保护ref | 开始/结束必须保持的SHA |
|---|---|
| P4 | 67f5f57bd82c6e326e9e78ec9540481c80105e5f |
| A | 3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5 |
| B | f8c99433561b2e110c04ba9fb33c30235910a3e9 |
| P6 | 77dd14d1ca761a488956f7a4ebf28cb3174835e4 |
| main | 50699048010c57ba10f8573461844c525b022a07 |

没有打开COM15/J-Link、烧录、复位、重新编译、重新测量、300秒负载、真实豆包调用、正式rollback/activate、服务重启、SG/DNS/ACL变更、PR、merge/rebase/cherry-pick、强推或删branch/tag，也未运行Security Gate。

## 2. PC-0：一次有界验证，保留证据限制

完整回执：[PC0-readonly.json](evidence/postclose-20261021/PC0-readonly.json)。窗口预算240秒；开始/截止的原始UTC见回执，实际结束 **18:57:48 北京时间 / 10:57:48 UTC**。外部每个指定端口仅一次TCP尝试，没有追加其他端口扫描或重试。

- 负责人报告已删除8884规则，并提供当前Edge控制台截图。可见规则为8883/8443/1883/9999/443/3010/8080/80/22及ICMP；未见8884。截图为实例防火墙样式，未显示实例标识、完整关联安全组及IPv6/等价广域规则全集。截图只存私有加密包，Git保留SHA `OWNER_SCREENSHOT_NOT_API_VERIFIED`。实例关联、规则ID及所有生效组独立核查为 **NOT_OBSERVED**，不虚构API身份或规则ID散列。
- 本机无已配置腾讯云只读API；agent-browser只读连接现有浏览器发现5个标签，无腾讯云标签，负责人随后指出页面在Edge。未重启或接管用户Edge以开启调试，不修改任何云规则。
- **服务器18:56:31.882–18:56:33.620北京时间**只读脚本exit **0**：8884监听0，8883监听2（IPv4/IPv6监听行，不是两套生产Broker），临时preview/AI/Backend/Broker均inactive，自有H3 filter/NAT引用0。
- filter为393行，SHA `e6f238e23dece4fe2763aae2c48a482f749a56f632aeac6d31aa1130d7abed1c`；NAT为12行，SHA `96ba2354a7ee95379dbc8c4bc83f5c5d13ccc95d5367d69e3af1e6dec9ed3157`，与H3结束记录一致；历史更早整表差异仍不能归因。
- 8883外部TLS链与主机名校验通过，TLSv1.3，叶证书SHA `a3c4d1284c8f59ccb434b8736f4a1862d1ff3b42e589a26f0108c2a2d854bacd`。
- **8884外部socket connect返回成功**，耗时0.047秒；没有TLS/应用服务证明。该组合检查进程exit **1**原样保留，不能写成“外部8884已确认关闭”。本机DNS为全局地址，但目标路由实际经Mihomo TUN；该代理路径与主机无监听形成矛盾，不能仅凭connect成功断言服务器开放，也不能独立排除外部可达。没有绕过/关闭TUN、增加第二轮端口探测或自动云修复。
- 正式HTTPS index精确匹配 `92e1f44f80d1eec38ef17beb0979dfc1fba8088c6a9aa833ab1de15063535acb`；Backend健康ok/MQTT订阅正常、accepted9092/rejected0/dropped0。鉴权WSS观察10帧，错误令牌关闭1008，AI无令牌POST返回401；AI健康DOUBAO/MONITOR，账本保持9次/6138 Token，**本轮新增真实请求0**。
- 云端观察Gateway/A为ONLINE、B为OFFLINE，PPG STALE、PR/SpO2/NIBP INVALID，均隐藏当前值/样本。这是已有状态的短窗检查，不代表新有源采集或物理现场拆卸核验。

**PC0_PARTIAL_OWNER_EVIDENCE**：主机无8884、8883与正式业务正常；截图支持规则已删，但控制平面关联和不经代理的外部关闭证据缺失。按合同允许继续离线归档。若负责人要把本项升级PASS，后续只需获得真实关联规则证据及可靠外部验证；不在本轮自动重复验证或改规则。

## 3. PC-1：应用、完整Flash与恢复原件双端归档

归档来源是已核验受限原件，未重编：A来自既有运行中应用读回原件，C来自H3结束时正式C计数窗口的application-only读回原件。公开只使用来源别名，完整本机路径在加密索引与外部封存回执。

| 角色/公开文件 | 大小 | SHA256 |
|---|---:|---|
| Node-A `node-a-h3ac-final.bin` | 50084 B | f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6 |
| C 8883 MOCK `gateway-c-h3ac-8883-mock-final.bin` | 43172 B | b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe |

A作用范围仅A自己的sector0–3，起址0x08000000、末址0x0800C3A4（exclusive）；C仅自己的应用sector0–2，末址0x0800A8A4，不含0x0800C000 sector3记录。两者都为STM32F407ZGT6的原始应用BIN，A/C不能对调。A编译证据为ARMCC5.06u7 build960/FromELF；C为GNU Arm14.2 rel1、Cortex-M4 Thumb/EABI5 little-endian/hard-float。只读AXF/ELF头及向量证据保留，A浮点ABI不从未标明的ELF flags作推断。仓库归档提交、设备镜像SHA与云runtime源码SHA是不同身份。

**仅私有加密归档、未入Git的指定原件全部找到并核验：**

| 原件 | 大小 | 已验SHA256 |
|---|---:|---|
| A写后完整Flash | 1MiB | 7c0f68fbd779c61fd7184d687a858d41d154361862af3b1c2a93b32ef67e49a6 |
| A写前完整Flash | 1MiB | 4c2730ebc9a8eab33b1e4d585db7deb47567261b6369165e47ecaf9630f35f3a |
| C正式写后sector0–3 | 64KiB | 49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4 |
| C generation3配置 | 336B | 395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b |

旧C 59229…（8884）、9df43…（未作为本轮正式MOCK使用的LIVE候选）、旧A506423…（49888B）的历史原件/回执保留在私有原窗口中，不覆盖或冒充新镜像。指定必需原件无缺失；本轮没有重新读板。

本机原有GPG2.4.8，OpenPGP AES256+MDC+S2K3，随机恢复密钥只在外部受限文件，未进入argv实际值、Git或两个归档包。Windows/MSYS首次路径参数测试失败，第二次GPG exit2保留；转换为MSYS路径后合成加/解密及实际归档通过，没有降低加密或覆盖原件。Python/暂存检查也保留初始CRLF转换失败说明，不能当BIN身份不匹配；限定属性后重新核对实际Git blob。

**主归档位于物理磁盘1的E:；第二副本位于物理磁盘0的D:。** 两者不是同盘两个文件夹，但仍在同一主机，不能宣称抗整机丢失、勒索或火灾。两份应用均从磁盘重读SHA一致；五份加密文件逐一跨盘比较一致，其中实际解密第二份进行以下核验：

| 私有加密包 | 大小 | SHA256 | 第二盘实际核验 |
|---|---:|---|---|
| local-originals.tar.gpg | 47688308 B | 81d17f1570547dde97a6e7e7063469d50a7d11feb3d1c50512a4cdf87a51f185 | 1030个文件逐项SHA；全部指定Flash/配置与应用身份存在 |
| cloud-recovery.tar.gpg | 55125815 B | 8d7b34b1dbb09aa81301d27c80aa3b832623b67ef01321d2cecaec96abfab52d | 556个文件，两个恢复manifest及全部对象SHA |
| link-and-build-evidence.tar.gpg | 2120689 B | 307771d674552bd80e9e2c3ab194e1dbb3e6e2cbac0d63aa732e9327a839c799 | 101个AXF/MAP/ELF与构建回执文件 |

另有两个加密inventory索引，两盘文件字节/SHA均一致。解密核验通过流在内存完成，没有落盘新的明文完整Flash/sector3/云恢复包，也没有重新生成应用BIN。当前已有私有窗口原件未移动/删除/覆盖。

云恢复包以只读SSH/GNU tar（含owner/mode/ACL/xattr/链接语义）直接流入本机GPG，SSH/tar、加密及解密退出均0；传输小于1GiB，服务器未创建临时压缩文件。两份schema2 manifest SHA为 `53e1aec5021e6a0fba8b7e3c8b7df53346f9f8e2bce9c7aa0a64382c503ffed3`、`61f656e835a3689e89f0617d766b5529f7b9a8d9543050fcd83f824fd14145dc`，第二盘解密后逐对象比对。实际tar物理链接项0，原恢复对象中的链接关系仍由已验manifest保存，不虚构重新物理恢复测试。原正式计划、Backend/AI环境SHA也再次匹配。

两份应用的限定内容复核仅对本轮批准文件：从外部原件在内存加载网络/身份字段、访问令牌及UID比对，命中0；私钥/provider-key通用标识命中0。没有把秘密值放入restricted_patterns、脚本或防泄漏名单，不做全项目Security Gate，也不把“未发现”扩张为全部安全证明。

恢复密钥的实际外部受限文件和两个归档根路径随最终私有封存元数据交给负责人；**负责人线下离线保管尚待签收**，未声称已完成异地保管。以后恢复都需新的设备身份、双读、精确范围与授权，本合同不自动授予烧录。PC1字节/加密恢复性通过，密钥线下保管责任继续由负责人完成。

## 4. PC-2：私仓镜像回读与标签冻结

第一归档提交 **e4ee91c9ba7ca99ac2cc2aadb7b0bbc92e945185** 已正常SSH fast-forward推送。全新独立bare仓库只取单个提交树（depth1/blob按需），按Git原始blob bytes读回，未使用PowerShell文本重定向：

| 应用 | Git blob对象SHA | 远端字节/SHA |
|---|---|---|
| Node-A | 2b94eeee4b7bf2f610a435ccf040620035484739 | 50084 B / f59b76ef…完全匹配 |
| C 8883 MOCK | 89effa0ecd72ff07268ef45aad03eb8589a5e6a9 | 43172 B / b9b25b18…完全匹配 |

README/manifest/SHA256SUMS也逐字节回读匹配，仓库再次确认PRIVATE。回读实际11:12:00–11:12:56 UTC，exit0，完整两个SHA及所有文件对象见 [remote-artifact-verification.json](evidence/postclose-20261021/remote-artifact-verification.json)。两份BIN通过精确路径git add -f入索引，其他文件按显式清单正常add；从未强制添加整个build或evidence目录。归档包禁用text/filter，两个BIN额外binary属性；新回执-text。根.gitattributes沿用Git文本规范化，单独记录WT/Git两类SHA，不混作BIN变换。

本次新增/修改清单总计11项：

1. `.gitattributes`（仅本归档路径与新回执的字节策略）。
2. `artifacts/h3-ac-mock-eng-20261021/node-a-h3ac-final.bin`。
3. `artifacts/h3-ac-mock-eng-20261021/gateway-c-h3ac-8883-mock-final.bin`。
4. 同目录 `SHA256SUMS.txt`。
5. 同目录 `firmware-manifest.json`。
6. 同目录 `README.md`。
7. `doc/H3/evidence/postclose-20261021/PC0-readonly.json`。
8. 同目录 `PC1-archives.json`。
9. 同目录 `baseline.json`。
10. 同目录 `remote-artifact-verification.json`。
11. 本唯一新交接报告。

第一阶段9项全部暂存Git blob/路径/字节/SHA审计通过，第二阶段只加入本报告与远端回执。所有暂存条目按允许集合核对，已加载机密的限定比对命中0；完整Flash、sector3、凭据、env、云恢复包、UID和原始私有日志均不在新增清单中。

最终注释标签固定名 **`h3-ac-mock-eng-20261021-r1`**。先推送包含本文的最终冻结提交，再从远端再次取回全部应用与本文，全部一致后才创建/正常推送annotated tag；不是lightweight，不指向旧1878994f，不发布Release，不覆盖已有标签。标签message含H3工程PASS的非人体限定、完整A/C SHA、P4/B未合并及本轮PARTIAL边界。

**自引用身份说明：**最终包含本文的commit SHA和annotated tag object SHA只能在本文提交及标签创建后取得，不能伪造写成已存在。实际最终HEAD、tag对象SHA与peeled commit SHA分别写入外部受限 `POSTCLOSE-DELIVERY-RECEIPT.json` 并在最终答复给出。本文可通过下列真实Git命令复核（tag和commit是不同对象）：

```text
git rev-parse refs/tags/h3-ac-mock-eng-20261021-r1
git rev-parse refs/tags/h3-ac-mock-eng-20261021-r1^{}
git ls-remote --tags origin refs/tags/h3-ac-mock-eng-20261021-r1 refs/tags/h3-ac-mock-eng-20261021-r1^{}
```

该最终远端核验必须再确认tag指向包含两份BIN、清单、README和本报告的同一冻结commit，不能用push exit0替代实际对象/字节一致。若任何最终回读或标签步骤失败，以封存回执FAIL/NOT_COMPLETE为准，停止，不强推隐藏。

## 5. PC-3：分支与Node-B交接边界

P4/A/B/P6/main保持第1节身份；H3与B分支保留。本次不合并P4、不删任何branch/tag、不创建PR。H3冻结后释放单写入者lease、停止后续H3开发，不卸载依赖，不删除旧工作区或build，不关闭用户Chrome/Edge。只读浏览器任务只断开自己的控制进程，不发Browser.close关闭用户标签。

Node-B只在新独立工作区按新授权推进。B-H0/H1/H2（ECG/HR/RESP/RR源质量与算法）通过后，PI再裁定从P4建立 `integration/p4-h3-nodeb`，审核合入本冻结tag和B当时冻结提交的冲突、Node-ID/PDO/Backend/Web路由。三板物理验收与A/C回归通过后才考虑回合P4，分支删除另行批准，不凭祖先快进关系提前改P4。

现场A是否已移除/全部下电：**本轮NOT_OBSERVED，无新OWNER_REPORTED确认**；最后一次负责人反馈仍是A/C独立运行，PC0云端A ONLINE支持已有连接，但不能据此伪称实物检查。负责人签收归档后可先停模拟输入，A/C全部断电，再拆CANH/CANL/GND并贴签；不带电拆线。A标签应注明NODE-A/H3-AC-MOCK-20261021/50084B/f59b76ef…/BOOT0/1=GND。若C没有演示需求也一并断电封存；保留原J5/双屏/供电及线序参考。

再次接B+C或三板时重新核对500kbps、两端各一个120Ω（共两个，断电H-L约60Ω）与参考地，不把三板各一个120Ω直接并联，也不互接不同板电源。A移除后A OFFLINE及SpO2/PR/NIBP无当前值是预期，禁止填模拟数据维持在线。C缺CAN peer出现合理NO_ACK不能直接判新网络故障。正式8883继续需要原2.4GHz路由器/WAN、授时和证书；云服务仍在运行，未来使用可能继续占用云资源/模型费用，本轮无新增模型请求。

## 6. 完整残留风险与最终裁定

| Gate | 裁定 |
|---|---|
| PC-0 | **PARTIAL_OWNER_EVIDENCE**：截图支持删除；关联/全规则API未观察；经TUN的8884 connect成功与无监听矛盾，外部关闭不可独立确认；8883/TLS/业务正常 |
| PC-1 | **ARCHIVE_INTEGRITY_PASS**：两应用精确、全部指定原件找到、跨物理磁盘加密与第二份解密校验；负责人离线密钥签收待完成 |
| PC-2 | 两BIN/清单/说明已远端精确回读；最终报告提交/tag的生成后实际身份以远端ref与封存回执为准，不预写未知SHA |
| PC-3 | 保护分支不改、H3/B保留、Node-B准入与下电交接说明完成 |
| 本轮整体 | **H3_AC_POSTCLOSE_ARCHIVED_PARTIAL / POSTCLOSE_PARTIAL**，不改变原H3_AC_FINAL_PASS的限定范围 |

仍保留：原网络根因未唯一定位；串口ROM握手失败；C FLASH_CR完整工具修复仅Host验证而非又一次整套实板重刷；PPG连续359.701s但三流共同有效仅203.832s；历史filter整表差异不可归因；模拟源型号/校准与临床精度未验证；原实际rollback仅Nginx/新应用单元，不是C/ACL/全服务器/全防火墙物理全量恢复。新8884状态是负责人截图+主机无监听+代理路径外部探测不确定，不能声称全部安全验收已过。

实际原始回执/加密包与恢复密钥位置由外部受限封存元数据交给负责人；Git只含本文、批准的两份应用与脱敏证据。归档后停止H3工作，等待负责人确认归档结果。未请求重开H3或Node-B现场窗口。
