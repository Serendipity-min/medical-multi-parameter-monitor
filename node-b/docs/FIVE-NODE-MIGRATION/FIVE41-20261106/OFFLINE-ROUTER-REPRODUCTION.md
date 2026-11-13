# C出站策略缺陷的离线复现

使用本轮实际router.c、与C候选一致的MP_B5_CLOUD_CANDIDATE/MP_B5_EGRESS_FINAL/MP_ABC_TRI_CANDIDATE/MP_FIVE_NODE分支以及24实时＋56历史帧容量；输入为明确的合成夹具，无设备操作、无固件源码修改。编译和复现器原生退出均0，含义是两个既有缺陷被复现，不是修复通过。

1. 在线空队列连续放入同一A/PPG的两批：实时仍有大量空位，却只留下第二批，第一批迁入历史；live=1、cache=1、live_replaced=1。与B波形保护FIFO行为不同。
2. 历史有1批、实时成功配额已到8且距上次补传超过2秒，随后持续每100ms提供一个实时帧。连续25次mp_router_take_egress全部取实时，replay=0、cached=1、credit=8；真正的历史配额分支没有执行机会。

这两项共同解释持续负载时PPG被挤向历史、历史又被饿死直到淘汰的可行软件路径，不能替代A入口缺口根因或串口吞吐预算的现场证据。后续修复必须同时验证ECG/RESP/PPG完整性与发送预算，不只添加PPG例外或扩大缓存。

[原生结果](ROUTER-POLICY-REPRODUCER.json)。复现代码/编译日志/真实运行日志保存在本次忽略的build目录，未提交或push。
