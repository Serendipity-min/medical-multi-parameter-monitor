"""普通Host队列回归：使用真实队列C源和既有夹具，不连接硬件。"""
from pathlib import Path
import os
import subprocess

root = Path(__file__).resolve().parents[2]
out = Path(os.environ['NODE_B_TEST_OUT']) / 'queue'
out.mkdir(parents=True, exist_ok=False)
source = root / 'node-b/firmware/biov2/实验固件/HARDWARE'
command = ['C:/mingw64/bin/gcc.exe', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
           '-DECG_QUEUE_HOST_TEST', '-I' + str(source), str(source / 'ecg_frame_queue.c'),
           str(Path(__file__).with_name('test_production_queue.c')), '-o', str(out / 'queue.exe')]
proc = subprocess.run(command, capture_output=True)
(out / 'compile.log').write_bytes(proc.stdout + proc.stderr)
if proc.returncode:
    raise SystemExit(proc.returncode)
# 可执行文件由上面的Host编译产生，不调用下载器或调试器。
raise SystemExit(subprocess.run([str(out / 'queue.exe')]).returncode)
