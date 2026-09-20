"""冻结 Paho 源码与平台头，复用已验证的 F407 HSI/标准库构建基础。"""
import importlib.util
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('probe_build',ROOT.parent/'esp_at_probe/build.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
vendor=ROOT.parent/'third_party/paho-embedded-c'
build=ROOT/'build'
build.mkdir(exist_ok=True)
canopen=ROOT.parent/'canopen'
core=ROOT.parent/'third_party/CANopenNode'
includes=[ROOT/'src',canopen/'src',core,*base.INCLUDES,vendor/'MQTTClient-C/src',vendor/'MQTTPacket/src']
flags=[*base.COMMON_FLAGS,'-DCO_MULTIPLE_OD','-DMQTTCLIENT_PLATFORM_HEADER=gateway_platform.h','-DMAX_MESSAGE_HANDLERS=1',
       *[f'-I{path}' for path in includes]]
sources=[*sorted((ROOT/'src').glob('*.c')),*sorted((canopen/'src').glob('*.c')),canopen/'stm32/bxcan_loopback.c',ROOT.parent/'data_model/model.c',ROOT.parent/'storage/router.c',core/'CANopen.c',*sorted((core/'301').glob('*.c')),*base.SOURCES[1:],vendor/'MQTTClient-C/src/MQTTClient.c',
         *sorted((vendor/'MQTTPacket/src').glob('*.c'))]
objects=[]
for source in sources:
    target=build/(source.stem+'.o')
    # 第三方代码仅包含 PATCHES.md 中列出的补丁；平台代码以全部告警为错误构建。
    warnings=['-Wextra','-Werror'] if (source.is_relative_to(ROOT/'src') or source.is_relative_to(canopen) or source.parent.name in ('data_model','storage')) else []
    subprocess.run([str(base.GCC),*flags,*warnings,'-c',str(source),'-o',str(target)],check=True)
    objects.append(target)
startup=build/'startup.o'
subprocess.run([str(base.GCC),*flags,'-c',str(base.STARTUP),'-o',str(startup)],check=True)
objects.append(startup)
elf=build/'gateway_mqtt.elf'
subprocess.run([str(base.GCC),*flags,'-T',str(ROOT/'STM32F407ZGT6_FLASH.ld'),'-Wl,--gc-sections',
                '--specs=nano.specs','--specs=nosys.specs','-o',str(elf),*map(str,objects),'-lm'],check=True)
subprocess.run([str(base.OBJCOPY),'-O','binary',str(elf),str(build/'gateway_mqtt.bin')],check=True)
subprocess.run([str(base.SIZE),str(elf)],check=True)
