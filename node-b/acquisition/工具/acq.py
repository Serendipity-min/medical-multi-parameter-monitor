# 公开副本：不再内置现场UID；硬件窗口须显式指定 --expected-uid。
"""标准采集命令入口；默认命令纯脱机，硬件采集必须显式 --execute。"""
import argparse
from pathlib import Path
import shutil
import sys

from acq_protocol import dump_strict_json, dumps_strict_json, load_strict_json, sha256_file
from acq_storage import (PROFILE, check_configuration, create_run, exclusive, offline_precheck,
                         require, seal_run, update_index, VERSION)
from acq_processing import compare_dataset, export_run, validate_run


def import_files(run, source, paused=None, paused_confirmed=False):
    """复制明确原件到新轮次；不运行旧脚本、不覆盖历史，不回填虚构设备身份。"""
    run, source = Path(run).resolve(), Path(source).resolve()
    check_configuration(run)
    require(source.is_dir() and not source.is_relative_to(run), '导入源目录无效')
    require(not (run/'raw_manifest.json').exists(), '轮次已经封存，禁止再次导入')
    sources = sorted(source.glob('slot_*.bin')) + sorted(source.glob('state_*.bin'))
    require(bool(sources), '没有 slot/state 原始块；CSV 不是此适配器的原始块')
    sources += sorted(source.glob('*.jlink')) + sorted(source.glob('*jlink.log'))
    with exclusive(run/'.capture.lock'):
        (run/'.capture.started').open('x').close()
        receipt = {'protocol_version': '1.0', 'run_id': run.name, 'mode': 'OFFLINE_IMPORT',
                   'status': 'IMPORT_STARTED', 'identity_status': 'UNKNOWN',
                   'reason': '预期 profile 不证明历史设备身份；不读取当前板卡补造历史身份',
                   'hardware_operations': [], 'target_end_state': 'NOT_OPERATED',
                   'paused_snapshot_evidence': None, 'sources': []}
        failure = None
        try:
            for file in sources:
                target = run/'raw'/file.name
                require(not target.exists(), '原件目标已存在')
                shutil.copyfile(file, target)
                receipt['sources'].append({'source': str(file), 'target': target.relative_to(run).as_posix(),
                                           'sha256': sha256_file(target)})
            if paused:
                require(paused_confirmed, '尾段导入需要明确暂停证据声明；否则只导入 live 观察')
                file = Path(paused).resolve()
                require(file.is_file() and file.stat().st_size == 131072, '暂停 RAM 长度错误')
                target = run/'raw/final-paused-ram.bin'
                require(not target.exists(), '尾段原件已存在')
                shutil.copyfile(file, target)
                receipt['paused_snapshot_evidence'] = 'IMPORTED_DECLARATION'
                receipt['sources'].append({'source': str(file), 'target': 'raw/final-paused-ram.bin',
                                           'sha256': sha256_file(target)})
            receipt['status'] = 'IMPORT_COMPLETED'
        except BaseException as exc:
            receipt.update(status='IMPORT_INCOMPLETE', error=str(exc))
            failure = exc
        finally:
            dump_strict_json(receipt, run/'acquisition_receipt.json')
            seal_run(run)
            update_index(run, reason=receipt['status'])
        if failure:
            raise failure
    return export_run(run)


def main(argv=None):
    parser = argparse.ArgumentParser(description='acq 标准采集工具 v1：身份冻结、原件保留、双通道导出与批量表征')
    parser.add_argument('--version', action='version', version=VERSION)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='创建唯一采集轮次，不连接硬件')
    init.add_argument('--dataset', type=Path, required=True)
    init.add_argument('--sample', required=True, help='匿名样本编号')
    init.add_argument('--condition', required=True, help='条件编号')
    init.add_argument('--input-kind', required=True, choices=['ACTIVE_HARDWARE_SIMULATOR','INTERNAL_TEST_SIGNAL',
                             'SOFTWARE_FIXTURE','PASSIVE_PHANTOM','HUMAN_DECLARED','UNKNOWN'])
    init.add_argument('--fixture', required=True, help='实际输入设备或来源说明，不等于核验资料')
    init.add_argument('--profile', type=Path, default=PROFILE)
    init.add_argument('--duration', type=int, default=150)
    init.add_argument('--warmup', type=int, default=30)
    init.add_argument('--expected-uid', default='')
    init.add_argument('--hr-setpoint', type=float, help='已知模拟器设定心率，仅保存声明，不当作独立测量')
    init.add_argument('--resp-setpoint', type=float, help='已知模拟器设定呼吸率，未知时省略')
    for name in ['precheck','capture','import','validate','analyze']:
        command = sub.add_parser(name)
        command.add_argument('--run', type=Path, required=True)
        if name == 'precheck':
            for flag in ['bin','elf','symbols']:
                command.add_argument('--'+flag, type=Path)
        elif name == 'capture':
            command.add_argument('--execute', action='store_true', help='缺省只显示计划，不访问硬件')
            command.add_argument('--confirm-no-human', action='store_true', help='确认电极未连接任何活人')
            command.add_argument('--jlink', type=Path, default=Path('E:/stm32/j_link/JLink_V512/JLink.exe'))
        elif name == 'import':
            command.add_argument('--source', type=Path, required=True)
            command.add_argument('--paused-ram', type=Path)
            command.add_argument('--paused-snapshot-confirmed', action='store_true')
    compare = sub.add_parser('compare')
    compare.add_argument('--dataset', type=Path, required=True)
    compare.add_argument('--output', type=Path, required=True)
    compare.add_argument('--purpose', choices=['integrity','waveform'], default='integrity')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            run = create_run(args.dataset, args.sample, args.condition, args.input_kind, args.fixture,
                             args.profile, args.duration, args.warmup, args.expected_uid,
                             hr_setpoint=args.hr_setpoint, resp_setpoint=args.resp_setpoint)
            result = {'run': str(run), 'status': 'PREPARED', 'next': 'precheck --run <run>'}
        elif args.command == 'precheck':
            result = offline_precheck(args.run, args.bin, args.elf, args.symbols)
        elif args.command == 'capture':
            # 只显示计划时不导入硬件后端，避免任何意外设备连接。
            result = offline_precheck(args.run)
            if args.execute:
                from acq_swd import capture_run
                capture_run(args.run, args.jlink, args.confirm_no_human)
                analysis, quality = export_run(args.run)
                result = {'analysis': str(analysis), 'quality': quality}
            else:
                result['status'] = 'PLAN_ONLY_NO_HARDWARE'
                result['execute_requirements'] = '--execute --confirm-no-human；仅非人体台架'
        elif args.command == 'import':
            analysis, quality = import_files(args.run, args.source, args.paused_ram, args.paused_snapshot_confirmed)
            result = {'analysis': str(analysis), 'quality': quality}
        elif args.command == 'analyze':
            analysis, quality = export_run(args.run)
            result = {'analysis': str(analysis), 'quality': quality}
        elif args.command == 'validate':
            result = validate_run(args.run)
        else:
            result = {'output': str(compare_dataset(args.dataset, args.output, args.purpose))}
        print(dumps_strict_json(result))
        if isinstance(result, dict) and result.get('quality', {}).get('integrity', {}).get('status') in {'INCOMPLETE','FAIL'}:
            return 2
        return 0
    except (ValueError, OSError, KeyError, RuntimeError, TimeoutError) as exc:
        print(dumps_strict_json({'status': 'STOP_OR_ERROR', 'reason': str(exc)}), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('已中止；不追加恢复命令，请查看本轮回执的目标状态。', file=sys.stderr)
        return 130


if __name__ == '__main__':
    # Windows 控制台统一 UTF-8，仅影响文字显示，不转换原始二进制日志。
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())
