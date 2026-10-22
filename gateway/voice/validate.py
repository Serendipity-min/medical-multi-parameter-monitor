"""有界功能验证：编译真实协议/官方MQTT，不访问实板、云服务或真实模型。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]


def main():
    if sys.platform == 'win32':
        # Windows worktree的.git绝对路径在WSL不可解析，公开HEAD由父进程显式传入。
        linux = '/mnt/' + ROOT.drive[0].lower() + ROOT.as_posix()[2:]
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        return subprocess.call(['wsl', '-d', 'HERA-C3', '--cd', linux, '--',
                                'env', 'VOICE_HEAD='+head, 'python3', 'gateway/voice/validate.py'])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT/'gateway/voice/build'/stamp;out.mkdir(parents=True)
    evidence = ROOT/'doc/VOICE-CLOUD/evidence'/('host-'+stamp);evidence.mkdir(parents=True)
    voice = ROOT/'gateway/voice'; mqtt = ROOT/'gateway/mqtt';vendor = ROOT/'gateway/third_party/coreMQTT'
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'head': os.environ['VOICE_HEAD'],
              'source_dirty': True, 'hardware': 'NOT_RUN', 'real_model_calls': 0, 'tests': [], 'exit_code': 0}
    groups = {
        'tts-existing': [voice/'tts_frame.c', voice/'tts_queue.c', voice/'tests/test_voice.c'],
        'p6v1': [voice/'tts_frame.c', voice/'p6v1.c', voice/'tests/test_p6v1.c'],
        'mixed-mqtt': [voice/'tts_frame.c', voice/'tts_queue.c', voice/'p6v1.c', voice/'cloud_voice.c',
                       voice/'tests/test_cloud_voice.c', mqtt/'tests/mocks/mock_esp.c',
                       mqtt/'src/gateway_transport.c', mqtt/'src/mqtt_transport_adapter.c',
                       ROOT/'gateway/data_model/model.c', ROOT/'gateway/storage/router.c',
                       *[vendor/'source'/n for n in ('core_mqtt.c','core_mqtt_serializer.c','core_mqtt_state.c')]]}
    for name, sources in groups.items():
        command = ['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',
                   *['-I'+str(p) for p in (voice, voice/'tests/hw',mqtt/'src',mqtt/'tests/mocks',vendor/'source/include',vendor/'source/interface')],
                   *(['-DMP_CLOUD_VOICE','-DGATEWAY_MQTT_HOST_TEST'] if name=='mixed-mqtt' else []),
                   *map(str,sources),'-o',str(out/name)]
        compiled = subprocess.run(command,capture_output=True)
        (evidence/(name+'-compile.log')).write_bytes(compiled.stdout+compiled.stderr)
        item = {'name':name,'command':command,'compile_exit':compiled.returncode}
        if compiled.returncode == 0:
            r = subprocess.run([str(out/name)],capture_output=True,timeout=30)
            (evidence/(name+'.log')).write_bytes(r.stdout+r.stderr);item['test_exit']=r.returncode
            print(r.stdout.decode(errors='replace'),end='')
        else:print(compiled.stderr.decode(errors='replace'))
        report['tests'].append(item)
        if item.get('test_exit',1):report['exit_code']=1
    inputs = {*[p for s in groups.values() for p in s],*voice.glob('*.h')}
    report['source_sha256'] = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)}
    (evidence/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('VOICE Host exit',report['exit_code']);return report['exit_code']


if __name__=='__main__':raise SystemExit(main())
