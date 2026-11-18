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


DIAG_REASON_ANCHOR = 'TxtGB(HP_SCR_PROBE, HP_TXT5_ADVICE, adv);'
HOME_QUALITY_WRITE = '    SetTextValue(HP_SCR_HOME, HP_TXT_QUAL, (uchar *)buf);\n'
HOME_CAPTURE_WRITE = '        TxtGB(HP_SCR_HOME, HP_TXT_CAP, STR_CAP);\n    }\n'
VALUE_TICK = '        ValueRefresh(now_ms);                    // 1s：瞬时心率/呼吸率 + 报警'


def inject_diag_reason(text):
    return replace_once(text, DIAG_REASON_ANCHOR, '''{
        const float ecg = g_bio_v2.ecg_mains_fraction;
        const float resp = g_bio_v2.resp_mains_fraction;
        const float rms = g_bio_v2.ecg_rms_codes;
        const unsigned ecg_pct = ecg >= 1.0f ? 100u : ecg > 0.0f ? (unsigned)(ecg * 100.0f + 0.5f) : 0u;
        const unsigned resp_pct = resp >= 1.0f ? 100u : resp > 0.0f ? (unsigned)(resp * 100.0f + 0.5f) : 0u;
        const unsigned long codes = rms >= 999999.0f ? 999999ul : rms > 0.0f ? (unsigned long)rms : 0ul;
        (void)adv;
        snprintf(buf, sizeof(buf), "H%lu R%lu M%u/%u E%lu",
                 (unsigned long)(g_bio_v2.hr_reason & 0xffu),
                 (unsigned long)(g_bio_v2.rpm_reason & 0xffu), ecg_pct, resp_pct, codes);
        TxtGB(HP_SCR_PROBE, HP_TXT5_ADVICE, (const uint8_t *)buf);
    }''')


def inject_capture_diag_reason(text):
    return replace_once(text, HOME_CAPTURE_WRITE, '''        {
            char diag[sizeof("H255 R255 M100")];
            const float ecg = g_bio_v2.ecg_mains_fraction;
            const unsigned pct = ecg >= 1.0f ? 100u : ecg > 0.0f ? (unsigned)(ecg * 100.0f + 0.5f) : 0u;
            snprintf(diag, sizeof(diag), "H%lu R%lu M%u",
                     (unsigned long)(g_bio_v2.hr_reason & 0xffu),
                     (unsigned long)(g_bio_v2.rpm_reason & 0xffu), pct);
            TxtGB(HP_SCR_HOME, HP_TXT_CAP, (const uint8_t *)diag);
        }
    }
''')


def inject_home_diag_reason(text):
    text = inject_capture_diag_reason(replace_once(text, HOME_QUALITY_WRITE, ''))
    return replace_once(text, VALUE_TICK, VALUE_TICK + '''
        if (s_cur == HP_SCR_HOME)
        {
            char diag[sizeof("H255 M100")];
            const float ecg = g_bio_v2.ecg_mains_fraction;
            const unsigned pct = ecg >= 1.0f ? 100u : ecg > 0.0f ? (unsigned)(ecg * 100.0f + 0.5f) : 0u;
            snprintf(diag, sizeof(diag), "H%lu M%u", (unsigned long)(g_bio_v2.hr_reason & 0xffu), pct);
            SetTextValue(HP_SCR_HOME, HP_TXT_QUAL, (uchar *)diag);
        }''')


def inject_algo_c1(text):
    replacements = (
        ('    uint32_t count, index, candidate_rate, reason;\n',
         '    uint32_t count, index, candidate_rate, reason, required;\n'),
        ('static uint8_t have_sample;\n', '''static uint8_t have_sample;
#ifndef HEART_REQUIRED
#define HEART_REQUIRED 5u
#endif
#ifndef MAINS_ABS_POWER
#define MAINS_ABS_POWER 9.6e11f /* 约100 mV峰值工频 */
#endif
'''),
        ('    c->periods.reason=BIO_V2_WARMUP;\n',
         '    c->periods.reason=BIO_V2_WARMUP;\n    c->periods.required=respiration ? 3u : HEART_REQUIRED;\n'),
        ('if (p->count<3u) return 1;', 'if (p->count<p->required) return 1;'),
        ('if(fraction>.95f && c->raw_power>10000.0f)reason|=BIO_V2_MAINS;',
         'if(c->line_power>MAINS_ABS_POWER)reason|=BIO_V2_MAINS;'),
        ('if(good_h && heart.raw_power>10000.0f && heart.line_power>heart.raw_power*.95f) {',
         'if(good_h && heart.line_power>MAINS_ABS_POWER) {'),
        ('if(good_r && breathing.raw_power>10000.0f && breathing.line_power>breathing.raw_power*.95f) {',
         'if(good_r && breathing.line_power>MAINS_ABS_POWER) {'),
    )
    for anchor, replacement in replacements:
        text = replace_once(text, anchor, replacement)
    return text


def inject_algo_c2(text):
    # 按 R89 §2.1 仅替换构建副本，锚点必须唯一。
    replacements = (
        ('''typedef struct { float b0,b1,b2,a1,a2,z1,z2; } Section;
typedef struct {
    uint32_t anchor, last_good, minimum, maximum, timeout, intervals[5];
    uint32_t count, index, candidate_rate, reason, required;
    uint8_t anchored;
} Periods;
typedef struct {
    Section notch1, notch2, hp, lp;
''',
         '''typedef struct { float b0,b1,b2,a1,a2,z1,z2; } Section;
typedef struct {
    uint32_t anchor, last_good, minimum, maximum, timeout, intervals[5];
    uint32_t count, index, candidate_rate, reason, required, tolerance;
    uint8_t anchored, bridge, bridged;
} Periods;
typedef struct {
    Section notch1, notch2, hp, lp;
'''),
        ('''#ifndef HEART_REQUIRED
#define HEART_REQUIRED 5u
#endif
#ifndef MAINS_ABS_POWER
#define MAINS_ABS_POWER 9.6e11f /* 约100 mV峰值工频 */
#endif
''',
         '''#ifndef HEART_REQUIRED
#define HEART_REQUIRED 5u
#endif
#ifndef HEART_TOLERANCE
#define HEART_TOLERANCE 30u /* 心搏窗口相对中位数的允许偏差，百分比 */
#endif
#ifndef MAINS_ABS_POWER
#define MAINS_ABS_POWER 9.6e11f /* 约100 mV峰值工频 */
#endif
'''),
        ('''static void forget_periods(Periods *p,uint32_t reason)
{
    /* 失效清除资格和全部旧间隔；仅保留配置，不重置滤波制造新的阶跃。 */
    p->count=0;p->index=0;p->candidate_rate=0;p->anchored=0;p->last_good=0;
    memset(p->intervals,0,sizeof(p->intervals));p->reason=reason;
}
static void configure(Channel *c,uint8_t respiration)
''',
         '''static void forget_periods(Periods *p,uint32_t reason)
{
    /* 失效清除资格和全部旧间隔；仅保留配置，不重置滤波制造新的阶跃。 */
    p->count=0;p->index=0;p->candidate_rate=0;p->anchored=0;p->bridged=0;p->last_good=0;
    memset(p->intervals,0,sizeof(p->intervals));p->reason=reason;
}
static void configure(Channel *c,uint8_t respiration)
'''),
        ('''    c->periods.timeout=respiration ? 12000u : 4000u;
    c->periods.reason=BIO_V2_WARMUP;
    c->periods.required=respiration ? 3u : HEART_REQUIRED;
}
static uint8_t accept_input(Channel *c,int32_t raw,uint8_t resp,uint32_t now)
{
''',
         '''    c->periods.timeout=respiration ? 12000u : 4000u;
    c->periods.reason=BIO_V2_WARMUP;
    c->periods.required=respiration ? 3u : HEART_REQUIRED;
    c->periods.tolerance=respiration ? 20u : HEART_TOLERANCE;
    c->periods.bridge=!respiration;
}
static uint8_t accept_input(Channel *c,int32_t raw,uint8_t resp,uint32_t now)
{
'''),
        ('''}
static void expire(Periods *p,uint32_t now)
{
    if ((p->count!=0 && (uint32_t)(now-p->last_good)>p->timeout) ||
        (p->anchored && (uint32_t)(now-p->anchor)>p->maximum))
        forget_periods(p,BIO_V2_EXPIRED);
}
static uint8_t accept_cycle(Periods *p,uint32_t at)
{
    uint32_t elapsed, sorted[5],i,j,swap,median,largest;
    /* 候选时刻与最后合法周期分开。非法候选不能更新合法周期的有效期。 */
    expire(p,at);
    if (!p->anchored) { p->anchor=at;p->anchored=1;p->reason=BIO_V2_NO_CYCLES;return 0; }
    elapsed=(uint32_t)(at-p->anchor);
    if (elapsed<p->minimum) return 0;
    if (elapsed>p->maximum) {
        forget_periods(p,BIO_V2_EXPIRED);p->anchor=at;p->anchored=1;return 0;
    }
    p->anchor=at;p->last_good=at;
    p->intervals[p->index]=elapsed;p->index=(p->index+1u)%5u;
    if (p->count<5u) p->count++;
    p->candidate_rate=0;p->reason=BIO_V2_NO_CYCLES;
    if (p->count<p->required) return 1;
    for (i=0;i<p->count;i++) sorted[i]=p->intervals[i];
    for (i=0;i<p->count;i++) for(j=i+1;j<p->count;j++)
        if(sorted[j]<sorted[i]) {swap=sorted[i];sorted[i]=sorted[j];sorted[j]=swap;}
    median=sorted[p->count/2u];largest=0;
    for(i=0;i<p->count;i++) {
        uint32_t difference=sorted[i]>median ? sorted[i]-median : median-sorted[i];
        if(difference>largest)largest=difference;
    }
    /* 最近窗口每个间隔都需在中位周期的20%内；不是只看数值是否在量程内。 */
    if(largest*100u>median*20u) {p->reason=BIO_V2_UNSTABLE;return 1;}
    p->candidate_rate=(60000u+median/2u)/median;p->reason=0;return 1;
}
static float filter_channel(Channel *c,int32_t raw,uint8_t respiration)
''',
         '''}
static void expire(Periods *p,uint32_t now)
{
    /* 可桥接漏检时锚点最长等两个最大间隔，否则慢心率下漏检一拍会先被判过期。 */
    uint32_t limit=(p->bridge && !p->bridged && p->count>=3u) ? 2u*p->maximum : p->maximum;
    if ((p->count!=0 && (uint32_t)(now-p->last_good)>p->timeout) ||
        (p->anchored && (uint32_t)(now-p->anchor)>limit))
        forget_periods(p,BIO_V2_EXPIRED);
}
static uint32_t window_median(const Periods *p,uint32_t sorted[5])
{
    uint32_t i,j,swap;
    for (i=0;i<p->count;i++) sorted[i]=p->intervals[i];
    for (i=0;i<p->count;i++) for(j=i+1;j<p->count;j++)
        if(sorted[j]<sorted[i]) {swap=sorted[i];sorted[i]=sorted[j];sorted[j]=swap;}
    return sorted[p->count/2u];
}
static uint8_t accept_cycle(Periods *p,uint32_t at)
{
    uint32_t elapsed, sorted[5],i,median,largest,tolerance;
    /* 候选时刻与最后合法周期分开。非法候选不能更新合法周期的有效期。 */
    expire(p,at);
    if (!p->anchored) { p->anchor=at;p->anchored=1;p->reason=BIO_V2_NO_CYCLES;return 0; }
    elapsed=(uint32_t)(at-p->anchor);
    if (elapsed<p->minimum) return 0;
    /* 漏检一拍：间隔为窗口中位数1.75–2.25倍时只前移锚点，不入窗、不改率值；
       不连续桥接，真实减半时下一间隔照常入窗并判不稳定。 */
    if (p->bridge && !p->bridged && p->count>=3u) {
        median=window_median(p,sorted);
        if (elapsed*4u>=median*7u && elapsed*4u<=median*9u) {
            p->anchor=at;p->last_good=at;p->bridged=1;return 0;
        }
    }
    if (elapsed>p->maximum) {
        forget_periods(p,BIO_V2_EXPIRED);p->anchor=at;p->anchored=1;return 0;
    }
    p->anchor=at;p->last_good=at;p->bridged=0;
    /* 滞回：上一判定有效才用放宽容差维持，首次锁定仍按20%，噪声难以偶然成锁。 */
    tolerance=p->candidate_rate ? p->tolerance : 20u;
    p->intervals[p->index]=elapsed;p->index=(p->index+1u)%5u;
    if (p->count<5u) p->count++;
    p->candidate_rate=0;p->reason=BIO_V2_NO_CYCLES;
    if (p->count<p->required) return 1;
    median=window_median(p,sorted);largest=0;
    for(i=0;i<p->count;i++) {
        uint32_t difference=sorted[i]>median ? sorted[i]-median : median-sorted[i];
        if(difference>largest)largest=difference;
    }
    /* 最近窗口每个间隔都需在中位周期的容差内（首次锁定20%，已有效的心搏按HEART_TOLERANCE维持）；不是只看数值是否在量程内。 */
    if(largest*100u>median*tolerance) {p->reason=BIO_V2_UNSTABLE;return 1;}
    p->candidate_rate=(60000u+median/2u)/median;p->reason=0;return 1;
}
static float filter_channel(Channel *c,int32_t raw,uint8_t respiration)
'''),
    )
    for anchor, replacement in replacements:
        text = replace_once(text, anchor, replacement)
    return text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--temp',action='store_true',help='离线构建UART4温度物表工程变体；不下载')
    parser.add_argument('--candidate-r6',action='store_true',help='离线构建带有R6微调度补偿的Node-B候选镜像；不下载')
    parser.add_argument('--temp-screen',action='store_true',help='复用旧USART3独立温度屏，仅构建显示绑定候选；不下载')
    parser.add_argument('--diag-reason', action='store_true', help='仅在构建副本的 B 屏探头页显示诊断原因码')
    parser.add_argument('--diag-home', action='store_true', help='在构建副本的主页信号质量和采集状态控件显示诊断')
    parser.add_argument('--diag-cap', action='store_true', help='只在主页采集状态控件显示诊断，保留质量数字')
    parser.add_argument('--algo-c1', action='store_true', help='在构建副本应用 R83 C1 算法')
    parser.add_argument('--algo-c2', action='store_true', help='在 C1 构建副本应用 R89 C2 算法')
    parser.add_argument('--dsp-library', type=Path, help='指定与冻结记录 SHA-256 一致的 CMSIS DSP 库')
    args=parser.parse_args()
    if args.temp_screen and not(args.temp and args.candidate_r6):parser.error('--temp-screen requires --temp --candidate-r6')
    if args.diag_reason and (not args.candidate_r6 or args.temp):
        parser.error('--diag-reason requires --candidate-r6 without --temp')
    if args.diag_home and not args.diag_reason:
        parser.error('--diag-home requires --diag-reason')
    if args.diag_cap and (not args.diag_reason or args.diag_home):
        parser.error('--diag-cap requires --diag-reason without --diag-home')
    if args.algo_c2 and not args.algo_c1:
        parser.error('--algo-c2 requires --algo-c1')
    if args.algo_c1 and not args.diag_cap:
        parser.error('--algo-c1 requires --diag-cap')
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
    dsp = args.dsp_library or Path('E:/medical-monitor-node-b-precan-closeout/node-b/build/arm-20261022T074340122429Z/firmware/CORE/arm_cortexM4lf_math.lib')
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
    if args.diag_reason:
        text = inject_diag_reason(text)
    if args.diag_home:
        text = inject_home_diag_reason(text)
    if args.diag_cap:
        text = inject_capture_diag_reason(text)
    page.write_text(text, encoding='utf-8')
    bio = project / 'HARDWARE/bio_v2.c'
    if args.algo_c1:
        algorithm = inject_algo_c1(bio.read_text(encoding='utf-8'))
        if args.algo_c2:
            algorithm = inject_algo_c2(algorithm)
            bio.write_text(algorithm, encoding='utf-8', newline='\n')
        else:
            bio.write_text(algorithm, encoding='utf-8')
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
    report['diag_reason_variant'] = args.diag_reason
    report['diag_home_variant'] = args.diag_home
    report['diag_cap_variant'] = args.diag_cap
    report['algo_c1_variant'] = args.algo_c1
    report['algo_c2_variant'] = args.algo_c2
    report['compiled_page_sha256']=sha(page)
    report['temperature_quantity']='nonhuman_object_surface_uncalibrated' if args.temp else 'INVALID'
    # 输出实际编译副本的头文件/工程输入SHA，覆盖屏幕钩子和C99选项，不只列出C文件。
    report['source_sha256'] = {p.relative_to(project).as_posix(): sha(p) for p in sorted(project.rglob('*'))
                              if p.is_file() and p.suffix.lower() in ('.c', '.h', '.s', '.uvprojx')}
    (out / 'executed-builder.py').write_bytes(Path(__file__).read_bytes())
    success = result.returncode == 0 and resource and '0 Error(s)' in log
    if success:
        binary = out / ('R89_C2_NODE_B.bin' if args.algo_c2 else 'R83_C1_NODE_B.bin' if args.algo_c1 else 'R80_HOME_DIAG_NODE_B.bin' if args.diag_home else 'R78_DIAG_REASON_NODE_B.bin' if args.diag_reason else 'B5_TEMP_SCREEN_NODE_B.bin' if args.temp_screen else 'B5_TEMP_NODE_B.bin' if args.temp else 'B4_NODE_B.bin')
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
        if success and args.diag_reason and binary.stat().st_size > 49152:
            success = False
            report['failure'] = 'DIAG_REASON_EXCEEDS_SECTOR0_2'
    report['status'] = 'PASS' if success else 'FAIL'
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(str(out.relative_to(ROOT)), report['status'])
    print(log[-6000:])
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
