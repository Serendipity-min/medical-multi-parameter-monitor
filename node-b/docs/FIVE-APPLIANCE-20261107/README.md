# FIVE-APPLIANCE｜离线实现交付（2026-11-07）

**OFFLINE_IMPLEMENTATION_PASS / CAPACITY_NOT_PASS / FIELD_NOT_RUN / FreeRTOS_NOT_STARTED**。

工作树 `E:/medical-monitor-five-appliance`，分支 `codex/five-appliance-integration-v1`，基点 `f9bdff8a6d73993390baf59abc8a52bdc992f16c`。离线实现结束时尚未提交或push；本次按负责人后续指令做独立分支Git交付，见[PI审核入口](PI-REVIEW.md)。没有接触设备、启动网络服务、调用真实模型或改变正式云端。原五板工作树和上轮只读核查文件保留。

- [实现、验证与资源](RESULTS.md)
- [录音/事实回复协议与隔离准备](PROTOCOL-AND-ISOLATION.md)
- [容量、FreeRTOS与41Ω的判断](CAPACITY-DECISION.md)
- [PI审核要点与本次Git交付范围](PI-REVIEW.md)
- [ARM资源及候选镜像摘要](ARM-RESOURCES.json)、[定向测试结果](TEST-RESULTS.json)、[保留项核对](PRESERVATION-CHECKS.json)
- [外部合同与参考源码溯源](SOURCE-INPUTS.json)、[供应模拟重跑结果](SUPPLIED-RERUN-SIM-RESULTS.json)

本目录中所有新 PCM 测试数据均由 C 整数序列生成，仅留忽略构建目录；没有私人录音或完整Flash。合成算法图和CSV显式标为Host输入。旧模拟报告的7项KNOWN_GAP作为历史状态保留，不改写；新代码对应的分层结果另见RESULTS。
