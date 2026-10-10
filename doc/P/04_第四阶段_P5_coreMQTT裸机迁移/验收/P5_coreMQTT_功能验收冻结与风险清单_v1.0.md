# P5 coreMQTT 功能验收冻结与风险清单 v1.0

日期：2026-10-09（Asia/Shanghai）。依据[最终审查合同](../合同/P5_coreMQTT功能验收_SecurityGate与PR6最终审查执行合同_v1.0.md)，本轮仅完成F0/F1/G0。G1扫描、配置补丁应用、合并及P6未授权，历史原件保留。

## 1. F0与冻结结论

`P5_FUNCTIONAL_VERDICT=PASS_WITH_LIMITATIONS`；`P5_FINAL_MERGE_STATUS=HOLD`。coreMQTT裸机迁移的功能证据成立，不能由H16仪器缺口推断功能失败；功能成立也不代表安全门或合并已准出。

洁净工作区 `E:/medical-monitor-p5/P5-final-review`，分支P5-coremqtt-baremetal，F0 HEAD `de36cc1b9bbe7c98757d6fffb4c87b32ffde8f53`；P4 `8dee339491cfd4edc468bb9451511d421f26db5e`，main `50699048010c57ba10f8573461844c525b022a07`。诊断分支 `38ccef7fd7e265b848880dd2ca1015ca3f3a7099` 只读归档，没有merge/cherry-pick其代码。原诊断工作区三份已知用户文档原地保留。

生产输入与最后受测源码 `e598fc63719acdf49a99c6da46c656dc8c607782` 的Git对象相同。活动客户端coreMQTT v2.3.1、MIT、上游 `2beef04725328923e05e576b884212d53ec97af7`；供应商9文件原字节核验通过。MQTT3.1.1、裸机、publish-only，无FreeRTOS/MQTT5迁移。

| 生产产物 | 本地实际字节 | SHA-256 |
|---|---:|---|
| P5功能BIN | 35552 | fd81076b9b34ad0a8f4ee35c08cd7ea14704f6d7b04620741cdf083c9c6c1069 |
| P5功能ELF | 66796 | c5eb2278669fe520c391c0e4dc69a13539686d724bdff6724cc4cc041e3f9a35 |
| P4对照BIN | 30180 | 5fd386b8bfe0bcf54d4f53ffb1ec6483d086a1c3287b4fe6c37a3ddeacd90547 |

这些为生产功能固件，未用H16诊断BIN替代，本轮没有重建/部署固件。机器清单：[p5-functional-freeze.json](evidence/p5-functional-freeze.json)。

## 2. 功能证据及复核等级

| 条目 | 本轮冻结结果 | 证据/限定 |
|---|---|---|
| 活动客户端/来源 | PASS，9文件与active白名单 | [upstream.json](../../../../gateway/third_party/coreMQTT/upstream.json)；本轮verifier已执行 |
| C普通功能/断言 | **42/42本轮复测PASS**＝38客户端/传输＋4 Host assert | [e598 P0摘要](evidence/p0-host-summary.json)和本轮ignored build/result.json；不把诊断70项加进分母 |
| 来源/构建契约 | **6/6本轮复测PASS** | 来源、manifest、额外文件、glob和白名单变异被普通用例拒绝 |
| PUBACK后Router ACK | PASS，真实源码及固定普通用例 | MQTT_Publish后继续有界ProcessLoop，仅pending ID合法PUBACK才使QoS1成功；错号/迟到/重复/跨会话/半包/丢ACK覆盖 |
| 隔离Mosquitto | **30/30历史PASS、输入/日志SHA重新匹配** | [隔离报告](P5_P0_隔离Mosquitto集成验证报告_v1.0.md)：Will/retain/保活/异常断连/P4-P5等价；本轮未重跑Broker |
| CAN/Router | **本轮12/11普通复测PASS** | 源码与505be8a历史执行源相同；固定溢出边界测试不等于现场无丢帧 |
| Canonical/Backend | **本轮41条/28项PASS** | RR INVALID、synthetic=true、Snapshot v1；旧log引用位置未找到，原摘要保留，不能冒充旧log已复核 |
| F407 B01 | 历史PASS，应用回读重新核对 | [生产真机报告](P5_真机合成Smoke与WiFi恢复报告_20261008.md)：双合成节点silent-loopback→ESP AT/TLS→Broker→Backend |
| Wi-Fi B02 | 历史PASS，成功窗口原件可访问 | OFFLINE→ONLINE、LIVE状态先于REPLAY；历史lost=203、首次25s观察超时保留 |
| 全片恢复B04 | 历史两窗口双读/恢复字节一致、应用回读匹配生产BIN | 原1MiB SHA 852d7618f8fc46c80cbe035ebd41f4e21e4d5a76a26cf10a39e0600f7a89ffb8；DMA_ADC恢复，不等于冷上电 |
| 项目assert | 4项Host PASS已包含在42项，ARM历史0告警/原log匹配 | [处置报告](P5_P0_assert只读复核与处置报告_v1.0.md)；真实故障注入NOT_RUN |
| ARM/静态资源 | 历史ARM PASS、当前ELF/BIN及4份P0原log SHA匹配 | RAM P4/P5 120160/120208 B，+48 B；24KiB Heap/8KiB Stack，不代表高水位 |
| H16 | **LIMITED / NOT_GRANTED** | 诊断38ccef7只读引用：Heap均9400 B，名义单次重连5.160445/5.002045 s，M03 PARTIAL、M04 BLOCKED；不作完整准出 |
| CI/托管App | F0核验de36cc1普通PR CI SUCCESS、托管Semgrep SUCCESS | 同SHA另有push CI并发CANCELLED；平台结果不是统一Gate |

P0普通/隔离输入保留副本分别22/22、9/9原始字节SHA匹配。新签出分别12/4个文件因core.autocrlf成为CRLF，已逐个证明仅行尾变化，测试提交与当前Git blob相同。清单同时记录原始SHA、签出SHA、Git blob SHA，不伪称签出原字节全部相同。新42项用例实际编译新签出输入并通过。

H16报告/JSON只以精确诊断Git提交及文件SHA引用，不复制诊断分支全量材料；不改变B01/B02/B04生产固件指纹。旧NOT_RUN/失败报告不改写。

## 3. 风险及例外请求

| 项目 | 事实/风险 | 请求、所有者与有效范围 |
|---|---|---|
| H16 M01/M02/M03/M04/M06 | 完成调用/匹配服务限定观测；纯CPU不可比；Stack BLOCKED；单次重连未做原20%评审 | **RISK_ACCEPTANCE_PENDING**，项目负责人决定工程样机是否带限制准出；无自动豁免 |
| M07/缓存 | 32帧有界缓存lost=203；新诊断342/325另存；未证明无损/排空 | 保留限制，不冒充持久缓存或无损机制 |
| B03生产Broker故障 | NOT_RUN；已有隔离30/30与真机Wi-Fi/LWT证据 | **WAIVER_REQUESTED**，项目负责人签字后才可WAIVED_FOR_P5；本轮不触发故障 |
| 冷上电 | NOT_RUN；reset运行/全片恢复不替代真实断电 | **RISK_ACCEPTANCE_PENDING**，未接受则最终HOLD；以后独立硬件窗口 |
| assert真机路径 | Host/ELF成立，真实故障UART/停机未主动触发 | **RISK_ACCEPTANCE_PENDING**，仅未来独立受控诊断窗口 |
| 真A/B/临床/24h | 当前合成silent-loopback，不代表三板/人体/医疗报警准出 | 独立阶段所有者负责，不把P6 24h计成P5已通过 |
| Gate/合并 | 活动覆盖有缺口、未实扫、R0未完成 | 项目负责人批准准确SHA/模式/补丁后才G1；PR保持Draft，P6不开始 |

旧合同H16要求仍可追溯；功能与增强性能分级是本合同提案，最终接受须负责人书面裁定。

## 4. G0覆盖矩阵与前置问题

| 工具/检查 | 当前真实配置 | 未应用方案/限制 |
|---|---|---|
| mandatory完整性 | Paho verifier还检查已被替换的Paho构建白名单 | 改coreMQTT 9文件＋6项契约；旧源/PATCH-01～03/审计与脚本保留 |
| mandatory sanitizer | 旧Paho run_security_regression.py | 复用42项P5夹具、真实core源编译ASan/UBSan，显式双开关；**ACTIVE_COREMQTT_SANITIZER_COVERAGE_GAP仍未闭合** |
| Gateway/CAN/Backend | CAN/Backend已有，ARM builder optional | 42项P5 Host构建/测试mandatory；ARM builder改mandatory但环境待对齐，不以旧BIN冒充Gate构建 |
| Semgrep Pro | 一方根，不含core vendor；include/no-git-ignore，排除node_modules/.venv/tools安全测试 | 加coreMQTT/source；具体语言、扫描文件及parse errors要G1核验，本轮NOT_RUN |
| clang-tidy | compile_capture仅CAN；多个MQTT/ESP TU没捕获 | 同时捕获P5＋CAN，并选core 3个C；first_party_c在旧adapter中是选择器，不改变vendor归属。main/platform/heap与ESP ARM-only仍**COVERAGE_GAP** |
| Trivy | 全快照fs vuln/secret/misconfig/license，排除.git/node_modules | C vendor漏洞库存/SBOM识别未知；不能以零findings证明coreMQTT CVE全覆盖 |
| Gitleaks pr | P4精确base→目标HEAD Git历史，redact=100、禁源码allow | 当前P5范围，不扫描未合流诊断分支全历史；实际结果待G1 |
| pip/npm audit | Backend锁与cloud/web；npm ci禁安装脚本 | 不是C vendor审计；锁定工程依赖安装及元数据网络范围须G1明确 |
| 工具/策略/CI | 固定锁/规则/接受策略；workflow仅dispatch，旧jobs=[]未启动 | 不改核心/锁/接受项/CI；不doctor、扫描、安装升级或取凭据 |

原选择器还未覆盖canopen/stm32/bxcan_loopback.c及CANopenNode全部vendor TU，保留静态覆盖缺口；普通编译/来源验证不是安全扫描。本节是配置/配方审计，实际扫描覆盖仍NOT_RUN。

G1前必须明确：

1. Gate源码快照无.git；原生HERA-C3须从批准HEAD注入同一40位`P5_COMMIT`，不能造快照提交冒充源身份。
2. Windows worktree的.git指针不能直接供Linux Git使用；需获准取固定SHA的POSIX洁净签出，不动原F0区。
3. 测试解释器按repo路径哈希隔离，当前未检查/准备新目标解释器；doctor工具通过不证明项目pytest环境已准备。缺失按TOOL_ERROR，准备依赖需明确授权，不拷贝venv或擅自升级扫描器。
4. 原ARM builder指向Windows GCC/SDK，HERA-C3原生执行方式未对齐。批准后解决路径，否则报告TOOL_ERROR，不能降mandatory或用旧摘要替代。
5. Pro认证/版本运行时未核验，不读取认证/代理；仅获G1许可后doctor。建议doctor+pr工程样机范围，不含release/ZAP/公共目标/Broker/设备。

## 5. P5_G0_AUTH_REQUEST

只提议三文件：`.security-gate.json`、`tools/security_gate/profiles/medical-monitor.json`、`gateway/mqtt/tests/run_p5_host_tests.py`。

候选profile（UTF8/LF）SHA256：`1d6194eaaecc7e8837efc1979ba33d4b2300bc9a4d1d352c750131d8dd9354e2`；完整未应用Patch SHA256：`d0c3bb5a3b06e726a49e23d8af67e7462ee185f7359ff3f3543d3fe728715a04`。忽略目录为 `gateway/mqtt/build/p5-final-f0-f1-g0-20261009/`，附录为同一完整Diff。JSON、Python AST/语法编译（未执行）与git apply --check通过；三个活动文件原SHA不变。

先请求批准仅这些配置/测试入口补丁的应用范围。获准后普通验证并提交，再报告新的准确40位HEAD；正式Gate须对变更后SHA另行明确授权，不能沿用本轮文档SHA。推荐base=P4 `8dee339491cfd4edc468bb9451511d421f26db5e`、既有原生HERA-C3、doctor+pr，无target/real-data/release/自动合并。环境/ARM缺口须一并明确，不后台安装工具试撞绿灯。

后续审批示意命令（本轮未运行）：`P5_COMMIT=<批准SHA> python3 tools/security_gate/gate.py pr --repo <批准POSIX签出> --base 8dee339491cfd4edc468bb9451511d421f26db5e --authorize`。示意、Patch显式开关和本报告建议均不是G1授权。

## 6. 交接与停止

F0 GO；F1 **PASS_WITH_LIMITATIONS**；G0 **GAP_IDENTIFIED / PATCH_READY_NOT_APPLIED**。Gate及真实core sanitizer未运行，风险/豁免未签字，PR #6 OPEN/DRAFT，R0/R1/P6 HOLD。文档提交后以GitHub最新HEAD交接；本轮仅4个允许文档路径，没有Gate代码改动。到此停止等待授权。

## 附录：完整未应用Diff

旧Paho两任务由活动core任务替换，历史源/证据/脚本未删除。普通runner默认行为不变；安全模式双开关、同42项固定夹具、真实官方源、有限时间。首次安全回归只能在G1许可后运行。

```diff
--- a/.security-gate.json
+++ b/.security-gate.json
@@ -1,20 +1,23 @@
 {
   "name": "medical-monitor",
-  "source_roots": ["cloud/backend", "cloud/web/src", "gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src"],
+  "source_roots": ["cloud/backend", "cloud/web/src", "gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src", "gateway/third_party/coreMQTT/source"],
   "requirements": ["cloud/backend/requirements.lock"],
   "npm_roots": ["cloud/web"],
-  "first_party_c": ["gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src"],
+  "first_party_c": ["gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src", "gateway/third_party/coreMQTT/source"],
   "github_repository": "Serendipity-min/medical-multi-parameter-monitor",
-  "compile_capture": ["{python}", "gateway/canopen/build_host.py"],
+  "compile_capture": ["{python}", "gateway/mqtt/tests/run_p5_host_tests.py", "--with-can-capture"],
   "commands": [
-    {"name": "sanitizer-fixed", "argv": ["{python}", "gateway/canopen/run_security_regression.py"], "required_file": "gateway/canopen/run_security_regression.py", "modes": ["quick", "pr", "release"], "mandatory": true},
+    {"name": "p5-coremqtt-asan-ubsan", "argv": ["{python}", "gateway/mqtt/tests/run_p5_host_tests.py", "--asan-ubsan", "--authorize-sanitizers"], "required_file": "gateway/mqtt/tests/run_p5_host_tests.py", "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "backend-tests", "argv": ["{python}", "-m", "pytest", "cloud/backend/tests", "-q", "-p", "no:cacheprovider"], "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "canopen-host-tests", "argv": ["{python}", "gateway/canopen/build_host.py"], "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "c-backend-test", "argv": ["{python}", "gateway/canopen/tools/check_canonical.py"], "modes": ["pr", "release"], "mandatory": true},
-    {"name": "paho-integrity", "argv": ["{python}", "gateway/third_party/verify_paho_integrity.py"], "required_file": "gateway/third_party/verify_paho_integrity.py", "modes": ["pr", "release"], "mandatory": true},
+    {"name": "coremqtt-integrity", "argv": ["{python}", "gateway/third_party/verify_coremqtt_integrity.py"], "required_file": "gateway/third_party/verify_coremqtt_integrity.py", "modes": ["quick", "pr", "release"], "mandatory": true},
+    {"name": "p5-source-contract-tests", "argv": ["{python}", "-m", "unittest", "discover", "-s", "gateway/mqtt/tests", "-p", "test_p5_integrity.py"], "required_file": "gateway/mqtt/tests/test_p5_integrity.py", "modes": ["quick", "pr", "release"], "mandatory": true},
+    {"name": "p5-coremqtt-ordinary", "argv": ["{python}", "gateway/mqtt/tests/run_p5_host_tests.py"], "required_file": "gateway/mqtt/tests/run_p5_host_tests.py", "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "web-build", "argv": ["npm", "run", "build"], "cwd": "cloud/web", "modes": ["quick", "pr", "release"], "mandatory": true},
-    {"name": "gateway-build", "argv": ["{python}", "gateway/mqtt/build.py"], "modes": ["pr", "release"], "mandatory": false}
+    {"name": "gateway-build", "argv": ["{python}", "gateway/mqtt/build.py"], "modes": ["pr", "release"], "mandatory": true}
   ],
+  "historical_evidence": ["gateway/third_party/paho-embedded-c/PATCHES.md", "gateway/third_party/paho-embedded-c/upstream.json", "gateway/third_party/paho-embedded-c/patched.json", "gateway/canopen/run_security_regression.py"],
   "coverage_notes": ["ARM-only units absent from host compile database are explicit coverage gaps; no compiler flags are discarded"],
   "manual_checklist": ["browser_no_mqtt", "gateway_publish_only", "no_remote_nibp", "mock_live_replay_isolated", "stale_offline_no_old_value", "mqtt_no_anonymous", "tls_verification", "secrets_outside_git", "backend_internal", "nginx_broker_boundaries", "real_data_identity", "retention_policy", "no_physiological_payload_logs", "backup_permissions", "dependency_provenance", "residual_risk_owner"],
   "real_data_checklist": ["no_shared_test_token", "revocable_identity_or_vpn", "https_wss", "redacted_access_logs", "retention_deletion", "backup_permissions", "mock_live_isolation", "no_dangerous_remote_control"]
--- a/tools/security_gate/profiles/medical-monitor.json
+++ b/tools/security_gate/profiles/medical-monitor.json
@@ -1,20 +1,23 @@
 {
   "name": "medical-monitor",
-  "source_roots": ["cloud/backend", "cloud/web/src", "gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src"],
+  "source_roots": ["cloud/backend", "cloud/web/src", "gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src", "gateway/third_party/coreMQTT/source"],
   "requirements": ["cloud/backend/requirements.lock"],
   "npm_roots": ["cloud/web"],
-  "first_party_c": ["gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src"],
+  "first_party_c": ["gateway/canopen/src", "gateway/data_model", "gateway/storage", "gateway/mqtt/src", "gateway/esp_at_probe/src", "gateway/third_party/coreMQTT/source"],
   "github_repository": "Serendipity-min/medical-multi-parameter-monitor",
-  "compile_capture": ["{python}", "gateway/canopen/build_host.py"],
+  "compile_capture": ["{python}", "gateway/mqtt/tests/run_p5_host_tests.py", "--with-can-capture"],
   "commands": [
-    {"name": "sanitizer-fixed", "argv": ["{python}", "gateway/canopen/run_security_regression.py"], "required_file": "gateway/canopen/run_security_regression.py", "modes": ["quick", "pr", "release"], "mandatory": true},
+    {"name": "p5-coremqtt-asan-ubsan", "argv": ["{python}", "gateway/mqtt/tests/run_p5_host_tests.py", "--asan-ubsan", "--authorize-sanitizers"], "required_file": "gateway/mqtt/tests/run_p5_host_tests.py", "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "backend-tests", "argv": ["{python}", "-m", "pytest", "cloud/backend/tests", "-q", "-p", "no:cacheprovider"], "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "canopen-host-tests", "argv": ["{python}", "gateway/canopen/build_host.py"], "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "c-backend-test", "argv": ["{python}", "gateway/canopen/tools/check_canonical.py"], "modes": ["pr", "release"], "mandatory": true},
-    {"name": "paho-integrity", "argv": ["{python}", "gateway/third_party/verify_paho_integrity.py"], "required_file": "gateway/third_party/verify_paho_integrity.py", "modes": ["pr", "release"], "mandatory": true},
+    {"name": "coremqtt-integrity", "argv": ["{python}", "gateway/third_party/verify_coremqtt_integrity.py"], "required_file": "gateway/third_party/verify_coremqtt_integrity.py", "modes": ["quick", "pr", "release"], "mandatory": true},
+    {"name": "p5-source-contract-tests", "argv": ["{python}", "-m", "unittest", "discover", "-s", "gateway/mqtt/tests", "-p", "test_p5_integrity.py"], "required_file": "gateway/mqtt/tests/test_p5_integrity.py", "modes": ["quick", "pr", "release"], "mandatory": true},
+    {"name": "p5-coremqtt-ordinary", "argv": ["{python}", "gateway/mqtt/tests/run_p5_host_tests.py"], "required_file": "gateway/mqtt/tests/run_p5_host_tests.py", "modes": ["quick", "pr", "release"], "mandatory": true},
     {"name": "web-build", "argv": ["npm", "run", "build"], "cwd": "cloud/web", "modes": ["quick", "pr", "release"], "mandatory": true},
-    {"name": "gateway-build", "argv": ["{python}", "gateway/mqtt/build.py"], "modes": ["pr", "release"], "mandatory": false}
+    {"name": "gateway-build", "argv": ["{python}", "gateway/mqtt/build.py"], "modes": ["pr", "release"], "mandatory": true}
   ],
+  "historical_evidence": ["gateway/third_party/paho-embedded-c/PATCHES.md", "gateway/third_party/paho-embedded-c/upstream.json", "gateway/third_party/paho-embedded-c/patched.json", "gateway/canopen/run_security_regression.py"],
   "coverage_notes": ["ARM-only units absent from host compile database are explicit coverage gaps; no compiler flags are discarded"],
   "manual_checklist": ["browser_no_mqtt", "gateway_publish_only", "no_remote_nibp", "mock_live_replay_isolated", "stale_offline_no_old_value", "mqtt_no_anonymous", "tls_verification", "secrets_outside_git", "backend_internal", "nginx_broker_boundaries", "real_data_identity", "retention_policy", "no_physiological_payload_logs", "backup_permissions", "dependency_provenance", "residual_risk_owner"],
   "real_data_checklist": ["no_shared_test_token", "revocable_identity_or_vpn", "https_wss", "redacted_access_logs", "retention_deletion", "backup_permissions", "mock_live_isolation", "no_dangerous_remote_control"]
--- a/gateway/mqtt/tests/run_p5_host_tests.py
+++ b/gateway/mqtt/tests/run_p5_host_tests.py
@@ -1,5 +1,7 @@
 """用既有 GCC 编译真实 P5 源码的普通功能用例；不启用 sanitizer 或扫描器。"""
+import argparse
 import json
+import re
 import hashlib
 import os
 from pathlib import Path
@@ -13,6 +15,14 @@
 
 
 def main() -> int:
+    parser = argparse.ArgumentParser()
+    parser.add_argument('--asan-ubsan', action='store_true')
+    parser.add_argument('--authorize-sanitizers', action='store_true')
+    parser.add_argument('--with-can-capture', action='store_true')
+    args = parser.parse_args()
+    # 普通CI默认无sanitizer；安全模式必须在G1授权后显式选择，不能隐式升级普通测试。
+    if args.asan_ubsan != args.authorize_sanitizers:
+        parser.error('ASAN_UBSAN_REQUIRES_EXPLICIT_AUTHORIZATION')
     if sys.platform == 'win32':
         # 只复用已安装 HERA-C3 的 GCC，不安装工具；argv 直接传递，避免 shell 拼接路径。
         linux_root = '/mnt/' + ROOT.drive[0].lower() + ROOT.as_posix()[2:]
@@ -20,14 +30,23 @@
         # Windows worktree 的 .git 绝对路径无法由 Linux Git 解析，仅传公开提交标识。
         return subprocess.call(['wsl', '-d', 'HERA-C3', '--cd', linux_root, '--',
                                 'env', 'P5_COMMIT=' + commit,
-                                'python3', 'gateway/mqtt/tests/run_p5_host_tests.py'])
+                                'python3', 'gateway/mqtt/tests/run_p5_host_tests.py', *sys.argv[1:]])
+    # Gate只复制源码、不带.git；G1必须从批准HEAD注入P5_COMMIT，不能造一个快照提交冒充源身份。
+    source_commit = os.environ.get('P5_COMMIT') or subprocess.check_output(
+        ['git', 'rev-parse', 'HEAD'], text=True).strip()
+    if not re.fullmatch(r'[0-9a-f]{40}', source_commit):
+        parser.error('EXACT_SOURCE_COMMIT_REQUIRED')
+    if args.with_can_capture:
+        # bear包围此入口时同时捕获原CAN/Router及活动coreMQTT的真实编译命令。
+        subprocess.run([sys.executable, str(ROOT / 'gateway/canopen/build_host.py')], check=True)
     stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
     out = MQTT / 'build/p5-tests' / stamp
     out.mkdir(parents=True, exist_ok=True)
     report = {'started_at': datetime.now(timezone.utc).isoformat(), 'synthetic': True,
-              'security_gate': 'NOT_AUTHORIZED/NOT_RUN', 'tests': []}
-    report['commit'] = os.environ.get('P5_COMMIT') or subprocess.check_output(
-        ['git', 'rev-parse', 'HEAD'], text=True).strip()
+              'security_gate': 'AUTHORIZED_BOUNDED_ASAN_UBSAN' if args.asan_ubsan else 'NOT_AUTHORIZED/NOT_RUN', 'tests': []}
+    report['commit'] = source_commit
+    report['asan_ubsan'] = args.asan_ubsan
+    report['with_can_capture'] = args.with_can_capture
     report['compiler'] = subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0]
     # 文件摘要绑定本次真实编译输入；即使提交后再增补文档，也不混淆测试代码版本。
     inputs = [*sorted((MQTT / 'src').glob('*.[ch]')),
@@ -55,6 +74,9 @@
                             str(ROOT / 'gateway/storage/router.c'),
                             *[str(VENDOR / 'source' / source) for source in
                               ['core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c']]]
+        if args.asan_ubsan:
+            # 同一42项固定夹具编译真实活动源码；编译和链接一起启用，不关闭任何诊断。
+            command[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-g']
         compiled = subprocess.run(command, text=True, capture_output=True)
         (out / f'{name}-compile.log').write_text(compiled.stdout + compiled.stderr, encoding='utf-8')
         if compiled.returncode:
@@ -63,7 +85,12 @@
             (out / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
             print(compiled.stderr)
             return 1
-        result = subprocess.run([str(out / name)], text=True, capture_output=True)
+        test_environment = os.environ.copy()
+        if args.asan_ubsan:
+            test_environment.update(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
+                                    UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
+        result = subprocess.run([str(out / name)], text=True, capture_output=True,
+                                env=test_environment, timeout=120 if args.asan_ubsan else None)
         (out / f'{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
         report['tests'].append({'suite': name, 'exit_code': result.returncode,
                                 'cases': result.stdout.splitlines(), 'command': command})
```
