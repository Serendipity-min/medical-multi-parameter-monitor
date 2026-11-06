# PPG短批计数解释更正

FIVE STATE的partial_batches/partial_samples对应ppg_partial_batches/ppg_partial_samples。实际MP_FIVE_NODE分支在波形间断、质量边界或静默尾段遇到已有PPG点时，调用emit提交真实短批后返回，保留最后真实采样时间，不补点、不把不同边界拼接。该计数不是丢弃，也不能单独证明已到Broker。

ECG窗该保留/提交计数增加8批/51点；RR窗增加10批/131点。两窗unstamped均无新增，说明本段没有因未授时拒绝这些emit。后续出站队列仍可能转存/淘汰旧批，这才是另一层损失。

B5 WAVE的partial_discarded是另一通用计数：ECG窗12→12，RR窗123→325；它不计入上述PPG保留分支，现有记录没有ECG/RESP细分，不能把202点直接归给有效RESP。

此前进度中把PPG的partial计数描述成丢弃不准确，现已更正；初版报告副本保留在corrections，原始实板数据、真实退出码和出站丢弃证据不变。
