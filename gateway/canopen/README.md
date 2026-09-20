# CANopen Gateway 阶段二

固定版本 CANopenNode 核心 + 项目 OD/驱动适配 + 两个合成测试生产者。当前 F407 构建采用静默内部 bxCAN loopback，不能直接当成三板实物正常模式固件。

- `src/mp_od.c`：对象字典与五路PDO映射。
- `src/mp_stack.c`：独立A/B/Gateway协议实例及测试生产者。
- `src/mp_can_driver.c`：有界帧队列；`stm32/bxcan_loopback.c`：真实CAN1外设端口。
- `src/mp_adapter.c`：Gateway RPDO镜像→Canonical Model；不直接拼JSON。
- `../data_model`：固定点模型和MQTT边界序列化。
- `../storage`：实时优先、RAM环形缓存、REPLAY和容量计数。
- `../mqtt`：ESP SSL/Paho传输、协作CAN调度、F407程序入口与构建。

本机或CI验证（Linux有gcc，Python安装项目Backend测试依赖）：

```text
python gateway/canopen/build_host.py
python gateway/canopen/tools/check_canonical.py
python -m pytest cloud/backend/tests -q
```

Windows使用本机已安装WSL运行第一条；后两条可使用项目`.venv`。STM32构建：`python gateway/mqtt/build.py`，使用已确认的本机ARM工具链和ST外设库，无网络下载。

硬件验收工具 `tools/board_acceptance.py` 需要 pyserial 3.5、Backend依赖、仓库外MQTT观察者配置和当前授权的开发板。`--flash-helper` 仅在显式指定时执行外部临时烧录程序；`--ssh-alias` 仅在显式指定时重启本项目Broker。私有二进制连接配置不得进入仓库。烧录前完整备份/比对，结束后恢复并验证原Flash。

本地串口控制：A/B分别切换测试节点，C切换测试总线，R重启B协议实例，G重启Gateway协议实例，E切换测试EMCY，D断开Wi‑Fi30秒。连续控制须等待前一条确认；这些是本地测试入口，不是远程设备控制API。

界面验证用 `tools/browser_phase2.py`：默认只在本机静态页面注入LIVE/REPLAY接口夹具，明确标注非实测，不会连接生产MQTT；显式传仓库外`--production-config`时只读验证真实云端Gateway-C合成流。

冻结接口及限制见 [阶段二文档](../../doc/P/02_第二阶段_CANopen可靠性/README.md)。
