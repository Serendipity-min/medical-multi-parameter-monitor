"""以项目内固定配置构建 STM32F407 ESP AT 查询固件，避免依赖图形 IDE 状态。"""

from pathlib import Path
import argparse
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent
BUILD = PROJECT / "build"
LIBRARY = Path(
    r"E:\stm32\stm32文件\1，STM32F4xx固件库\stm32f4_dsp_stdperiph_lib\STM32F4xx_DSP_StdPeriph_Lib_V1.4.0"
)
TOOLCHAIN = Path(r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin")
GCC = TOOLCHAIN / "arm-none-eabi-gcc.exe"
OBJCOPY = TOOLCHAIN / "arm-none-eabi-objcopy.exe"
SIZE = TOOLCHAIN / "arm-none-eabi-size.exe"

# 只编译实际使用的外设驱动，既缩短构建时间，也减小固件的攻击面与可审计范围。
SOURCES = [
    PROJECT / "src" / "main.c",
    PROJECT / "src" / "stm32f4xx_it.c",
    PROJECT / "src" / "system_stm32f4xx.c",
    PROJECT / "src" / "syscalls.c",
    LIBRARY / "Libraries" / "STM32F4xx_StdPeriph_Driver" / "src" / "stm32f4xx_rcc.c",
    LIBRARY / "Libraries" / "STM32F4xx_StdPeriph_Driver" / "src" / "stm32f4xx_gpio.c",
    LIBRARY / "Libraries" / "STM32F4xx_StdPeriph_Driver" / "src" / "stm32f4xx_usart.c",
]
STARTUP = (
    LIBRARY
    / "Libraries"
    / "CMSIS"
    / "Device"
    / "ST"
    / "STM32F4xx"
    / "Source"
    / "Templates"
    / "gcc_ride7"
    / "startup_stm32f40_41xxx.s"
)
INCLUDES = [
    PROJECT / "src",
    LIBRARY / "Libraries" / "CMSIS" / "Include",
    LIBRARY / "Libraries" / "CMSIS" / "Device" / "ST" / "STM32F4xx" / "Include",
    LIBRARY / "Libraries" / "STM32F4xx_StdPeriph_Driver" / "inc",
]
COMMON_FLAGS = [
    # F407 具备单精度 FPU；采用硬浮点 ABI 可避免旧版 CMSIS 在软浮点路径上的无效参数告警。
    "-mcpu=cortex-m4",
    "-mthumb",
    "-mfpu=fpv4-sp-d16",
    "-mfloat-abi=hard",
    "-DSTM32F40_41xxx",
    "-DUSE_STDPERIPH_DRIVER",
    "-Os",
    "-ffunction-sections",
    "-fdata-sections",
    "-Wall",
    "-std=c11",
]
PROJECT_WARNING_FLAGS = ["-Wextra", "-Werror"]


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True)


# 只使用既有工具链和外设库生成本机产物；烧录、备份与恢复由独立授权流程完成。
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--network-probe', action='store_true', help='构建只读分区与指定 SSID 查询固件'
    )
    parser.add_argument('--bridge', action='store_true', help='构建本机证书配置诊断桥')
    args = parser.parse_args()
    sources = list(SOURCES)
    if args.network_probe:
        sources[0] = PROJECT / 'src' / 'network_probe.c'
    target = 'esp_network_probe' if args.network_probe else 'esp_at_probe'
    if args.bridge:
        sources[0] = PROJECT / 'src' / 'bridge.c'
        target = 'esp_diagnostic_bridge'
    if not GCC.is_file():
        raise FileNotFoundError(f"未找到 ARM GCC：{GCC}")
    if not STARTUP.is_file() or not LIBRARY.is_dir():
        raise FileNotFoundError("未找到 STM32F4 标准外设库或启动文件")

    BUILD.mkdir(exist_ok=True)
    include_flags = [f"-I{path}" for path in INCLUDES]
    objects: list[Path] = []
    for source in sources:
        object_file = BUILD / f"{source.stem}.o"
        # 仅将 -Werror 施加到本项目源码；不为兼容新编译器而改写用户提供的旧版 ST 库。
        warnings = PROJECT_WARNING_FLAGS if source.is_relative_to(PROJECT) else []
        run(
            [
                str(GCC),
                *COMMON_FLAGS,
                *warnings,
                *include_flags,
                "-c",
                str(source),
                "-o",
                str(object_file),
            ]
        )
        objects.append(object_file)

    startup_object = BUILD / "startup.o"
    run([str(GCC), *COMMON_FLAGS, "-c", str(STARTUP), "-o", str(startup_object)])
    objects.append(startup_object)

    elf = BUILD / (target + ".elf")
    binary = BUILD / (target + ".bin")
    run(
        [
            str(GCC),
            *COMMON_FLAGS,
            "-T",
            str(PROJECT / "STM32F407ZGT6_FLASH.ld"),
            "-Wl,--gc-sections",
            "--specs=nano.specs",
            "--specs=nosys.specs",
            "-o",
            str(elf),
            *map(str, objects),
        ]
    )
    run([str(OBJCOPY), "-O", "binary", str(elf), str(binary)])
    run([str(SIZE), str(elf)])
    print(f"构建完成：{binary}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"构建失败：{error}", file=sys.stderr)
        raise SystemExit(1)
