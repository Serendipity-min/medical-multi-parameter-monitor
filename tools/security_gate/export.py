"""将统一执行器及项目接入配置复制到指定 Git 工作树；不创建分支、提交或推送。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from common import HERE, dump, git, sha

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--profile', default='generic')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    target = args.target.resolve()
    git(target, 'rev-parse', '--show-toplevel')
    source_root = HERE.parents[1]
    if target == source_root:
        parser.error('export target must differ from source toolkit repository')
    skill = source_root / 'skills/security-gate'
    if not skill.is_dir():
        skill = source_root / '.agents/skills/security-gate'
    files = {}
    for source, dest in ((HERE, Path('tools/security_gate')), (skill, Path('.agents/skills/security-gate'))):
        for file in source.rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                files[dest / file.relative_to(source)] = file
    templates = HERE / 'templates'
    files[Path('.github/workflows/security-gate.yml')] = templates / 'security-gate.yml'
    files[Path('.github/dependabot.yml')] = templates / ('dependabot-medical.yml' if args.profile == 'medical-monitor' else 'dependabot-generic.yml')
    files[Path('.security-gate.json')] = HERE / 'profiles' / (args.profile + '.json')
    previous_manifest = target / 'tools/security_gate/export-manifest.json'
    previous = json.loads(previous_manifest.read_text()).get('files', {}) if previous_manifest.exists() else {}
    # 仅覆盖本工具已导出的文件；既有用户配置冲突则停止，避免悄悄改项目策略。
    for name, source in files.items():
        dest = target / name
        if not dest.resolve().is_relative_to(target):
            raise ValueError('export path escapes target')
        if dest.exists() and dest.read_bytes() != source.read_bytes():
            if previous.get(name.as_posix()) != sha(dest):
                raise ValueError('existing project file conflicts: ' + name.as_posix())
    if not args.apply:
        print(json.dumps({'mode': 'plan', 'files': len(files), 'profile': args.profile}))
        return 0
    for name, source in files.items():
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    dump(target / 'tools/security_gate/export-manifest.json',
         {'toolkit_commit': git(source_root, 'rev-parse', 'HEAD'), 'profile': args.profile,
          'files': {name.as_posix(): sha(source) for name, source in files.items()}})
    print(json.dumps({'exported_files': len(files), 'profile': args.profile, 'commit_or_push_performed': False}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
