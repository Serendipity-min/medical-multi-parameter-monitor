"""五板B原码/处理队列只读观察，沿用冻结ABI与G3解码，不采集B上的旧温度接口。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import subprocess

import b4_recovery as private
import b4_runtime as runtime
import b5_g3_contract as g
from b5_g3_devices import BLink

IMAGE_BYTES = 40040
IMAGE_SHA = 'f2276540bb8ca92551d08b78aecfdf31346597d9e273783f456be90c67014991'
ROOT = Path(__file__).resolve().parents[2]


def capture(job, installed):
    private.protected(job, False)
    out = job / 'B'
    out.mkdir()
    private.protected(out, False)
    (out / 'executed-B-source.py').write_bytes(Path(__file__).read_bytes())
    result = dict(exit_code=1, status='NOT_STARTED', explicit_Halt_Reset_Go_Flash_writes=0,
                  B_image_bytes=IMAGE_BYTES, B_image_sha256=IMAGE_SHA)
    link = None
    try:
        link = BLink(out, job, integration_window_s=540, debug_speed_khz=4000)
        # 此B镜像的slots/queue/clock/CAN/BIO ABI与原G3一致，增加的只有精确应用读长。
        from b5_g3_devices import READS
        link.allowed_reads = {address: set(sizes) for address, sizes in READS.items()}
        link.allowed_reads[0x08000000].add(IMAGE_BYTES)
        link.open()
        identity = runtime.raw.identity(link)
        runtime.raw.check_identity(identity)
        reference = json.loads((private.protected(installed, False) / 'probe/identity-after-private.json').read_text())
        g.require(identity == reference, 'G3_FIVE_B_IDENTITY')
        g.save(out / 'identity-private.json', identity)
        g.save(out / 'entry-sticky-private.json', dict(DHCSR=link.u32(runtime.ro.SYSTEM['DHCSR'])))
        state = runtime.ro.snapshot(link)
        g.save(out / 'entry-state-private.json', state)
        runtime.ro.check_running(link, state)
        app = link.read(0x08000000, IMAGE_BYTES)
        g.require(hashlib.sha256(app).hexdigest() == IMAGE_SHA, 'G3_FIVE_B_IMAGE')
        first = runtime.snapshot(link, out, 'prearm-first')
        time.sleep(2)
        last = runtime.snapshot(link, out, 'prearm-last')
        runtime.assess(first, last)
        g.save(job / 'B_READY.json', dict(monotonic=time.monotonic(), image_sha256=IMAGE_SHA,
                                       source_samples=last['bio']['samples']))
        with (out / 'blocks-private.bin').open('xb') as blocks, (out / 'blocks-private.jsonl').open('x') as index, \
             (out / 'diagnostics-private.jsonl').open('x') as diagnostics:
            g.append(diagnostics, 'B_DIAG', first)
            g.append(diagnostics, 'B_DIAG', last)
            count = 0
            next_diag = time.monotonic()
            while not (job / 'END_B').exists():
                started = time.monotonic()
                cpu = link.u32(runtime.ro.SYSTEM['DHCSR'])
                if cpu & (runtime.raw.HALT | runtime.raw.LOCKUP | runtime.raw.RESET):
                    link.verified_running_flash = False
                    g.save(out / 'changed-state-private.json', dict(DHCSR=cpu))
                    raise ValueError('G3_B_CPU_CHANGED')
                block = link.read(g.SLOTS, g.BLOCK_BYTES)
                blocks.write(block)
                blocks.flush()
                g.append(index, 'B_BLOCK', dict(index=count, offset=count*g.BLOCK_BYTES,
                    read_start=started, read_end=time.monotonic(), sha256=g.sha(block)))
                count += 1
                if time.monotonic() >= next_diag:
                    current = runtime.snapshot(link)
                    g.append(diagnostics, 'B_DIAG', current)
                    runtime.assess(last, current)
                    if current['CAN1_ESR'] & 0xffff0004:
                        raise ValueError('G3_FIVE_B_CAN_ERRORS')
                    last = current
                    next_diag += .5
                time.sleep(max(0, .05-(time.monotonic()-started)))
            final = runtime.snapshot(link)
            runtime.assess(last, final)
            g.append(diagnostics, 'B_DIAG', final)
        link.final_close_verified = True
        link.set_close_resume(True)
        result.update(exit_code=0, status='B_FIVE_RAW_AND_CAN_QUEUE_CAPTURED_REVIEW_PENDING', blocks=count)
    except (Exception, KeyboardInterrupt) as error:
        g.save(out / 'failure-private.json', dict(type=type(error).__name__, detail=str(error)))
        g.save(job / 'B_FAULT.json', dict(reason='B_SOURCE_OBSERVER_STOPPED'))
        result['error_type'] = type(error).__name__
        # 质量/主机错误仍与未知HALT/ROM区分；只在SDK和运行态均已核验时设置Close策略。
        if link and not link.native_failed and link.verified_running_flash:
            try:
                state = runtime.ro.snapshot(link)
                runtime.ro.check_running(link, state)
                link.final_close_verified = True
                link.set_close_resume(True)
            except Exception:
                link.verified_running_flash = False
    finally:
        if link:
            try:
                link.close()
                result['Close_completed'] = True
            except Exception as error:
                result.update(exit_code=1, Close_completed=False, close_error_type=type(error).__name__)
        g.save(out / 'receipt-private.json', result)
    print(json.dumps(result), flush=True)
    return result['exit_code']


def supervise(job, installed):
    private.protected(job, False)
    command = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker', '--job', str(job), '--installed', str(installed)]
    reason = None
    started = time.monotonic()
    with (job / 'B-native-worker-private.log').open('xb') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        while child.poll() is None:
            heartbeat = job / 'B/heartbeat-events.jsonl'
            if heartbeat.exists():
                with heartbeat.open('rb') as events:
                    events.seek(0, 2)
                    events.seek(max(0, events.tell()-2048))
                    tail = events.read()
                rows = tail.splitlines()
                if not tail.endswith(b'\n'):
                    rows = rows[:-1]
                if rows:
                    event = json.loads(rows[-1])
                    if event.get('active') and time.monotonic() > event['deadline_monotonic']:
                        reason = 'B_NATIVE_CALL_DEADLINE'
            if time.monotonic() - started > 540:
                reason = 'B_OBSERVER_SESSION_BOUND'
            if reason:
                g.save(job / 'B_FAULT.json', dict(reason=reason))
                child.kill()
                break
            time.sleep(.05)
        native = child.wait(timeout=5)
    g.save(job / 'B-supervisor.json', dict(worker_native_exit=native, reason=reason,
                                        target_reset_halt_go=0, forced_exit=bool(reason)))
    print(json.dumps(dict(B_worker_native_exit=native, supervisor_reason=reason)), flush=True)
    return native if reason is None else 4


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    raise SystemExit(capture(args.job, args.installed) if args.worker else supervise(args.job, args.installed))
