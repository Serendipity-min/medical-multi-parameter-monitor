# Security Gate Report

> 结果仅适用于本次提交、规则集和实际覆盖范围。

## Commit / Branch

Commit `ec75b10c885b066f6a7bd6142cc1a9cf98b6affa`; branch ``; dirty `False`

## Tool Versions

- semgrep: 1.175.0 (OK)
- trivy: Version: 0.74.0 (OK)
- gitleaks: 8.30.1 (OK)
- clang: Debian clang version 19.1.7 (3+b1) (OK)
- clang-tidy: Debian LLVM version 19.1.7 (OK)
- gcc: gcc (Debian 14.2.0-19) 14.2.0 (OK)
- node: v20.19.2 (OK)
- npm: 9.2.0 (OK)
- bear: bear 3.1.6 (OK)
- docker: None (MISSING)
- pip-audit: pip-audit 2.10.1 (OK)
- semgrep-pro: None (OK)
- arm: None (PROJECT_CONFIGURATION_REQUIRED)

## Gate Mode

pr

## Coverage

| Component | Status | Mandatory |
| --- | --- | --- |
| doctor | OK | True |
| semgrep-pro-validation | OK | True |
| semgrep | OK | True |
| gitleaks | OK | True |
| trivy | OK | True |
| pip-audit-0 | OK | True |
| npm-audit-0 | OK | True |
| clang-tidy | OK | True |
| npm-ci-0 | OK | True |
| sanitizer-fixed | MISSING | True |
| backend-tests | OK | True |
| canopen-host-tests | OK | True |
| c-backend-test | OK | True |
| paho-integrity | MISSING | True |
| web-build | OK | True |
| gateway-build | COVERAGE_GAP | False |
- Gap: clang-tidy:no-compilation-command:gateway/esp_at_probe/src/bridge.c
- Gap: clang-tidy:no-compilation-command:gateway/esp_at_probe/src/main.c
- Gap: clang-tidy:no-compilation-command:gateway/esp_at_probe/src/network_probe.c
- Gap: clang-tidy:no-compilation-command:gateway/esp_at_probe/src/stm32f4xx_it.c
- Gap: clang-tidy:no-compilation-command:gateway/esp_at_probe/src/syscalls.c
- Gap: clang-tidy:no-compilation-command:gateway/esp_at_probe/src/system_stm32f4xx.c
- Gap: clang-tidy:no-compilation-command:gateway/mqtt/src/gateway_transport.c
- Gap: clang-tidy:no-compilation-command:gateway/mqtt/src/heap.c
- Gap: clang-tidy:no-compilation-command:gateway/mqtt/src/main.c
- Gap: clang-tidy:no-compilation-command:gateway/mqtt/src/platform.c
- Gap: ARM-only units absent from host compile database are explicit coverage gaps; no compiler flags are discarded

## Findings

| ID | Tool / Rule | Relative path | Severity |
| --- | --- | --- | --- |
| 5326ed587770e311db43b023 | trivy / GHSA-g7r4-m6w7-qqqr | cloud/web/package-lock.json:0 | LOW |
| f2b3fd216b71f3a8145cc10e | trivy / CVE-2026-39363 | cloud/web/package-lock.json:0 | HIGH |
| f72e5a704f318ccc4edc9da0 | trivy / CVE-2026-39364 | cloud/web/package-lock.json:0 | HIGH |
| c971b8bef4830b0ee50adf51 | trivy / CVE-2026-53571 | cloud/web/package-lock.json:0 | HIGH |
| a746c9be662c407444fb5b6c | trivy / CVE-2026-39365 | cloud/web/package-lock.json:0 | MEDIUM |
| d4436121e647188b6b2cefd4 | trivy / CVE-2026-53632 | cloud/web/package-lock.json:0 | MEDIUM |
| 29cf8483b1faff4914da697f | npm-audit / esbuild | package-lock.json:0 | LOW |
| 89e545bc8946680a1605b89c | npm-audit / vite | package-lock.json:0 | HIGH |
| 325e582a26a8af357f406984 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_adapter.c:7 | MEDIUM |
| 25a3c06de08bf993b68c5c78 | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_adapter.c:12 | MEDIUM |
| 627e1d08af51b10ef43926b4 | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_adapter.c:26 | MEDIUM |
| 14b5943bab9aea2a0f53d912 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_adapter.c:84 | MEDIUM |
| 28c3a7a5d5025a72502fb1b3 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_can_driver.c:12 | MEDIUM |
| d6e4b255b6ab2ab2eebcfdac | clang-tidy / bugprone-multi-level-implicit-pointer-conversion | gateway/canopen/src/mp_can_driver.c:12 | MEDIUM |
| 76164cd51793ce15741837f8 | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_can_driver.c:99 | MEDIUM |
| 31f8ff7a24e3cabe5543109d | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_can_driver.c:106 | MEDIUM |
| 988c907ef764730d1945448a | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_can_driver.c:107 | MEDIUM |
| dfe83d028288a5205311f60c | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_can_driver.c:108 | MEDIUM |
| 94ba96409d54bc92f17f4f6d | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_can_driver.c:140 | MEDIUM |
| e818a576f6e0b35f8d48a13d | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_can_driver.c:146 | MEDIUM |
| e9cb937f6135b7a38e3d2938 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_can_driver.c:170 | MEDIUM |
| 70d423ba3d5de76c0c95b2c0 | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_od.c:7 | MEDIUM |
| 4870d0bc41f9a93310d7d8ea | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_od.c:20 | MEDIUM |
| ce7b357ee3b0300d57d4a9e6 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_od.c:68 | MEDIUM |
| c908a802ce5e43e18c34e7c3 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_od.c:69 | MEDIUM |
| 32c69ec4fc4d6bbbde86ec68 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_od.c:152 | MEDIUM |
| 9062341edd933662a16c30dd | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_od.c:156 | MEDIUM |
| fa6139f28506b0a2f607ba34 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_od.c:161 | MEDIUM |
| ca7d9c60b726026b0ffebff9 | clang-tidy / bugprone-easily-swappable-parameters | gateway/canopen/src/mp_stack.c:7 | MEDIUM |
| 1dfe93cb52fce89306017d93 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/canopen/src/mp_stack.c:45 | MEDIUM |
| 336d8cf9adb9a3b01661bc0b | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/data_model/model.c:25 | MEDIUM |
| 35f9d1c04d4ee43e9a7d3e02 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/data_model/model.c:112 | MEDIUM |
| 32deadee239e51f7863dfa59 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/data_model/model.c:114 | MEDIUM |
| cfa4d80aa55191a5a9673edd | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/data_model/model.c:117 | MEDIUM |
| 86a6eaa24b0317b720d44279 | clang-tidy / clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling | gateway/storage/router.c:7 | MEDIUM |

## Accepted Risk

No recorded valid acceptance.

## ASan/UBSan

- sanitizer-fixed: MISSING

## SCA

- trivy: OK
- pip-audit-0: OK
- npm-audit-0: OK

## Secrets

- gitleaks: OK

## Static C

- clang-tidy: OK

## Build/Test

- backend-tests: OK
- canopen-host-tests: OK
- c-backend-test: OK
- paho-integrity: MISSING
- web-build: OK
- gateway-build: COVERAGE_GAP

## DAST

Not executed in this mode; see coverage and project checklist.

## SBOM

SHA-256: None

## GitHub Alerts

Not executed in this mode; see coverage and project checklist.

## Architecture Checklist

Not executed in this mode; see coverage and project checklist.

## Residual Risk

- gateway-build:COVERAGE_GAP
- review:a746c9be662c407444fb5b6c
- review:d4436121e647188b6b2cefd4
- review:325e582a26a8af357f406984
- review:25a3c06de08bf993b68c5c78
- review:627e1d08af51b10ef43926b4
- review:14b5943bab9aea2a0f53d912
- review:28c3a7a5d5025a72502fb1b3
- review:d6e4b255b6ab2ab2eebcfdac
- review:76164cd51793ce15741837f8
- review:31f8ff7a24e3cabe5543109d
- review:988c907ef764730d1945448a
- review:dfe83d028288a5205311f60c
- review:94ba96409d54bc92f17f4f6d
- review:e818a576f6e0b35f8d48a13d
- review:e9cb937f6135b7a38e3d2938
- review:70d423ba3d5de76c0c95b2c0
- review:4870d0bc41f9a93310d7d8ea
- review:ce7b357ee3b0300d57d4a9e6
- review:c908a802ce5e43e18c34e7c3
- review:32c69ec4fc4d6bbbde86ec68
- review:9062341edd933662a16c30dd
- review:fa6139f28506b0a2f607ba34
- review:ca7d9c60b726026b0ffebff9
- review:1dfe93cb52fce89306017d93
- review:336d8cf9adb9a3b01661bc0b
- review:35f9d1c04d4ee43e9a7d3e02
- review:32deadee239e51f7863dfa59
- review:cfa4d80aa55191a5a9673edd
- review:86a6eaa24b0317b720d44279
- clang-tidy:no-compilation-command:gateway/esp_at_probe/src/bridge.c
- clang-tidy:no-compilation-command:gateway/esp_at_probe/src/main.c
- clang-tidy:no-compilation-command:gateway/esp_at_probe/src/network_probe.c
- clang-tidy:no-compilation-command:gateway/esp_at_probe/src/stm32f4xx_it.c
- clang-tidy:no-compilation-command:gateway/esp_at_probe/src/syscalls.c
- clang-tidy:no-compilation-command:gateway/esp_at_probe/src/system_stm32f4xx.c
- clang-tidy:no-compilation-command:gateway/mqtt/src/gateway_transport.c
- clang-tidy:no-compilation-command:gateway/mqtt/src/heap.c
- clang-tidy:no-compilation-command:gateway/mqtt/src/main.c
- clang-tidy:no-compilation-command:gateway/mqtt/src/platform.c
- ARM-only units absent from host compile database are explicit coverage gaps; no compiler flags are discarded
- f2b3fd216b71f3a8145cc10e
- f72e5a704f318ccc4edc9da0
- c971b8bef4830b0ee50adf51
- 89e545bc8946680a1605b89c
- sanitizer-fixed:MISSING
- paho-integrity:MISSING

## Final Verdict

**TOOL / COVERAGE ERROR**; exit `3`
