# M0恢复入口

仅适用于本轮核验的A42608、B41516及C，不是通用F407刷写包。A/B本轮未刷写，其BIN与符号映射沿用原受限安装回执。

C的唯一当前应用制品由RELEASE-MANIFEST.json的selected_C_candidate指定。boot写sector0，code写sector4；禁止把两段拼成连续BIN、整片擦除、覆盖sector1–3/5–11或修改Options。

受限恢复原件入口：本机忽略文件node-b/build/m0-current-pointer.json。其job目录中的C-startup-order-install-pointer.json登记当前安装、原C44520完整备份及前一候选。完整Flash、Options、UID及配置不在Git；先核对这些原件的现有回执及SHA，再使用gateway/microphone/unified_install.py的plan-only模式审查install/restore参数。执行需要当期正确目标与现场隔离条件；不要向未知板卡套用文件。

既有入口按完整1MiB/Options、身份及当前镜像核对，限制下载器写入sector0/4，下载后全片验证，成功后才执行已授权的Reset/Go。下载/核验失败不得自动重复刷写或启动，保全原生日志，按该次回执采用受控恢复。

本轮隔离云配置及口令只存受限EFS；Git中不提供生产端点、SSID/口令或可直接复用的授权凭据。设备断电会清除本轮RAM网络配置。SDK Open/Close原生隐式副作用仍未证明消除。
