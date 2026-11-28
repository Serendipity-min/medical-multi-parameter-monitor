"""R100 冻结版 PPG-RR（2026-11-19，采集前定稿，只用合成对照调参，未看新真人数据）：
ppg_rr.rr 的流程，加 8–39 次/分主峰限制；窗 32 s、步长 2 s；qmin=0.50；至少两个合格特征相差 ≤2 次/分才输出。"""
import ppg_rr, rr_sens  # noqa: F401  rr_sens 导入时启用 8–39 次/分限制
def rr(ppg, A, B):
    return ppg_rr.rr(ppg, A, B, W=32, step=2, qmin=.50, agree=2.0)
