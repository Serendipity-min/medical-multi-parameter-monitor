"""Host定向测试；输出仅为合成PCM/构建日志，不访问设备或服务。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cc', default=shutil.which('gcc') or 'gcc')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    flags = [args.cc, '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
             '-D__USE_MINGW_ANSI_STDIO=1', '-DMP_FRAME_MAX_SAMPLES=100', '-DMP_LIVE_CAPACITY=24',
             '-DMP_CACHE_CAPACITY=56', '-DMP_B5_EGRESS_FINAL', '-DMP_B5_CLOUD_CANDIDATE',
             '-DMP_ABC_TRI_CANDIDATE', '-DMP_FIVE_NODE', '-DMP_FINAL_UNIFIED',
             '-DMP_FIVE_APPLIANCE', '-DMP_CLOUD_VOICE', '-DCO_MULTIPLE_OD']
    flags += ['-I'+str(ROOT/p) for p in ['gateway/mqtt/src', 'gateway/microphone', 'gateway/b5',
              'gateway/voice', 'gateway/canopen/src', 'gateway/third_party/CANopenNode']]
    cases = {
        'startup': ['gateway/microphone/test_five_appliance_startup.c', 'gateway/storage/router.c',
                    'gateway/data_model/model.c', 'gateway/b5/b5_policy.c',
                    'gateway/microphone/mic_format.c', 'gateway/microphone/mic_protocol.c'],
        'keys-short-audio': ['gateway/microphone/test_five_appliance_audio.c',
                    'gateway/microphone/unified_audio.c', 'gateway/microphone/mic_format.c',
                    'gateway/microphone/mic_protocol.c', 'gateway/voice/tts_queue.c', 'gateway/voice/tts_frame.c'],
        'legacy-audio': ['gateway/microphone/test_unified_audio.c',
                    'gateway/microphone/unified_audio.c', 'gateway/microphone/mic_format.c',
                    'gateway/microphone/mic_protocol.c', 'gateway/voice/tts_queue.c', 'gateway/voice/tts_frame.c'],
    }
    results = []
    for name, sources in cases.items():
        exe = args.out/(name+'.exe')
        extra = ['-flto', '-fwhole-program', '-Wno-unused-function', '-Wno-return-type'] if name == 'startup' else []
        case_flags = [f for f in flags if name != 'legacy-audio' or f != '-DMP_FIVE_APPLIANCE']
        command = case_flags+extra+[str(ROOT/p) for p in sources]+['-o', str(exe)]
        build = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (args.out/(name+'-build.log')).write_text(build.stdout+build.stderr, encoding='utf-8')
        if build.returncode:
            raise RuntimeError(f'{name}: build exit {build.returncode}; see build log')
        command = [str(exe)] + ([str(args.out/'synthetic-mc01.bin')] if name == 'keys-short-audio' else [])
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (args.out/(name+'-run.log')).write_text(run.stdout+run.stderr, encoding='utf-8')
        results.append(dict(case=name, exit=run.returncode, output=run.stdout.strip()))
        print(name, run.returncode, run.stdout.strip(), run.stderr.strip())
        if run.returncode:
            raise RuntimeError(f'{name}: test exit {run.returncode}')
    library = args.out/'mic-protocol.dll'
    build = subprocess.run(flags+['-shared', str(ROOT/'gateway/microphone/mic_protocol.c'),
            str(ROOT/'gateway/microphone/mic_format.c'), '-o', str(library)], capture_output=True,
            text=True, encoding='utf-8', errors='replace')
    (args.out/'protocol-build.log').write_text(build.stdout+build.stderr, encoding='utf-8')
    if build.returncode:
        raise RuntimeError('protocol shared build failed')
    (args.out/'native-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
