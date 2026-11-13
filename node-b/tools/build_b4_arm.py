"""独立构建B4候选，冻结部署源码不动；无下载、调试器或网络入口。"""
from pathlib import Path
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import argparse

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def replace_once(text, anchor, replacement):
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError('R6_ANCHOR_NOT_UNIQUE_' + str(count))
    return text.replace(anchor, replacement)


def inject_r6(text):
    # 在 ValueRefresh 及周期 UI 刷新后增加协作式 FrameFeed(TimeBase_GetMs())（严格对齐 8 处协作点）
    # 协作点 1: HR 状态刷新后
    text = replace_once(text,'StateTxt(HP_TXT_HR_ST, st_hr);',
                        'StateTxt(HP_TXT_HR_ST, st_hr);\n        FrameFeed(TimeBase_GetMs());')
    # 协作点 2: RR 状态刷新后
    text = replace_once(text,'StateTxt(HP_TXT_RR_ST, st_rr);',
                        'StateTxt(HP_TXT_RR_ST, st_rr);\n        FrameFeed(TimeBase_GetMs());')
    # 协作点 3: 探头刷新后
    text = replace_once(text,'ProbeRefresh(now_ms);',
                        'ProbeRefresh(now_ms);\n    FrameFeed(TimeBase_GetMs());')
    # 协作点 4: 探头页面刷新后
    text = replace_once(text,'if (s_cur == HP_SCR_PROBE) { ProbePageRefresh(now_ms); }',
                        'if (s_cur == HP_SCR_PROBE) { ProbePageRefresh(now_ms); }\n        FrameFeed(TimeBase_GetMs());')
    # 协作点 5: 质量统计刷新后
    text = replace_once(text,'QualityRefresh();\n    }',
                        'QualityRefresh();\n        FrameFeed(TimeBase_GetMs());\n    }')
    # 协作点 6: 60s 趋势历史推点后
    text = replace_once(text,'MinuteTick();                            // 60s：趋势历史推 1 点\n    }',
                        'MinuteTick();                            // 60s：趋势历史推 1 点\n        FrameFeed(TimeBase_GetMs());\n    }')
    # 协作点 7: 30s RTC 校时后
    text = replace_once(text,'ReadRTC();                               // 30s：RTC 校时\n    }',
                        'ReadRTC();                               // 30s：RTC 校时\n        FrameFeed(TimeBase_GetMs());\n    }')
    # 协作点 8: 控件扫描后
    text = replace_once(text,'ScanControls();\n    }',
                        'ScanControls();\n        FrameFeed(TimeBase_GetMs());\n    }')
    return text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--temp',action='store_true',help='离线构建UART4温度物表工程变体；不下载')
    parser.add_argument('--candidate-r6',action='store_true',help='离线构建带有R6微调度补偿的Node-B候选镜像；不下载')
    parser.add_argument('--temp-screen',action='store_true',help='复用旧USART3独立温度屏，仅构建显示绑定候选；不下载')
    args=parser.parse_args()
    if args.temp_screen and not(args.temp and args.candidate_r6):parser.error('--temp-screen requires --temp --candidate-r6')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT / 'node-b/build' / ('b4-arm-' + stamp)
    project = out / 'firmware'
    frozen = ROOT / 'node-b/firmware/biov2/实验固件'
    freeze = json.loads((ROOT / 'node-b/evidence/B4-001/deployment-freeze.json').read_text(encoding='utf-8'))
    for name, expected_sha in freeze['source_sha256'].items():
        if sha(ROOT / name) != expected_sha: raise RuntimeError('冻结部署源码漂移：' + name)
    shutil.copytree(frozen, project)
    shutil.copytree(ROOT / 'node-b/canopen', project / 'B4')
    if args.temp:
        shutil.copytree(ROOT / 'node-b/temperature', project / 'B5_TEMP')
    shutil.copytree(ROOT / 'gateway/third_party/CANopenNode', project / 'CANopenNode')
    dsp = Path('E:/medical-monitor-node-b-precan-closeout/node-b/build/arm-20261022T074340122429Z/firmware/CORE/arm_cortexM4lf_math.lib')
    expected = json.loads((ROOT / 'node-b/evidence/external-build-dependencies.json').read_text(encoding='utf-8'))['CMSIS_DSP_ARMCC_library']['sha256']
    assert sha(dsp) == expected
    shutil.copyfile(dsp, project / 'CORE/arm_cortexM4lf_math.lib')
    # 仅构建副本增加生产者钩子：同一帧完成算法后投递，CAN任务主循环处理而非ISR。
    page = project / 'HARDWARE/hr_page.c'
    text = page.read_text(encoding='utf-8')
    hook = 'BioV2_Process(ecg_code,resp_code,sampleMs,sequence,ADS1292_GetLastFrameFlags());'
    assert text.count(hook) == 1
    text = '#include "b_canopen_app.h"\n' + text.replace(hook, hook +
        '\n        /* 通信只读取已处理快照，不改变250SPS采集及算法。 */\n'
        '        BCan_Sample(sampleMs,sequence,ADS1292_GetLastFrameFlags());\n'
        '        CanOpen_Task(TimeBase_GetMs());')
    if args.candidate_r6:
        text = inject_r6(text)
        (out / 'hr_page.candidate.c').write_text(text, encoding='utf-8')
    if args.temp_screen:
        text='#include "b_temp_screen.h"\n'+text
        text=replace_once(text,'ValueRefresh(now_ms);','ValueRefresh(now_ms);\n        BTempScreen_Refresh(TimeBase_GetMs());\n        FrameFeed(TimeBase_GetMs());')
    page.write_text(text, encoding='utf-8')
    main_c = project / 'USER/main.c'
    text = main_c.read_text(encoding='utf-8').replace('#include "canopen.h"', '#include "b_canopen_app.h"')
    # 屏10ms时基和算法TIM2时基不混用，避免两次CAN任务之间出现假回绕/假过期。
    text = text.replace('CanOpen_Task(now_ms);', 'CanOpen_Task(TimeBase_GetMs());')
    text = text.replace('CAN1 1M + CANopen 从站(NodeID=3)', 'CAN1 500kbps + CANopenNode B2（软件候选，未实测）')
    if args.temp:
        text='#include "b_temperature.h"\n'+text
        text=text.replace('UartInit(HMI_BAUDRATE);','UartInit(HMI_BAUDRATE);\n    BTemp_Init();')
    if args.temp_screen:
        text='#include "b_temp_screen.h"\n'+text
        text=replace_once(text,'BTemp_Init();','BTemp_Init();\n    BTempScreen_Init();')
        driver=project/'SCREEN/hmi_user_uart.c';uart=driver.read_text(encoding='utf-8')
        marker='void SendChar(uchar t)';at=uart.index(marker);body=uart[at:]
        body=replace_once(body,'{\n','{\n    USART_TypeDef *target=BTempScreen_IsSelected()?USART3:USART1;\n')
        if body.count('USART1,')!=3:raise RuntimeError('TEMP_SCREEN_UART_SEND_ANCHOR')
        driver.write_text('#include "b_temp_screen.h"\n'+uart[:at]+body.replace('USART1,','target,'),encoding='utf-8')
    main_c.write_text(text, encoding='utf-8')
    xml = project / 'USER/BIO_V2.uvprojx'
    tree = ET.parse(xml)
    for group in tree.findall('.//Group'):
        files = group.find('Files')
        if files is not None:
            for file in list(files):
                if file.findtext('FileName') in ('can.c', 'canopen.c'):
                    files.remove(file)
    group = ET.SubElement(tree.find('.//Groups'), 'Group')
    ET.SubElement(group, 'GroupName').text = 'B4_CANopenNode'
    files = ET.SubElement(group, 'Files')
    sources = [*sorted((project / 'B4').glob('*.c')), project / 'CANopenNode/CANopen.c',
               *sorted((project / 'CANopenNode/301').glob('*.c')), project / 'CANopenNode/303/CO_LEDs.c']
    if args.temp:
        sources += [project/'B5_TEMP/gy641.c',project/'B5_TEMP/b_temperature.c']
    if args.temp_screen:sources += [project/'B5_TEMP/b_temp_screen.c']
    for file in sources:
        entry = ET.SubElement(files, 'File')
        ET.SubElement(entry, 'FileName').text = file.name
        ET.SubElement(entry, 'FileType').text = '1'
        ET.SubElement(entry, 'FilePath').text = '..\\' + str(file.relative_to(project)).replace('/', '\\')
    inc = tree.find('.//Cads/VariousControls/IncludePath')
    inc.text = '..\\B4;..\\CANopenNode;' + inc.text
    if args.temp:
        inc.text='..\\B5_TEMP;'+inc.text
        define=tree.find('.//Cads/VariousControls/Define')
        define.text=(define.text+',' if define.text else '')+'B_TEMP_ENABLED'
    # CANopenNode使用标准inline/指定初始化，AC5必须显式选择C99。
    tree.find('.//Cads/uC99').text = '1'
    tree.write(xml, encoding='utf-8', xml_declaration=True)
    for folder in ('OBJ', 'USER/Listings'):
        (project / folder).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'node-b/acquisition/工具'))
    from acq_swd import ascii_mapping  # 仅使用盘符路径映射上下文，不构造SWD对象。
    uv = Path('D:/keil/UV4/UV4.exe')
    fromelf = Path('D:/keil/ARM/ARMCC/bin/fromelf.exe')
    with ascii_mapping(project) as prefix:
        result = subprocess.run([str(uv), '-r', prefix + 'USER/BIO_V2.uvprojx', '-o', prefix + 'build.log'], capture_output=True, timeout=180)
    log = (project / 'build.log').read_text(encoding='utf-8', errors='replace')
    (out / 'launcher.log').write_bytes(result.stdout + result.stderr)
    resource = re.search(r'Program Size: Code=(\d+) RO-data=(\d+) RW-data=(\d+) ZI-data=(\d+)', log)
    report = {'version': 'B4-0.3', 'scope': 'ARM_SOFTWARE_ONLY_NO_FLASH', 'exit_code': result.returncode,
              'hardware_eligible': False, 'deployment_default_unchanged': True,
              'bio_source_sha256': sha(project / 'HARDWARE/bio_v2.c'), 'log_sha256': sha(project / 'build.log'),
              'builder_sha256': sha(Path(__file__)), 'resources': list(map(int, resource.groups())) if resource else None,
              'tool_sha256': {'UV4': sha(uv), 'fromelf': sha(fromelf)}}
    report['temperature_variant']=args.temp
    report['candidate_r6_variant']=args.candidate_r6
    report['temperature_screen_variant']=args.temp_screen
    report['compiled_page_sha256']=sha(page)
    report['temperature_quantity']='nonhuman_object_surface_uncalibrated' if args.temp else 'INVALID'
    # 输出实际编译副本的头文件/工程输入SHA，覆盖屏幕钩子和C99选项，不只列出C文件。
    report['source_sha256'] = {p.relative_to(project).as_posix(): sha(p) for p in sorted(project.rglob('*'))
                              if p.is_file() and p.suffix.lower() in ('.c', '.h', '.s', '.uvprojx')}
    (out / 'executed-builder.py').write_bytes(Path(__file__).read_bytes())
    success = result.returncode == 0 and resource and '0 Error(s)' in log
    if success:
        binary = out / ('B5_TEMP_SCREEN_NODE_B.bin' if args.temp_screen else 'B5_TEMP_NODE_B.bin' if args.temp else 'B4_NODE_B.bin')
        axf = project / 'OBJ/BIO_V2.axf'
        symbols = out / 'symbols.txt'
        for mode, target in [('--bin', binary), ('-s', symbols)]:
            p = subprocess.run([str(fromelf), mode, '--output', str(target), str(axf)], capture_output=True)
            if p.returncode:
                success = False
                report['fromelf_exit_code'] = p.returncode
        if success:
            report['artifacts'] = {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in (binary, axf, symbols)}
            mapfile = project / 'USER/Listings/BIO_V2.map'
            report['map_status'] = 'PRESENT' if mapfile.is_file() else 'UNKNOWN_MISSING'
            if mapfile.is_file():
                report['artifacts'][mapfile.name] = {'bytes': mapfile.stat().st_size, 'sha256': sha(mapfile)}
    report['status'] = 'PASS' if success else 'FAIL'
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(str(out.relative_to(ROOT)), report['status'])
    print(log[-6000:])
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
