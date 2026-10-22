"""C离线台架的显式单次写入/原sector0恢复；默认plan不接触J-Link。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from tools import h3_c_jlink as base
from gateway.physical_can.r2_config_record import validate

ROOT = Path(__file__).resolve().parents[2]
CURRENT_IMAGE = 'b9b25b186c3b40d62b4a1c1919e09f27b639806271a3b20ae7fc80ea4cda1efe'
CURRENT_FULL = '49d3fad5040b25b746905d5c1468bff4d5be5a4f13197286ce215e0711798fb4'
CURRENT_RECORD = '395c6a36d7c4a636b34a72eacd1ccc2a2fc7f025df7089f3d94e1d2de14c5a3b'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def plan(image):
    data = image.read_bytes()
    manifest_path = sorted((ROOT/'doc/VOICE/evidence').glob('*offline-bench.json'))[-1]
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['exit_code'] or manifest['image']['sha256'] != sha(data) or manifest['image']['erase_sectors'] != [0]:
        raise ValueError('VOICE_IMAGE_MANIFEST_MISMATCH')
    if not 0 < len(data) <= 16384:
        raise ValueError('VOICE_IMAGE_OUTSIDE_SECTOR0')
    return {'role': 'C', 'image_bytes': len(data), 'image_sha256': sha(data),
            'write_block_bytes': 16384, 'write_block_sha256': sha(data.ljust(16384, b'\xff')),
            'write_start': 0x08000000, 'write_end_exclusive': 0x08004000, 'erase_sectors': [0],
            'preserve_sectors': list(range(1,12)), 'options_write': False, 'mass_erase': False,
            'network': 'NOT_LINKED', 'default_audio': 'DISABLED', 'trigger': 'WK_UP_PA0_SINGLE_PRESS',
            'backup_bytes_each': 65536, 'backup_reads': 2,
            'current_image_sha256': CURRENT_IMAGE, 'current_64k_sha256': CURRENT_FULL,
            'config_generation': 3, 'config_record_sha256': CURRENT_RECORD,
            'automatic_retry': False, 'automatic_restore': False, 'automatic_go': False,
            'temporary_debug_IWDG_freeze': 'BIT12_RESTORE_VERIFIED',
            'jlink_sha256': sha(base.JLINK.read_bytes())}


class Window(base.Window):
    def controller(self, label):
        data = self.read(label, [('flash-status',0x40023c0c,8)])['flash-status']
        sr, cr = int.from_bytes(data[:4],'little'), int.from_bytes(data[4:],'little')
        # 拒绝BSY/错误位和残留PG/SER/MER/PSIZE；不靠清状态或解锁绕过异常。
        if sr & 0x100f2 or cr != 0x80000000:
            raise RuntimeError('VOICE_FLASH_CONTROLLER_NOT_CLEAN_LOCKED_STOP')
        return data

    def program(self, image):
        scope = plan(image)
        identity = self.identity_read('identity-before')
        protected = self.protection('protected-before')
        controller = self.controller('controller-before')
        freeze = int.from_bytes(identity['freeze'], 'little') | (1 << 12)
        first = self.read('first', [('flash64k', 0x08000000, 65536)],
                          [f'w4 0xE0042008 {hex(freeze)}'])['flash64k']
        second = self.read('second', [('flash64k', 0x08000000, 65536)])['flash64k']
        if first != second or sha(first) != CURRENT_FULL or sha(first[:43172]) != CURRENT_IMAGE:
            raise RuntimeError('VOICE_CURRENT_OR_DOUBLE_BACKUP_MISMATCH_STOP')
        record = first[49152:49152+336]
        if sha(record) != CURRENT_RECORD or validate(record) != 3:
            raise RuntimeError('VOICE_CONFIG_GENERATION_MISMATCH_STOP')
        original = self.private/'original-sector0.bin'
        original.write_bytes(first[:16384])
        if original.read_bytes() != first[:16384]: raise RuntimeError('VOICE_BACKUP_DISK_MISMATCH')
        block = image.read_bytes().ljust(16384, b'\xff')
        if sha(block) != scope['write_block_sha256']: raise RuntimeError('VOICE_CANDIDATE_CHANGED')
        blockpath = self.private/'candidate-sector0.bin'; blockpath.write_bytes(block)
        if blockpath.read_bytes() != block: raise RuntimeError('VOICE_CANDIDATE_DISK_MISMATCH')
        # 显式提供完整16KiB扇区，避免Flash工具的局部加载策略影响尾部字节。
        (self.private/'write-attempt.json').write_text(json.dumps(scope, indent=2))
        after = self.read('after', [('flash64k', 0x08000000, 65536)],
            [f'loadbin {blockpath.as_posix()}, 0x08000000', 'h', f'verifybin {blockpath.as_posix()}, 0x08000000'])['flash64k']
        if after != block+first[16384:]: raise RuntimeError('VOICE_READBACK_OR_PRESERVED_SECTOR_CHANGED')
        if self.protection('protected-after') != protected: raise RuntimeError('VOICE_PROTECTED_CHANGED')
        if self.controller('controller-after') != controller: raise RuntimeError('VOICE_CONTROLLER_CHANGED')
        final = self.identity_read('identity-after')
        if any(identity[k] != final[k] for k in ['chip','size','uid','options']): raise RuntimeError('VOICE_IDENTITY_CHANGED')
        restored = self.read('debug-restored', [('freeze',0xE0042008,4)],
            [f'w4 0xE0042008 {hex(int.from_bytes(identity["freeze"],"little"))}'])['freeze']
        if restored != identity['freeze']: raise RuntimeError('VOICE_DEBUG_FREEZE_RESTORE_FAILED')
        proof = {'exit_code': 0, 'action': 'VOICE_BENCH_LOAD_VERIFIED', 'scope': scope,
                 'before_64k_sha256': sha(first), 'after_64k_sha256': sha(after),
                 'original_sector0_sha256': sha(first[:16384]), 'protected_unchanged': True,
                 'target_execution': 'HALTED_NO_GO', 'audio_heard': 'NOT_OBSERVED', 'identity_match': True}
        (self.private/'program-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
        return proof

    def restore(self, prior):
        proof = json.loads((prior/'program-proof.json').read_text(encoding='utf-8'))
        identity = self.identity_read('restore-identity-before'); protected = self.protection('restore-protected-before')
        controller = self.controller('restore-controller-before')
        now = self.read('restore-first', [('flash64k',0x08000000,65536)])['flash64k']
        again = self.read('restore-second', [('flash64k',0x08000000,65536)])['flash64k']
        if now != again or sha(now) != proof['after_64k_sha256']: raise RuntimeError('VOICE_RESTORE_CURRENT_CHANGED')
        original = (prior/'first-flash64k.bin').read_bytes()
        block = (prior/'original-sector0.bin').read_bytes()
        if sha(original) != CURRENT_FULL or block != original[:16384] or now[16384:] != original[16384:]:
            raise RuntimeError('VOICE_RESTORE_ORIGINAL_CHANGED')
        blockpath = self.private/'restore-sector0.bin'; blockpath.write_bytes(block)
        after = self.read('restore-after', [('flash64k',0x08000000,65536)],
            [f'loadbin {blockpath.as_posix()}, 0x08000000', 'h', f'verifybin {blockpath.as_posix()}, 0x08000000'])['flash64k']
        if after != original or self.protection('restore-protected-after') != protected:
            raise RuntimeError('VOICE_RESTORE_FAILED_STOP')
        if self.controller('restore-controller-after') != controller: raise RuntimeError('VOICE_RESTORE_CONTROLLER_CHANGED')
        final = self.identity_read('restore-identity-after')
        if any(identity[k] != final[k] for k in ['chip','size','uid','options']): raise RuntimeError('VOICE_RESTORE_IDENTITY_CHANGED')
        return {'exit_code':0, 'action':'ORIGINAL_SECTOR0_RESTORED', 'actual_64k_sha256':sha(after),
                'config_unchanged':True, 'protected_unchanged':True, 'target_execution':'HALTED_NO_GO'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['plan','program','restore'])
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--auth', type=Path); p.add_argument('--identity-source', type=Path)
    p.add_argument('--private-dir', type=Path); p.add_argument('--prior-dir', type=Path)
    a = p.parse_args(); scope = plan(a.image)
    if a.action == 'plan': print(json.dumps(scope, indent=2)); return 0
    # 授权卡可能含中文现场说明；Windows默认GBK不得改变UTF-8 JSON的解释。
    card = json.loads(a.auth.read_text(encoding='utf-8'))
    expiry = datetime.fromisoformat(card['expires_utc'])
    if expiry.tzinfo is None or datetime.now(timezone.utc) >= expiry: raise ValueError('VOICE_WINDOW_EXPIRED')
    if card.get('auth_id') != 'AUTH-VOICE-C-OFFLINE-BENCH-1' or card.get('approved_by_owner') is not True:
        raise ValueError('VOICE_EXPLICIT_HARDWARE_APPROVAL_REQUIRED')
    if card.get('scope') != scope or card.get('action') != a.action or card.get('tool_sha256') != sha(Path(__file__).read_bytes()):
        raise ValueError('VOICE_SCOPE_CHANGED')
    if card.get('field_state') != 'C_ONLY_A_B_OFF_NO_HUMAN_ESP_DISCONNECTED_BOOT_GND_SWD_C':
        raise ValueError('VOICE_FIELD_STATE_NOT_CONFIRMED')
    if card.get('voltage_pinout_gate_passed') is not True or card.get('speaker_8ohm_1w_short_test_owner_override') is not True:
        raise ValueError('VOICE_ELECTRICAL_GATE_NOT_CONFIRMED')
    if card.get('source_commit') != subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip():
        raise ValueError('VOICE_SOURCE_CHANGED')
    if a.identity_source.resolve().is_relative_to(ROOT) or sha(a.identity_source.read_bytes()) != card.get('identity_source_sha256'):
        raise ValueError('VOICE_PRIVATE_IDENTITY_CHANGED')
    private = a.private_dir.resolve()
    allowed_private = Path('E:/medical-monitor-c-voice-private').resolve()
    if not private.is_relative_to(allowed_private) or private == allowed_private or not private.is_dir() or any(private.iterdir()):
        raise ValueError('VOICE_EMPTY_RESTRICTED_PRIVATE_DIRECTORY_REQUIRED')
    # 写入前落一份单次执行标记；失败不自动重试，也不擅自恢复。
    (private/'single-attempt.json').write_text(json.dumps({'action':a.action,'scope':scope},indent=2))
    try:
        window = Window(private, base.Bridge(private), base.external_identity(a.identity_source))
        result = window.program(a.image) if a.action == 'program' else window.restore(a.prior_dir)
    except Exception as exc:
        result = {'exit_code':1, 'state':'STOPPED_NO_AUTO_RETRY', 'error_type':type(exc).__name__}
        if isinstance(exc,(ValueError,RuntimeError)): result['error_code'] = str(exc)
    (private/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2)); return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
