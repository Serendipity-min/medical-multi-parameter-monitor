"""固定 coreMQTT v2.3.1，复用原 F407 裸机构建；不连接硬件或网络服务。"""

import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
# 编译前离线核验 coreMQTT 固定原字节和 active 白名单；不运行安全回归。
subprocess.run(
    [sys.executable, str(ROOT.parent / 'third_party/verify_coremqtt_integrity.py')], check=True
)
spec = importlib.util.spec_from_file_location('probe_build', ROOT.parent / 'esp_at_probe/build.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
vendor = ROOT.parent / 'third_party/coreMQTT'
build = ROOT / 'build'
build.mkdir(exist_ok=True)
canopen = ROOT.parent / 'canopen'
core = ROOT.parent / 'third_party/CANopenNode'
includes = [
    ROOT / 'src',
    canopen / 'src',
    core,
    vendor / 'source/include',
    vendor / 'source/interface',
    *base.INCLUDES,
]
flags = [
    *base.COMMON_FLAGS,
    '-DCO_MULTIPLE_OD',
    *[f'-I{path}' for path in includes],
]
# 入口、项目适配和固定上游核心分别列出；这里仅构建文件，不连接开发板或烧录。
mqtt_sources = [
    vendor / 'source/core_mqtt.c',
    vendor / 'source/core_mqtt_serializer.c',
    vendor / 'source/core_mqtt_state.c',
]
sources = [
    *sorted((ROOT / 'src').glob('*.c')),
    *sorted((canopen / 'src').glob('*.c')),
    canopen / 'stm32/bxcan_loopback.c',
    ROOT.parent / 'data_model/model.c',
    ROOT.parent / 'storage/router.c',
    core / 'CANopen.c',
    *sorted((core / '301').glob('*.c')),
    *base.SOURCES[1:],
    *mqtt_sources,
]
objects = []
for source in sources:
    target = build / (source.stem + '.o')
    # 第三方代码仅包含 PATCHES.md 中列出的补丁；平台代码以全部告警为错误构建。
    warnings = (
        ['-Wextra', '-Werror']
        if (
            source.is_relative_to(ROOT / 'src')
            or source.is_relative_to(canopen)
            or source.parent.name in ('data_model', 'storage')
        )
        else []
    )
    subprocess.run(
        [str(base.GCC), *flags, *warnings, '-c', str(source), '-o', str(target)], check=True
    )
    objects.append(target)
startup = build / 'startup.o'
subprocess.run([str(base.GCC), *flags, '-c', str(base.STARTUP), '-o', str(startup)], check=True)
objects.append(startup)
elf = build / 'gateway_mqtt.elf'
subprocess.run(
    [
        str(base.GCC),
        *flags,
        '-T',
        str(ROOT / 'STM32F407ZGT6_FLASH.ld'),
        '-Wl,--gc-sections',
        '-Wl,-Map=' + str(build / 'gateway_mqtt.map'),
        '--specs=nano.specs',
        '--specs=nosys.specs',
        '-o',
        str(elf),
        *map(str, objects),
        '-lm',
    ],
    check=True,
)
subprocess.run(
    [str(base.OBJCOPY), '-O', 'binary', str(elf), str(build / 'gateway_mqtt.bin')], check=True
)
subprocess.run([str(base.SIZE), str(elf)], check=True)
