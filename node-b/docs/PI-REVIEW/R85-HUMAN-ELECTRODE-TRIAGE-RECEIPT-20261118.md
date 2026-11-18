# R85 · P1 手腕电极排查回执

2026-11-18（北京时间）。离线与服务器准备 **PASS**，现场上电、采集和实录 **NOT_RUN**。

- 卡片提交 `3d7f4fc30ceac35c05f8834e274449736a54ea83`，SHA-256 `d405fbb5ccbffcaa0e0e19279b0926820fce9d0f67575373a7cdb02fea68bbca`。
- 录制器提交 `a28cd94499b17122cbbb239d0ed6caf5bb525fe7`，脚本 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。沿用 R83 录制格式和 60 分钟上限，独立客户端仅以 QoS 0 订阅 NODE-A、NODE-B 各自的 `telemetry/+` 和 `status`，原始载荷照录。
- `python -m unittest discover -s node-b/tests -p test_r85_mqtt_readonly_capture.py -v` 在 Windows 和 Linux 各通过 3/3。验证 A 的 PR 和 B 的 INVALID 波形原载荷保留、四项订阅精确匹配、订阅拒绝及意外主题停止。录制源文件无 MQTT 发送调用。
- R83 封存写后读回前 40,420 B 的 SHA-256 为 `1c28707fa215f2ee068750440cc670cddc8e9629f45d20927fc2676ac168642b`，整片为 `a40ad7633b4c2acaa8db0fbb229d635e747fad148f67266610789ac032ce560f`，与卡片一致。本轮核对归档，未连接目标板。
- Broker 与后端的 `mmpm-control status <unit>` 均退出 0，active。后端现用 MQTT 配置可访问，运行环境为 Paho 2.1.0，交付目录属主及权限符合要求。启动命令和受限 EFS 目录已准备，实际 Broker 订阅尚未开启。

| 项目 | 状态 |
| --- | --- |
| 当轮现场安全条件 | 待核对。整条导电链、电池供电、志愿者知情同意与看护按卡执行 |
| S1 录制、上电和在线核对 | NOT_RUN。PI 需提前 5 分钟获知上电时刻，确认 MQTT 已订阅后按 GT → A/B → C 上电。A、B 云端上线后再开始 P1 |
| S2 P1 | NOT_RUN。负责人指定 P1：红 RA 右手腕内侧、黄 LA 左手腕内侧、绿 RL 右踝内侧。SpO₂ 指夹用左手手指，A 屏读数确认后计时 |
| S3 P2 | NOT_RUN。负责人指定本轮只做 P1 |
| S4 收尾及录制交付 | NOT_RUN |
| R86 分析 | 待采集原件。本轮录制的范围为现有遥测与状态 |
