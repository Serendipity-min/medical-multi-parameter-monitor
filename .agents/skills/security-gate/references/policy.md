# 授权与判定

- 普通代码改动不触发；自动发现已禁用。不安装后台任务或自动 Git hook。
- `doctor` 检查工具及 Pro 规则可用性；`release --dry-run` 只生成计划，永远不表示扫描 PASS。
- `quick/pr/release` 必须本次明确授权，并且 `--repo` 与模式落在授权范围；CLI 的 `--authorize` 是这次授权的记录，不是替用户决定。
- 退出码：0 PASS；1 FAIL；2 CONDITIONAL PASS / HUMAN REVIEW；3 TOOL / COVERAGE ERROR。
- 发布要求准确 commit、干净工作树、SBOM 哈希、报告哈希和人工审核。CONDITIONAL 需 P 书面接受；工具错误不能作为条件放行。
- 真实人体数据 checklist 缺失产生 FAIL_FOR_REAL_DATA；不得把 mock 验收等同于人体数据准入。
