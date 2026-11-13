# P4 合流、Vite 升级与 clang 分类交付报告

日期：2026-09-21；执行者：Codex。仅完成本轮两项独立任务；未开始 A/B、RR 算法、真三板、Flash、24h、RC、Docker/ZAP、release、部署或人体数据验收。

## 1. Git 合流及 PR #3

- 安全整改旧 HEAD：`2fed4a290ef8c469a84fd8468d3ba2e9cb5ba4cd`。
- P4 的 Security Gate 接入提交：`bb2bc94f43337e6ff229ba1391c22140bbf4fb5a`，保留原提交，不 amend、不重写。
- 将 P4 合入修复分支的 merge：`254a0a08351bafc379f83c568769c5b510995f42`，无文件冲突。
- [PR #3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/3) 合并前状态为 MERGEABLE / CLEAN，检查全部通过；使用 match-head-commit 防止合并未经核对的新 HEAD。
- [PR CI 35522530275](https://github.com/Serendipity-min/medical-multi-parameter-monitor/actions/runs/35522530275) 通过；并发取消的 push 检查通过 [35522528892 的重跑](https://github.com/Serendipity-min/medical-multi-parameter-monitor/actions/runs/35522528892) 恢复为成功。
- 已按本轮授权 merge PR #3 → P4。新的 P4 精确 SHA：`44e3bdf74c1d503abefc992406700ea719ab346c`。没有修改 main。

## 2. 新 P4 的精确 SHA 门禁

目标 SHA 为 `44e3bdf74c1d503abefc992406700ea719ab346c`，profile 为 medical-monitor；pr 的 base 为合并前 P4 `bb2bc94f43337e6ff229ba1391c22140bbf4fb5a`。

| 模式 | 权威记录目录名 | 结果 |
|---|---|---|
| doctor | `doctor-2026-09-20T163105.021596_0000-08d11e` | PASS / 0，dirty=false |
| quick | `quick-2026-09-20T163147.471568_0000-cfb7d8` | FAIL / 1，dirty=false；固定回归全部成功，工具锁摘要触发 Gitleaks |
| pr | `pr-2026-09-20T163207.084339_0000-4aae60` | FAIL / 1，dirty=false；Vite HIGH 及一次 Backend 测试失败，另有 clang 人工复核与 ARM 覆盖缺口 |

以上目录及 raw 均保留在仓库外的既定 Security Gate 输出根。本报告和机器可读交付摘要只记录脱敏结论。日期名为 UTC，执行记录按本地日期归档。

首轮 Windows 入口转 WSL 时，WSL Git 未使用 Windows 的 CRLF 规则，产生 dirty=true；Windows Git 当时干净。仅对后续命令设置 `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=core.autocrlf`、`GIT_CONFIG_VALUE_0=true`，WSL Git 即返回干净树。没有更改全局配置、索引、文件内容或 Gate 源码。首轮记录保留但不作为干净树验收：doctor `162541...0269e6`、quick `162633...a3c9b4`、pr `162937...343d9d`。

quick 命中 `tools/security_gate/toolchain.lock.json:75` 的 `generic-api-key`，ID `46c506adf538844789e78222`。结合 `bootstrap.py` 的安装报告读取路径，命中字段实际是 `tools.pip-audit.download_hashes.pip_api` 中的公开下载包 SHA-256，不是登录凭据。没有添加 allowlist 或风险接受项，原始 FAIL 保留。pr 的 Gitleaks 只检查所选 commit 范围，与 quick 的工作树范围不同，pr 不命中该项不能证明该项已被工具修复。

干净树 pr 的 `test_browser_auth_and_no_device_ingest` 在 TestClient WebSocket 上下文退出时发生 `concurrent.futures.CancelledError`，本次 27 passed / 1 failed。其他基线执行曾 28 passed；同一环境下单项复核随后 1 passed。没有改写 Backend 或测试以掩盖失败，也不把单项重跑通过当作根因已修复。升级后全量门禁结果见下节，首次失败证据保留。

## 3. 独立 Vite 修复

从上述新 P4 创建 `codex/p4-vite-clang-triage`。依赖修复独立提交：`45eb5c046da47911c451e4cd17d624e3c9a4a669`。

仅修改 `cloud/web/package.json` 和 `cloud/web/package-lock.json`：Vite 7.3.1 → 精确 7.3.5，以及对应 tarball URL / integrity。未改变其他依赖版本、UI 源码、业务协议或安全工具配置。

- `npm ci --no-audit --no-fund`：成功。
- `npm run build`：TypeScript 与 Vite 7.3.5 生产构建成功，12 modules。
- `npm ls vite esbuild --depth=1`：Vite 7.3.5，esbuild 0.27.7（原锁版本保持不变）。
- 本机 agent-browser：升级前 16 / 16，升级后 16 / 16。
- UI 回归复用实际 Backend / Hub 和既有 MOCK 载荷辅助函数，直接向 Hub 注入合成数据；使用构建后的静态页面及 loopback WebSocket。没有 MQTT Broker、真实设备、生产服务器、患者数据或公网安全请求。
- 覆盖四模块、ECG/RESP/RR 绘制、血氧及血压、INVALID 清空、A/B 掉线隔离、REPLAY 与实时分离、静默过期、重连、网关切换、全屏、1920×1080 与移动端布局。保留 `browser-acceptance.json`；详细截图和临时测试工具留在仓库外。

升级后对 `45eb5c046da47911c451e4cd17d624e3c9a4a669` 的干净树运行 `security-gate pr`，base 为 `44e3bdf74c1d503abefc992406700ea719ab346c`：

记录：`pr-2026-09-20T163657.405546_0000-849030`。**CONDITIONAL PASS，Gate exit_code=2，dirty=false，blockers=[]，mandatory tools 全部 OK。** 没有改动 Gate 判定或降低策略。

| 项目 | 升级前 | 升级后 |
|---|---|---|
| Trivy | Vite 相关 3 HIGH / 2 MEDIUM，另有 esbuild LOW | 仅 esbuild 1 LOW，Vite 原有命中消失 |
| npm audit | Vite HIGH + esbuild LOW | 仅 esbuild LOW |
| Backend | 干净树基线一次 27 passed / 1 failed | 完整回归 28 passed；保留早先失败证据 |
| 固定 sanitizer / CANopen / canonical / Paho integrity / Web | 完成，详见各 run | 全部通过 |
| clang-tidy | 27 MEDIUM 提示 | 同一组 27 项，ID 集合一致；分类未写入忽略规则 |

残留依赖项为 esbuild 0.27.7 的 `GHSA-g7r4-m6w7-qqqr`，工具标 LOW、修复版本 0.28.1。本轮仅按授权升级 Vite，不以跨版本 override 代替独立依赖决策，也未将 LOW 项记为已修复。

CONDITIONAL 的维护/覆盖事项仍包括 27 项 clang 提示和 ARM 构建覆盖边界：WSL optional gateway-build 为 COVERAGE_GAP，10 个 ARM 编译单元缺少 host 编译命令，另保留 profile 的 ARM 说明。不能解释为 release 或真实数据准出。

## 4. clang-tidy 27 项逐项分类

见 [27 项逐项分类](P4_clang-tidy_27项逐项分类_2026-09-21.md) 与同名 JSON。原始批次和当前 P4 涉及的六个 C 源文件一致。

- 18 项缓冲 API 提示：逐项核对对象大小、调用者、格式常量、截断判断，分类为当前调用上下文不成立的通用告警（FP_CONTEXT）。
- 8 项易混参数：没有确认实参交换，保留为维护复核；部分签名属于 CANopenNode ABI，不能机械调换。
- 1 项多级指针转换：memset 只按字节初始化 ports 数组；保留空指针字节表示的跨 ABI 可移植性复核事项。

所有 27 项均有 Finding ID、位置、依据和后续建议。没有自动修复、NOLINT、baseline 追加或 accepted-findings 更新。Codex 分类不是 P 的风险接受签字；门禁仍保留原提示。

## 5. 独立的安全工具基础设施待办

本轮没有修改 Security Gate 安装/导出副本、配置或模板。以下仅记录，不混入医疗项目修复提交：

1. `toolchain.lock.json` 下载摘要触发 Gitleaks 的误报，需在集中工具库用有证据、范围受限的方式另行处理，不能整个文件或仓库排除。
2. `.github/workflows/security-gate.yml` 在 [Run 35522528378](https://github.com/Serendipity-min/medical-multi-parameter-monitor/actions/runs/35522528378) 未创建 job 即失败。静态定位到 `jobs.gate.env` 使用 `runner.temp`；该位置不支持 runner context，step 级 env 才支持，见 [GitHub 官方 context availability](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability)。这是对配置错误原因的定位，未修改集中模板或项目副本。它与已通过的 PR #3 test-and-build 是不同工作流。
3. Windows / WSL Git 换行语义应由工具入口显式说明；本轮用命令级设置获得干净树，不改安装基础设施。
4. WSL profile 的 optional Gateway ARM 构建及 10 个 ARM 编译单元仍有覆盖缺口；host C 回归不冒充 ARM 或真机验收。
5. 记录 Backend WebSocket 测试的间歇退出异常，后续用独立任务调查，不因 Vite 升级改变而自动宣布修复。

## 6. 交付与边界

医疗项目修复与分类文档放在专用分支；独立于已保留的 Security Gate 接入提交。PR #3 已按授权合并；Vite/clang 新 PR 供审核，本轮不把它直接合入 P4。风险接受、最终 RC、真实数据和 DAST 均未执行。

回滚 Vite 可在新提交中 revert `45eb5c0` 并重跑 npm/build/UI；不 reset 已推送历史，不改 P4 既有安全修复，不恢复原始扫描产物。
