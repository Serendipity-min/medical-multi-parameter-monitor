"""只做离线构建，不打开串口/J-Link、不运行烧录或网络客户端。"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', action='store_true')
    args = parser.parse_args()
    out = HERE / 'build' / ('host' if args.host else 'offline-bench')
    out.mkdir(parents=True, exist_ok=True)
    evidence = ROOT / 'doc/VOICE/evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    name = 'host' if args.host else 'offline-bench'
    linker = HERE/'BENCH_FLASH.ld'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    record = {'started_utc': datetime.now(timezone.utc).isoformat(), 'cwd': str(ROOT),
              'hardware': 'NOT_RUN', 'network': 'NOT_LINKED', 'commands': [],
              'feature': 'MP_TTS_BENCH' if not args.host else 'PURE_C_HOST', 'exit_code': 1}
    log = bytearray()
    def run(argv):
        argv = list(map(str, argv)); record['commands'].append(argv)
        r = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.extend(r.stdout)
        if r.returncode:
            raise subprocess.CalledProcessError(r.returncode, argv)
        return r.stdout

    sources = [HERE / 'tts_frame.c', HERE / 'tts_queue.c']
    try:
        if args.host:
            sources.append(HERE / 'tests/test_voice.c')
            executable = out / 'voice-host'
            run(['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I'+str(HERE), *sources, '-o', executable])
            record['host_result'] = run([executable]).decode().strip()
        else:
            spec = importlib.util.spec_from_file_location('base', ROOT/'gateway/esp_at_probe/build.py')
            base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
            sources += [HERE/'tts_uart_port.c', HERE/'bench_main.c', ROOT/'gateway/physical_can/src/system_hse.c',
                        *[p for p in base.SOURCES if p.name.startswith('stm32f4xx_') and p.name != 'stm32f4xx_it.c'], base.STARTUP]
            flags = [*base.COMMON_FLAGS, '-Wextra', '-Werror', '-DHSE_VALUE=8000000', '-DMP_TTS_BENCH',
                     '-I'+str(HERE), *['-I'+str(p) for p in base.INCLUDES]]
            # 独立链接只含USART2/时钟，不引入原网络启动入口或任何sector3数据。
            objects = []
            for i, src in enumerate(sources):
                obj = out / f'{i}_{src.stem}.o'; run([base.GCC, *flags, '-c', src, '-o', obj]); objects.append(obj)
            elf = out/'c_voice_offline_bench.elf'
            run([base.GCC, *flags, '-T', linker, '-Wl,--gc-sections', '-Wl,-Map='+str(out/'c_voice_offline_bench.map'),
                 '--specs=nano.specs', '--specs=nosys.specs', '-o', elf, *objects])
            run([base.OBJCOPY, '-O', 'binary', elf, out/'c_voice_offline_bench.bin'])
            record['size'] = run([base.SIZE, elf]).decode().strip()
            from bench_manifest import inspect
            record['image'] = inspect(elf, out/'c_voice_offline_bench.bin', base.TOOLCHAIN/'arm-none-eabi-nm.exe')
            if record['image']['erase_sectors'] != [0]:
                raise ValueError('BENCH_MUST_FIT_SECTOR0')
            record['toolchain'] = run([base.GCC, '--version']).decode().splitlines()[0]
        record['exit_code'] = 0
    except subprocess.CalledProcessError as exc:
        record['exit_code'] = exc.returncode
    except (OSError, ValueError) as exc:
        record['error'] = str(exc)
    finally:
        # 每轮独立时间戳保存原始失败，后续成功不会覆盖它。
        inputs = [*HERE.glob('*.[ch]'), Path(__file__), HERE/'bench_manifest.py', HERE/'tests/test_voice.c', *sources]
        record['input_sha256'] = {(p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else 'external-sdk/'+p.name):
                                 hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
        if not args.host: record['input_sha256'][linker.relative_to(ROOT).as_posix()] = hashlib.sha256(linker.read_bytes()).hexdigest()
        record['ended_utc'] = datetime.now(timezone.utc).isoformat()
        (evidence/f'{stamp}-{name}.log').write_bytes(log)
        (evidence/f'{stamp}-{name}.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({k: record[k] for k in ('exit_code','hardware','feature')}))
        print(log.decode(errors='replace')[-3000:])
    return record['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
