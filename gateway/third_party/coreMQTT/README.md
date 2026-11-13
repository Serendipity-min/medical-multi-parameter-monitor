# 固定 coreMQTT v2.3.1

官方仓库：https://github.com/FreeRTOS/coreMQTT

tag 对象 `f4616fa5753781aef73ed645edd5793a8028291d`，解引用 commit
`2beef04725328923e05e576b884212d53ec97af7`；协议 MQTT 3.1.1，MIT 许可。
三份 `.c`、四份公共头、transport_interface.h 和 LICENSE 均按官方 Git Blob
SHA-1 校验后原字节入库，SHA-256 见 upstream.json。保留上游换行字节，不格式化。

仅引入客户端必需文件；mqttFilePaths.cmake 已核对三份编译源。
项目配置、ESP 适配与普通测试位于 gateway/mqtt；不引入 RTOS、Agent 或 MQTT5。
离线检查：`python gateway/third_party/verify_coremqtt_integrity.py --vendor-only`；
最终 active 构建同时检查 build.py 的 MQTT 源白名单。
