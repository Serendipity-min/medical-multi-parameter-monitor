"""R102 补记：集中度门槛 q 的敏感性（只改 Q_MIN，其余沿用 resp_eval_amend 的修订评估）。
R100 是开发集，本表只说明调 q 的代价，不作为新的门槛依据。"""
import contextlib, io, runpy, resp_r1, resp_eval_amend  # noqa: F401（导入即替换 window）
for q in (.35, .40, .45, .50, .55):
    resp_r1.Q_MIN = q; buf = io.StringIO()
    with contextlib.redirect_stdout(buf): runpy.run_path('resp_eval.py', run_name='__main__')
    print(f'##### Q_MIN = {q:.2f}'); print(buf.getvalue(), end='')
