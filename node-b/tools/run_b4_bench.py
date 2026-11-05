"""隔离台架及恢复包离线验证入口；只调用编译器和合成测试，不导入硬件SDK。"""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT / 'node-b/build' / ('b4-bench-tests-' + stamp); out.mkdir()
    vendor, dual = ROOT / 'gateway/third_party/CANopenNode', ROOT / 'gateway/dual_can'
    sources = [vendor / 'CANopen.c', *sorted((vendor / '301').glob('*.c')),
               ROOT / 'gateway/canopen/src/mp_od.c', ROOT / 'gateway/data_model/model.c',
               ROOT / 'gateway/storage/router.c', *[dual / name for name in
               ('b4_bus.c', 'b4_gateway.c', 'b4_bench.c', 'tests/bench.c')]]
    cases = []

    def run(name, argv, expected=0):
        # stdout/stderr原样留存，真实负例退出不改写为0；无硬件恢复/自动重试入口。
        p = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=240)
        log = p.stdout + p.stderr; (out / (name + '.log')).write_bytes(log)
        cases.append({'name': name, 'argv': list(map(str, argv)), 'exit_code': p.returncode,
                      'expected_exit': expected, 'passed': p.returncode == expected,
                      'log_sha256': hashlib.sha256(log).hexdigest()})
        print(name, p.returncode, flush=True)
        if p.returncode != expected: print(log.decode('utf-8', errors='replace')[-5000:])
        return p.returncode == expected

    exe = out / 'bench.exe'
    if run('compile-bench-host', ['C:/mingw64/bin/gcc.exe', '-std=c11', '-O2', '-Wall', '-Wextra',
            '-Werror', '-Wno-unused-parameter', '-DCO_MULTIPLE_OD', '-DMP_FRAME_MAX_SAMPLES=100',
            '-DMP_CACHE_CAPACITY=64', '-I' + str(dual), '-I' + str(ROOT / 'gateway/canopen/src'),
            '-I' + str(vendor), *sources, '-o', exe]):
        run('bench-protocol', [exe])
    phy=out/'phy60.exe'
    if run('compile-phy60-host', ['C:/mingw64/bin/gcc.exe', '-std=c11', '-O2', '-Wall', '-Wextra',
            '-Werror', '-Wno-unused-parameter', '-DCO_MULTIPLE_OD', '-DMP_FRAME_MAX_SAMPLES=100',
            '-DMP_CACHE_CAPACITY=64', '-DMP_FIVE_NODE', '-DB4_BENCH_LIMIT_MS=60000u',
            '-I'+str(dual), '-I'+str(ROOT/'gateway/canopen/src'), '-I'+str(vendor), *sources, '-o', phy]):
        run('phy60-protocol-and-stop', [phy])
    run('recovery-nor-and-negative-cases', [sys.executable, '-X', 'utf8', ROOT / 'node-b/tests/test_b4_recovery.py'])
    run('bench-network-mutually-exclusive', [sys.executable, dual / 'build_arm.py', '--bench', '--network-link'], 2)
    # 实际取证负例要求独立UART服务模型和管理门禁，不能只模拟足够的平均线速。
    capture=out/'capture.exe'
    flags=['C:/mingw64/bin/gcc.exe','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(dual)]
    if run('compile-capture',[*flags,dual/'b4_capture.c',dual/'tests/capture.c','-o',capture]):
        run('capture-polled-host',[capture]);run('capture-explicit-overflow',[capture,'overflow'])
        run('capture-independent-IRQ-service',[capture,'irq'])
    for name,extra in (('network',[]),('isolated',['-DB4_CAPTURE_SERIAL=1'])):
        exe=out/('link-policy-'+name+'.exe')
        if run('compile-link-policy-'+name,[*flags,*extra,'-DMP_FRAME_MAX_SAMPLES=100',
                 '-DMP_CACHE_CAPACITY=64',dual/'tests/link_policy.c','-o',exe]):
            run('link-policy-'+name,[exe])
    # 用RAM MMIO替身编译真实驱动，覆盖仲裁未完成、真正ACK、旧ALST失败和STOP取消邮箱。
    mmio = out / 'bxcan-retransmit.exe'
    if run('compile-bxcan-retransmit', [*flags, '-Wno-unused-parameter', '-DB4_BXCAN_MMIO_TEST=1',
            '-DB4_CAPTURE_SERIAL=1', '-DCO_MULTIPLE_OD', '-DMP_FRAME_MAX_SAMPLES=100',
            '-DMP_CACHE_CAPACITY=64', '-I' + str(ROOT / 'gateway/canopen/src'),
            '-I' + str(vendor), dual / 'b4_bxcan.c', dual / 'tests/bxcan_retransmit.c', '-o', mmio]):
        run('bxcan-retransmit-and-stop', [mmio])
    if run('compile-phy-bxcan', [*flags, '-Wno-unused-parameter', '-DB4_BXCAN_MMIO_TEST=1',
            '-DB4_CAPTURE_SERIAL=1', '-DB4_PHY_DIAGNOSTIC', '-DMP_FIVE_NODE', '-DCO_MULTIPLE_OD',
            '-DMP_FRAME_MAX_SAMPLES=100', '-DMP_CACHE_CAPACITY=64', '-I'+str(ROOT/'gateway/canopen/src'),
            '-I'+str(vendor), dual/'b4_bxcan.c', dual/'tests/bxcan_retransmit.c', '-o', mmio]):
        run('phy-CAN1-isolation-and-stop', [mmio])
    report = {'status': 'PASS' if len(cases) == 18 and all(c['passed'] for c in cases) else 'FAIL',
              'scope': 'OFFLINE_SYNTHETIC_NO_TARGET_IO', 'hardware_operations': 0, 'cases': cases,
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                [*sources,dual/'b4_capture.c',dual/'b4_capture.h',dual/'tests/capture.c',
                                 dual/'b4_resources.h',dual/'tests/link_policy.c',
                                 dual/'b4_bxcan.c',dual/'tests/bxcan_mmio_shim.h',dual/'tests/bxcan_retransmit.c',
                                 ROOT / 'node-b/tools/b4_recovery.py', ROOT / 'node-b/tests/test_b4_recovery.py', Path(__file__)]}}
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    print(str(out.relative_to(ROOT)), report['status'])
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
