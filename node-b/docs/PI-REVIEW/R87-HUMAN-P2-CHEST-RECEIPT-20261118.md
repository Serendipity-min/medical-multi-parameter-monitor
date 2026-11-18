# R87 · P2 胸部贴法采集回执

2026-11-18（北京时间）。离线准备 **PASS**，现场与实录 **NOT_RUN**。

- 卡片提交 `e3425a205c3d99c1eeb44e9e33262259a12e0dd7`，文件 SHA-256 `0338f515c7b60e598e10c2b79e07b5356a8dff40ff5a3ac005a7b4119a7c16d6`。
- R85 P1 的受限原件复核通过，2,013,246 B，SHA-256 `805e3a2a82ddf8f6d02c5989e061ccca934b6bcd145fa27fcceeb75c5916a5d7`。R86 已确认 P1 的 HR 有效 2/281、RR 0/281，并提供 P2 比较所用的 QRS 与带内噪声基线。
- R83 C1 封存整片与卡片一致，全片 SHA-256 `a40ad7633b4c2acaa8db0fbb229d635e747fad148f67266610789ac032ce560f`，应用前 40,420 B SHA-256 `1c28707fa215f2ee068750440cc670cddc8e9629f45d20927fc2676ac168642b`。这是归档核对。
- 从 `codex/r85-electrode-triage@ae87a5c1c5a526a43b8bff57bfdfb18b547e428a` 提取录制器，原字节 SHA-256 `d2b4a3d11c761e00f0804582fb8b03d80dfc7e410739fa158be2267fb3f26686`。`python -m unittest discover -s node-b/tests -p test_r85_mqtt_readonly_capture.py -v` 的 3 项模拟用例复跑通过，源文件无 MQTT 发布调用。录制器仍只读订阅 NODE-A/B 的四项主题。
- 已在受限 EFS 预留独立 R87 目录，封存原录制器、启动包装器及分节点汇总工具。启动包装器只改当轮运行名前缀，输出为 `r87-<UTC>-node-ab.jsonl`，全轮只用一次录制连接，上限 60 分钟。后续文件交付目录为 `/home/mmpm-deploy/r83-capture/`。

| 项目 | 当前状态 |
| --- | --- |
| S0 当轮电气与现场条件 | UNKNOWN，待现场逐项确认电池供电、无市电、志愿者无植入设备与有人看护 |
| S0 胸部贴法与隐私同意 | UNKNOWN，需当轮明确同意。现场只留必要人员，胸部照片及身份信息不采集 |
| S1 PI WSS、MQTT 订阅与设备在线 | NOT_RUN。待 PI 先开 WSS 和通知窗口；MQTT 确认订阅后，按 GT → A/B → C 上电，D/E 断电；云端 A/B 在线才开始 P2 |
| S2 P2 | NOT_RUN。仅 P2，全部换新电极。先确认左手 SpO₂ 指夹读数，再按卡贴法和顺序执行 |
| S4 摘除、断电与交付 | NOT_RUN。结束后先摘电极和指夹，再断 C、A、B、GT，停录和封存 |
| R88 对照 | NOT_RUN。P2 待采集，P1 数据与 R86 结论保留独立 |

计时从 P2 贴好并确认开始静坐起算。按卡依次为 1 分钟静坐、10 秒标记、2 分钟正常呼吸、10 秒标记、1 分钟节律呼吸、10 秒结束标记，共 4 分 30 秒。留存实际开始、结束和分钟级异常，PI 可据此与波形对齐。
