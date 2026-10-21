"""新A专用受限维护；默认只生成离线计划，实板入口必须绑定当次授权卡。

不复用旧49888B下载脚本，不发送erase/复位/SetPC/MSP/VTOR/go命令。
原件、UID、J-Link完整输出仅保存在仓库外的受限窗口目录。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
IMAGE_SHA = 'f59b76ef865c373c6df62aa09aea958597687f6d46b17c402ceb7126ca8f60d6'
OLD_SHA = '506423dc295318a8de730d0d6b5100fc4ef199c349ee3acd2fbba350bf576f88'
FLASH = 0x08000000
SIZE = 0x100000
BOUND = 0x10000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plan(image):
    data = image.read_bytes()
    sp, reset = int.from_bytes(data[:4], 'little'), int.from_bytes(data[4:8], 'little')
    if len(data) != 50084 or sha(data) != IMAGE_SHA:
        raise ValueError('NEW_A_IMAGE_MISMATCH')
    if not (0x20000000 < sp <= 0x20020000 and FLASH < reset < FLASH + len(data) and reset & 1):
        raise ValueError('A_VECTOR_INVALID')
    return {'role': 'A', 'image_sha256': IMAGE_SHA, 'bytes': len(data),
            'start': FLASH, 'end_exclusive': FLASH + len(data), 'erase_sectors': [0, 1, 2, 3],
            'backup_bytes': SIZE, 'protected_after': FLASH + BOUND,
            'execution': 'HALT_ONLY_NORMAL_COLD_BOOT_BY_OWNER', 'mass_erase': False}


def authorize(card, action, image):
    p = plan(image)
    # 卡片必须逐项绑定工具、提交、设备角色及有效窗口，不能把总合同当Flash授权。
    if card.get('auth_id') != 'AUTH-AC-A-FLASH' or card.get('approved_by_owner') is not True:
        raise ValueError('OWNER_WINDOW_REQUIRED')
    if card.get('action') != action or card.get('image_sha256') != p['image_sha256']:
        raise ValueError('AUTH_ACTION_OR_IMAGE_MISMATCH')
    if card.get('tool_sha256') != sha(Path(__file__).read_bytes()):
        raise ValueError('AUTH_TOOL_CHANGED')
    expiry = datetime.fromisoformat(card['expires_utc'])
    if expiry.tzinfo is None or datetime.now(timezone.utc) >= expiry:
        raise ValueError('AUTH_WINDOW_EXPIRED')
    if card.get('field_state') != 'A_ONLY_C_OFF_CAN_ISOLATED_NO_PROBE_CUFF':
        raise ValueError('FIELD_STATE_REQUIRED')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if card.get('source_commit') != head:
        raise ValueError('AUTH_SOURCE_CHANGED')
    return p


class Bridge:
    def __init__(self, directory):
        self.directory = directory
        self.index = 0

    def execute(self, lines):
        # 命令为模块内部生成的固定集合；无通用CLI透传，也没有独立扇区擦除命令。
        if not all(s in ('connect', 'h', 'q') or s.startswith(('savebin ', 'loadbin ',
                   'verifybin ', 'w4 0xE0042008 ')) for s in lines):
            raise ValueError('COMMAND_OUTSIDE_A_WINDOW')
        self.index += 1
        text = '\n'.join(lines) + '\n'
        stem = self.directory / ('jlink-' + str(self.index))
        stem.with_suffix('.commands').write_text(text, encoding='ascii')
        r = subprocess.run(['D:/keil/ARM/Segger/JLink.exe', '-device', 'STM32F407ZG',
            '-if', 'SWD', '-speed', '1000'], input=text.encode('ascii'), capture_output=True,
            timeout=90, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        stem.with_suffix('.raw.log').write_bytes(r.stdout + r.stderr)
        if r.returncode:
            raise RuntimeError('JLINK_PROCESS_NONZERO')


class Window:
    def __init__(self, directory, bridge, expected_uid):
        self.directory, self.bridge, self.uid = directory, bridge, expected_uid
        if len(expected_uid) != 12:
            raise ValueError('EXTERNAL_A_IDENTITY_REQUIRED')

    def read(self, label, specs, extra=()):
        lines = ['connect', 'h', *extra]
        for name, address, length in specs:
            target = self.directory / (label + '-' + name + '.bin')
            if target.exists() or any(c in target.as_posix() for c in ('\n', '\r', ',', ' ')):
                raise ValueError('PRIVATE_OUTPUT_PATH_INVALID_OR_OCCUPIED')
            lines.append(f'savebin {target.as_posix()}, {hex(address)}, {hex(length)}')
        self.bridge.execute([*lines, 'q'])
        data = {}
        for name, _, length in specs:
            value = (self.directory / (label + '-' + name + '.bin')).read_bytes()
            if len(value) != length:
                raise RuntimeError('READ_LENGTH_MISMATCH')
            data[name] = value
        return data

    def identity(self, label):
        value = self.read(label, [('chip', 0xE0042000, 4), ('size', 0x1FFF7A22, 2),
            ('uid', 0x1FFF7A10, 12), ('options', 0x1FFFC000, 16),
            ('optcr', 0x40023C14, 4), ('freeze', 0xE0042008, 4)])
        if int.from_bytes(value['chip'], 'little') & 0xFFF != 0x413 or int.from_bytes(value['size'], 'little') != 1024:
            raise RuntimeError('WRONG_CHIP_OR_CAPACITY')
        if value['uid'] != self.uid:
            raise RuntimeError('WRONG_A_IDENTITY')
        if (int.from_bytes(value['optcr'], 'little') >> 8) & 255 != 0xAA:
            raise RuntimeError('RDP_PROTECTED_STOP')
        return value

    def program(self, image):
        plan(image)
        before_id = self.identity('before')
        freeze = int.from_bytes(before_id['freeze'], 'little') | (1 << 12)
        # 仅冻结调试暂停期间的IWDG；保存旧寄存器并在成功读回后恢复，不改变应用喂狗。
        first = self.read('first', [('flash', FLASH, SIZE)], [f'w4 0xE0042008 {hex(freeze)}'])['flash']
        second = self.read('second', [('flash', FLASH, SIZE)])['flash']
        if first != second:
            raise RuntimeError('CURRENT_BACKUP_DOUBLE_READ_MISMATCH')
        if sha(first[:49888]) != OLD_SHA:
            raise RuntimeError('CURRENT_A_APPLICATION_UNKNOWN_STOP')
        identity = self.identity('prewrite')
        if any(identity[k] != before_id[k] for k in ('uid', 'chip', 'size', 'options', 'optcr')):
            raise RuntimeError('PREWRITE_IDENTITY_CHANGED')
        # 每次loadbin前先把备份落盘并再次回读；备份在失败路径也保留，恢复另行授权。
        proof = {'backup_sha256': sha(first), 'bytes': SIZE, 'outside_64k_sha256': sha(first[BOUND:]),
                 'options_sha256': sha(before_id['options']), 'independent_reads_match': True,
                 'image_sha256': IMAGE_SHA, 'restore_state': 'REQUIRES_SEPARATE_OWNER_RESTORE_APPROVAL'}
        (self.directory / 'fresh-backup.json').write_text(json.dumps(proof, indent=2))
        if (self.directory / 'first-flash.bin').read_bytes() != first or (self.directory / 'second-flash.bin').read_bytes() != first:
            raise RuntimeError('DISK_BACKUP_CHANGED')
        data = image.read_bytes()
        if sha(data) != IMAGE_SHA:
            raise RuntimeError('IMAGE_CHANGED_BEFORE_LOAD')
        after = self.read('after', [('flash', FLASH, SIZE)],
            [f'loadbin {image.as_posix()}, 0x08000000', 'h', f'verifybin {image.as_posix()}, 0x08000000'])['flash']
        after_id = self.identity('after-id')
        if after[:len(data)] != data or after[BOUND:] != first[BOUND:]:
            raise RuntimeError('READBACK_OR_OUTSIDE_SECTORS_CHANGED_STOP')
        if any(after_id[k] != before_id[k] for k in ('uid', 'chip', 'size', 'options', 'optcr')):
            raise RuntimeError('AFTER_IDENTITY_OR_OPTIONS_CHANGED_STOP')
        self.bridge.execute(['connect', 'h', f'w4 0xE0042008 {hex(int.from_bytes(before_id["freeze"], "little"))}', 'q'])
        return {**proof, 'exit_code': 0, 'state': 'READBACK_MATCH_HALTED_COLD_BOOT_PENDING',
                'after_flash_sha256': sha(after), 'normal_cold_boot': 'NOT_OBSERVED',
                'outside_sectors_unchanged': True, 'options_unchanged': True}

    def restore(self, backup_directory, expected_sha):
        backup_directory=Path(backup_directory)
        first=(backup_directory/'first-flash.bin').read_bytes()
        second=(backup_directory/'second-flash.bin').read_bytes()
        proof=json.loads((backup_directory/'fresh-backup.json').read_text())
        if len(first)!=SIZE or first!=second or sha(first)!=expected_sha or proof['backup_sha256']!=expected_sha:
            raise RuntimeError('FRESH_RESTORE_BACKUP_MISMATCH')
        identity=self.identity('restore-before')
        if sha(identity['options'])!=proof['options_sha256']:
            raise RuntimeError('RESTORE_OPTIONS_IDENTITY_CHANGED')
        freeze=int.from_bytes(identity['freeze'],'little')|(1<<12)
        current=self.read('restore-current',[('flash',FLASH,SIZE)],
            [f'w4 0xE0042008 {hex(freeze)}'])['flash']
        if current[BOUND:]!=first[BOUND:]:
            raise RuntimeError('RESTORE_OUTSIDE_SCOPE_CHANGED_STOP')
        # 只生成并加载本窗口原件的前64KiB，永不把1MiB兜底原件直接loadbin。
        image=self.directory/'restore-sector0-3.bin';image.write_bytes(first[:BOUND])
        after=self.read('restore-after',[('flash',FLASH,SIZE)],
            [f'loadbin {image.as_posix()}, 0x08000000','h',f'verifybin {image.as_posix()}, 0x08000000'])['flash']
        final_identity=self.identity('restore-after-id')
        if after!=first or any(identity[k]!=final_identity[k] for k in ('uid','chip','size','options','optcr')):
            raise RuntimeError('RESTORE_READBACK_OR_IDENTITY_CHANGED')
        self.bridge.execute(['connect','h',f'w4 0xE0042008 {hex(int.from_bytes(identity["freeze"],"little"))}','q'])
        return {'exit_code':0,'state':'ORIGINAL_A_SECTOR0_3_RESTORED_HALTED',
                'backup_sha256':expected_sha,'outside_sectors_unchanged':True,
                'normal_cold_boot':'NOT_OBSERVED'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('plan', 'program', 'restore'))
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--auth', type=Path)
    parser.add_argument('--private-dir', type=Path)
    parser.add_argument('--a-uid-file', type=Path)
    parser.add_argument('--fresh-backup-dir',type=Path)
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps(plan(args.image), indent=2))
        return 0
    card = json.loads(args.auth.read_text())
    authorize(card, args.action, args.image)
    directory = args.private_dir.resolve()
    if directory.is_relative_to(ROOT) or not directory.is_dir() or any(directory.iterdir()):
        raise ValueError('EMPTY_PRIVATE_WINDOW_OUTSIDE_REPO_REQUIRED')
    try:
        window=Window(directory, Bridge(directory), args.a_uid_file.read_bytes())
        if args.action=='restore':
            if card.get('restore_approved_by_owner') is not True or not card.get('fresh_backup_sha256'):
                raise ValueError('SEPARATE_FRESH_BACKUP_RESTORE_APPROVAL_REQUIRED')
            result=window.restore(args.fresh_backup_dir,card['fresh_backup_sha256'])
        else:result=window.program(args.image)
    except Exception as error:
        # 原始底层异常可能含UID/路径/内容，不带入Git或控制台。
        result = {'exit_code': 1, 'state': 'STOPPED_NO_AUTO_RESTORE', 'failure_type': type(error).__name__}
    (directory / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
