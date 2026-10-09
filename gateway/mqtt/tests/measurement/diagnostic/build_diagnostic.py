"""仅从冻结Git对象导出/精确打补丁并ARM编译；不含设备、网络、Git提交或清理动作。"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE_OUTPUT = ROOT / 'gateway/mqtt/build/h16-diagnostic'
OUTPUT = BASE_OUTPUT / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
PINS = {'P4': '8dee339491cfd4edc468bb9451511d421f26db5e',
        'P5': 'e598fc63719acdf49a99c6da46c656dc8c607782'}
PRODUCTION = {'P4': '5fd386b8bfe0bcf54d4f53ffb1ec6483d086a1c3287b4fe6c37a3ddeacd90547',
              'P5': 'fd81076b9b34ad0a8f4ee35c08cd7ea14704f6d7b04620741cdf083c9c6c1069'}
ALLOWED_PATCH = frozenset(('gateway/mqtt/src/main.c', 'gateway/mqtt/src/platform.c',
                          'gateway/mqtt/src/gateway_transport.c', 'gateway/mqtt/src/heap.c',
                          'gateway/esp_at_probe/src/stm32f4xx_it.c'))
PROBE_FILES = ('probe_config.h', 'probe_events.h', 'probe_events.c')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def safe_target(root, relative):
    # Git归档/patch路径不能逸出独立构建树，不能接受绝对路径或链接重定向。
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
        raise ValueError('isolated path escape')
    return target

def export_source(variant, destination):
    if variant not in PINS or destination.exists():
        raise ValueError('unknown variant or existing export directory')
    destination = safe_target(OUTPUT, destination.relative_to(OUTPUT))
    destination.mkdir(parents=True)
    identities = {}
    expected = {}
    for entry in git('ls-tree', '-rz', PINS[variant], '--', 'gateway').split(b'\0'):
        if entry:
            meta, path = entry.split(b'\t', 1)
            mode, kind, blob = meta.split()
            if kind != b'blob' or mode not in (b'100644', b'100755'):
                raise ValueError('unsupported frozen Git mode')
            expected[path.decode('utf-8')] = blob.decode()
    # 直接读取不可变blob，不使用archive/checkout的换行转换；拒绝链接/设备模式。
    # 每个blob既核对Git SHA1，又另存SHA256，输出字节不能“规范化后算相同”。
    for path, blob in expected.items():
        data = git('cat-file', 'blob', blob)
        found = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if found != blob:
            raise ValueError('Git object data mismatch')
        target = safe_target(destination, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output:
            output.write(data)
        identities[path] = {'sha256': sha(data), 'git_blob': found}
    if set(identities) != set(expected) or any(identities[p]['git_blob'] != blob for p, blob in expected.items()):
        raise ValueError('exported source does not match frozen Git objects')
    return identities

def patch_paths(text):
    paths = [line[6:] for line in text.splitlines() if line.startswith('+++ b/')]
    if set(paths) != ALLOWED_PATCH or len(paths) != len(ALLOWED_PATCH):
        raise ValueError('overlay must touch exactly the reviewed five files')
    headers = [line for line in text.splitlines() if line.startswith('diff --git ')]
    if len(headers) != len(ALLOWED_PATCH):
        raise ValueError('unexpected patch section')
    for path in paths:
        if f'diff --git a/{path} b/{path}' not in headers or f'--- a/{path}' not in text.splitlines():
            raise ValueError('patch header/context mismatch')
    if any(line.startswith(('new file mode', 'deleted file mode', 'rename ', 'copy ', 'GIT binary patch')) for line in text.splitlines()):
        raise ValueError('non-text or rename overlay forbidden')
    return paths

def apply_exact_patch(source, patch_file, identities):
    text = patch_file.read_text(encoding='utf-8')
    patch_paths(text)
    # 先以完整冻结blob清单验证，之后使用git apply --check和零模糊上下文应用，不调用patch fuzz。
    for path in ALLOWED_PATCH:
        if sha(safe_target(source, path).read_bytes()) != identities[path]['sha256']:
            raise ValueError('overlay input source drift')
    command = ['git', 'apply', '--directory=' + source.relative_to(ROOT).as_posix()]
    # --directory为受控仓库内隔离树；不放宽git的路径保护，也不接触索引。
    for path in ALLOWED_PATCH:
        safe_target(source, path)
    subprocess.run([*command, '--check', str(patch_file)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([*command, str(patch_file)], cwd=ROOT, check=True, capture_output=True)
    return {path: {'before_sha256': identities[path]['sha256'],
                   'after_sha256': sha((source / path).read_bytes())} for path in sorted(ALLOWED_PATCH)}

def foundation(source):
    spec = importlib.util.spec_from_file_location('frozen_probe_build', source / 'gateway/esp_at_probe/build.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    return base

def compile_arm(variant, source, artifacts, report_dir):
    base = foundation(source)
    mqtt, canopen, core = [source / path for path in ('gateway/mqtt', 'gateway/canopen', 'gateway/third_party/CANopenNode')]
    vendor = source / 'gateway/third_party' / ('paho-embedded-c' if variant == 'P4' else 'coreMQTT')
    includes = [mqtt / 'src', canopen / 'src', core, *base.INCLUDES]
    flags = [*base.COMMON_FLAGS, '-DCO_MULTIPLE_OD']
    if variant == 'P4':
        includes.extend([vendor / 'MQTTClient-C/src', vendor / 'MQTTPacket/src'])
        flags += ['-DMQTTCLIENT_PLATFORM_HEADER=gateway_platform.h', '-DMAX_MESSAGE_HANDLERS=1']
        library_sources = [vendor / path for path in ('MQTTClient-C/src/MQTTClient.c',
            'MQTTPacket/src/MQTTConnectClient.c', 'MQTTPacket/src/MQTTDeserializePublish.c',
            'MQTTPacket/src/MQTTPacket.c', 'MQTTPacket/src/MQTTSerializePublish.c',
            'MQTTPacket/src/MQTTSubscribeClient.c', 'MQTTPacket/src/MQTTUnsubscribeClient.c')]
    else:
        includes += [vendor / 'source/include', vendor / 'source/interface']
        library_sources = [vendor / 'source' / name for name in ('core_mqtt.c', 'core_mqtt_serializer.c', 'core_mqtt_state.c')]
    flags += ['-I' + str(path) for path in includes]
    sources = [*sorted((mqtt / 'src').glob('*.c')), *sorted((canopen / 'src').glob('*.c')),
               canopen / 'stm32/bxcan_loopback.c', source / 'gateway/data_model/model.c', source / 'gateway/storage/router.c',
               core / 'CANopen.c', *sorted((core / '301').glob('*.c')), *base.SOURCES[1:], *library_sources]
    artifacts.mkdir()
    objects, commands, inputs = [], [], {}
    # 只复用原构建选项和源选择；仅额外生成map/stack-usage，未更改原build.py或linker。
    for number, file in enumerate(sources):
        target = artifacts / f'{number:02d}-{file.stem}.o'
        warnings = ['-Wextra', '-Werror'] if file.is_relative_to(mqtt / 'src') or file.is_relative_to(canopen) or file.parent.name in ('data_model', 'storage') else []
        command = [str(base.GCC), *flags, *warnings, '-fstack-usage', '-c', str(file), '-o', str(target)]
        commands.append(command)
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (report_dir / f'{variant}-{number:02d}-compile.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError('ARM compilation failed: ' + file.name)
        objects.append(target)
        inputs[str(file)] = sha(file.read_bytes())
    startup = artifacts / 'startup.o'
    command = [str(base.GCC), *flags, '-c', str(base.STARTUP), '-o', str(startup)]
    subprocess.run(command, check=True, capture_output=True); commands.append(command); objects.append(startup)
    inputs[str(base.STARTUP)] = sha(base.STARTUP.read_bytes())
    elf, binary, mapfile = [artifacts / ('gateway_mqtt' + suffix) for suffix in ('.elf', '.bin', '.map')]
    command = [str(base.GCC), *flags, '-T', str(mqtt / 'STM32F407ZGT6_FLASH.ld'), '-Wl,--gc-sections',
               '-Wl,-Map=' + str(mapfile), '--specs=nano.specs', '--specs=nosys.specs', '-o', str(elf), *map(str, objects), '-lm']
    linked = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace'); commands.append(command)
    (report_dir / f'{variant}-link.log').write_text(linked.stdout + linked.stderr, encoding='utf-8')
    if linked.returncode:
        raise RuntimeError('ARM link failed')
    subprocess.run([str(base.OBJCOPY), '-O', 'binary', str(elf), str(binary)], check=True, capture_output=True)
    sections = subprocess.check_output([str(base.SIZE), '-A', str(elf)], text=True)
    symbols = subprocess.check_output([str(base.TOOLCHAIN / 'arm-none-eabi-nm.exe'), '-S', '-n', str(elf)], text=True)
    (report_dir / f'{variant}-sections.txt').write_text(sections, encoding='utf-8')
    (report_dir / f'{variant}-symbols.txt').write_text(symbols, encoding='utf-8')
    disassembly = subprocess.check_output([str(base.TOOLCHAIN / 'arm-none-eabi-objdump.exe'), '-d', str(elf)], text=True)
    (report_dir / f'{variant}-disassembly.txt').write_text(disassembly, encoding='utf-8')
    return {'inputs_sha256': inputs, 'commands': commands, 'source_count': len(sources),
            'elf_sha256': sha(elf.read_bytes()), 'bin_sha256': sha(binary.read_bytes()), 'map_sha256': sha(mapfile.read_bytes()),
            'bin_bytes': binary.stat().st_size,
            'compiler': subprocess.check_output([str(base.GCC), '--version'], text=True).splitlines()[0]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if OUTPUT.exists():
        raise SystemExit('Existing diagnostic directory retained; use review output, no overwrite or cleanup')
    OUTPUT.mkdir(parents=True)
    reports = OUTPUT / 'reports'; reports.mkdir()
    summary = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'kind': 'OFFLINE_DIAGNOSTIC_BUILD',
               'hardware_activity': False, 'broker_activity': False, 'security_gate': 'NOT_AUTHORIZED/NOT_RUN',
               'M04': 'BLOCKED_UNSAFE_SENTINEL', 'variants': {}}
    for variant, commit in PINS.items():
        source = OUTPUT / (variant.lower() + '-source')
        identities = export_source(variant, source)
        (reports / f'{variant}-frozen-inputs.json').write_text(json.dumps(identities, indent=2), encoding='utf-8')
        patch = HERE / 'overlays' / (variant + '.patch')
        changes = apply_exact_patch(source, patch, identities)
        (reports / f'{variant}-applied.patch').write_bytes(patch.read_bytes())
        for file in PROBE_FILES:
            target = source / 'gateway/mqtt/src' / file
            if target.exists(): raise ValueError('probe filename collides with frozen source')
            target.write_bytes((HERE / file).read_bytes())
        (source / 'gateway/mqtt/src/probe_variant.h').write_text(f'#define PROBE_VARIANT_ID {variant[1]}U\n', encoding='ascii')
        verifier = source / 'gateway/third_party' / ('verify_paho_integrity.py' if variant == 'P4' else 'verify_coremqtt_integrity.py')
        verified = subprocess.run(['python', str(verifier)], capture_output=True, text=True, encoding='utf-8', errors='replace')
        (reports / f'{variant}-vendor-integrity.log').write_text(verified.stdout + verified.stderr, encoding='utf-8')
        if verified.returncode: raise ValueError('frozen vendor integrity failed')
        record = {'source_commit': commit, 'production_bin_sha256': PRODUCTION[variant],
                  'overlay_sha256': sha(patch.read_bytes()), 'changes': changes,
                  'probe_sources_sha256': {file: sha((HERE / file).read_bytes()) for file in PROBE_FILES},
                  'vendor_integrity_exit': verified.returncode}
        if not args.prepare_only:
            record['arm'] = compile_arm(variant, source, OUTPUT / variant.lower(), reports)
        summary['variants'][variant] = record
        (reports / 'build-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(variant + ' diagnostic preparation/build complete', flush=True)
    summary['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    (reports / 'build-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
