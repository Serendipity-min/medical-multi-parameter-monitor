# RESP-003独立探索采集

本目录属于E0软件准备，不是当前硬件授权。源模板为`RESP_EXPLORATORY`、operator_ready=false，保留Z0/delta_Zpp=null、实际动态电极对UNVERIFIED。新运行profile使用独立schema，拒绝旧ECG profile；公共profile.offline.json禁用，真实板参考仅私有保存。

新入口为`supervise_resp_b.py`→`capture_resp_b.py`；完整120B诊断和纯脱机独立估计在`resp_exploratory.py`，冻结C源回放及报告在`analyze_resp_b.py`。旧ECG工具/profile及六窗原件不改。E1只允许10秒，E2/E3尚未在采集profile中启用；不得通过改seconds或冒用ORDINARY_ECG绕过阶段卡。

当前E0测试不加载J-Link DLL、不打开探针。新源的未知ΔΩ不再阻断探索，但电气判断和真实菜单确认仍须按[准确R2卡](../../docs/AUTH-B-RESP-PILOT-001-R2.md)完成。源模板的15/1.5R是提案，不能据此宣称已经切换模拟器；窒息项必须保存实际文字。

每次真实执行前，冻结卡、profile、source-record及工具SHA，完整argv和退出码写私有执行记录；成功/异常/冲突均独占保存，不覆盖旧轮次。原始帧、实板诊断、Host回放、独立估计和名义菜单参考分开标注。工厂检测照片、UID、整片Flash、RAM与波形仅留受限目录。
