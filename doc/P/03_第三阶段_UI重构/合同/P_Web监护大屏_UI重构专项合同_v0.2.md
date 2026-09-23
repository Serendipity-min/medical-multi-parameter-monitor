# Web 监护大屏 UI 重构专项合同 v0.2 — P4 实施结果对齐

> 文档类型：CONTRACT 的执行对齐版；旧 [v0.1](P_Web监护大屏_UI重构专项合同_v0.1.md) 保留历史授权正文。本版描述已合入的工程样机 UI，不新增开发授权。
> PR [#4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/4) 已合入 P4；源 SHA `49c0c3999c9be377e726610223f21736e3352e26`，Merge SHA `09695ff2023ef6fd8dadaf5ecd64268b384a9190`。

## 已实现的页面与技术

Vite 7.3.5、TypeScript、Vanilla DOM、Canvas 2D 和 Hash Router 组成六页面：Overview、ECG、SpO2、RESP、NIBP、TEMP。页面从同一数据源状态与浏览器会话读取，不把模拟值呈现成真实传感器验收结果。波形与数值的有效性、来源、时间及离线状态须与数据通道保持一致。

SessionHistory 是浏览器当前会话的有界记录；Freeze 仅冻结显示，不阻止通信层收帧和接收计数。CSV 导出只覆盖本地当前会话。Snapshot v1 以最终实现的结构、恢复条件与数据边界为准，不代表云端持久化。详情见 [最终替换与安全准出报告](../验收/02_Stitch六页面最终替换与安全准出报告_2026-09-22.md)。

## 验收与后续边界

最终 UI 的构建、交互、鉴权及门禁结果以 PR #4、对应 CI 和上述报告为证据。统一 Security Gate 已建立，但条件性发现与后续 Release Gate 不应写成“全部风险关闭”。UI 为工程样机展示，不用于临床判断。若后续修改页面或模拟数据，应在新分支按对应范围回归，不重写 v0.1 的历史授权或本次 PR 证据。
