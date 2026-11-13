"""sector3离线可测状态机与原始DAP桥；不加载SDK，不包含连接入口。"""
from contextlib import contextmanager
import time

import b5_sector3_plan as plan

BASE, END, COMMIT = 0x0800c000, 0x08010000, 0x0800c014
ACR, KEYR, SR, CR = 0x40023c00, 0x40023c04, 0x40023c0c, 0x40023c10
LOCK, BUSY, ERRORS = 0x80000000, 0x10000, 0xf2
ERASE_READY, ERASE_START, PROGRAM = 0x21a, 0x1021a, 0x201
COMMIT_VALUE = 0x54494d43
FULL_FLASH_BYTES = 1048576
FULL_READ_S, BUDGET_FACTOR = 26.5, 1.20
ERASE_WAIT_S, COMMIT_WAIT_S = 45, 5
PROGRAM_WORD_S, CONTROL_AND_CLOSE_S = 0.05, 10


def require(ok, reason):
    if not ok: raise ValueError(reason)


class DapBridge:
    """AP索引0/1/3按ADI word索引推导；真实桥必须先只读交叉核验，尚未实板验证。"""
    def __init__(self, bus):
        self.bus = bus; self.guard = None; self.proven = False; self.state_restored = True

    @contextmanager
    def window(self, bank=0):
        self.state_restored = False
        csw = tar = None
        try:
            # SWD DP offset8读是RESEND而非SELECT，绝不读取它冒充原SELECT。
            self.bus.write(2, False, 0)
            csw, tar = self.bus.read(0, True), self.bus.read(1, True)
            self.bus.write(2, False, bank)
            yield
        finally:
            # 恢复可读CSW/TAR，SELECT只规范化为AP0/bank0，不声称恢复未知旧值。
            if csw is not None and tar is not None:
                self.bus.write(2, False, 0)
                self.bus.write(1, True, tar)
                self.bus.write(0, True, csw)
            self.bus.write(2, False, 0)
            self.state_restored = True

    def read32(self, address):
        require(address % 4 == 0, 'DAP_READ_ALIGNMENT')
        allowed = address in (ACR, SR, CR, 0xe000ed00) or 0x08000000 <= address < 0x08000040
        require(allowed, 'DAP_READ_SCOPE')
        with self.window():
            csw = self.bus.read(0, True)
            self.bus.write(0, True, (csw & ~0x37) | 2)
            self.bus.write(1, True, address)
            return self.bus.read(3, True)

    def write32(self, address, value):
        require(self.proven and self.guard is not None, 'DAP_READONLY_PROBE_REQUIRED')
        self.guard(address, value)
        with self.window():
            csw = self.bus.read(0, True)
            self.bus.write(0, True, (csw & ~0x37) | 2)
            self.bus.write(1, True, address)
            self.bus.grant_target_write(address, value)
            try: self.bus.write(3, True, value)
            finally: self.bus.grant_target_write(None, None)

    def probe(self, sdk_cpuid, sdk_header, sdk_cr, sdk_sr):
        self.proven = False
        with self.window(0xf0): identifier = self.bus.read(3, True)
        require(identifier not in (0, 0xffffffff) and (identifier >> 13) & 15 == 8 and identifier & 15 == 1,
                'DAP_NOT_AHB_MEMAP')
        require(self.read32(0xe000ed00) == sdk_cpuid, 'DAP_CPUID_CROSSCHECK')
        header = b''.join(self.read32(0x08000000+i).to_bytes(4, 'little') for i in range(0, 64, 4))
        require(header == sdk_header, 'DAP_FLASH_HEADER_CROSSCHECK')
        require(self.read32(CR) == sdk_cr and self.read32(SR) == sdk_sr, 'DAP_FLASH_CONTROL_CROSSCHECK')
        require(self.state_restored, 'DAP_STATE_NOT_RESTORED')
        self.proven = True
        return {'AHB_MEMAP': True, 'CPUID_and_Flash_header_match_SDK': True,
                'control_registers_match_SDK': True, 'AP_CSW_TAR_restored_SELECT_canonical0': True,
                'native_hardware_validation': 'NOT_ESTABLISHED_BY_OFFLINE_TESTS'}


class Engine:
    def __init__(self, io, before, after, uncommitted_sector, options, phase, timeout_s=180,
                 started_monotonic=None, full_read_s=FULL_READ_S):
        require(phase in ('provision', 'restore_config', 'commit_resume'), 'SECTOR3_PHASE')
        self.resume = phase == 'commit_resume'
        require(len(before) == len(after) == 1048576 and len(options) == 16, 'SECTOR3_IMAGES')
        require(len(uncommitted_sector) == 16384, 'SECTOR3_UNCOMMITTED_SIZE')
        require(before[:49152] == after[:49152] and before[65536:] == after[65536:], 'SECTOR3_OUTSIDE_REGION_CHANGED')
        final_sector = after[49152:65536]
        require(uncommitted_sector[:20] + uncommitted_sector[24:] == final_sector[:20] + final_sector[24:]
                and uncommitted_sector[20:24] == b'\xff'*4, 'SECTOR3_PRECOMMIT_LAYOUT')
        require(final_sector[336:] == before[49152+336:65536], 'SECTOR3_TAIL_DRIFT')
        self.validate_transition(phase,before[49152:49152+336],final_sector[:336])
        self.io, self.before, self.after, self.stage, self.options = io, before, after, uncommitted_sector, options
        self.phase = 'PREFLIGHT'; self.operation = phase; self.erases = 0; self.commits = 0
        self.keys = []; self.words = []; self.stage_verified = False; self.original_acr = None
        self.expected_words = [] if self.resume else [
            (BASE+i, int.from_bytes(uncommitted_sector[i:i+4], 'little'))
            for i in range(0, END-BASE, 4) if i != COMMIT-BASE and uncommitted_sector[i:i+4] != b'\xff'*4]
        self.cr_history = []; self.cr_phase_counts = {}; self.acr_history = []; self.erase_completed = False
        self.started = time.monotonic() if started_monotonic is None else started_monotonic
        self.timeout_s = timeout_s
        self.full_read_s = max(FULL_READ_S, full_read_s)
        self.prewrite_budget = None
        self.io.bind_guard(self.authorize_write)

    def validate_transition(self,phase,before,after):
        old_generation,_,old_fields=plan.parse_record(before);generation,_,fields=plan.parse_record(after)
        old_b5=old_fields['username']==b'b5-gateway' and old_fields['client_id']==b'b5-c-isolated'
        is_b5=fields['username']==b'b5-gateway' and fields['client_id']==b'b5-c-isolated'
        require((phase=='provision' and (old_generation,generation)==(3,4) and is_b5 and not old_b5)
            or (phase=='restore_config' and (old_generation,generation)==(4,3) and old_b5 and not is_b5),
            'SECTOR3_CONFIG_IDENTITY_OR_GENERATION')

    def deadline(self, reserve=0):
        require(time.monotonic()-self.started+reserve <= self.timeout_s, 'SECTOR3_SESSION_TIMEOUT')

    def check_prewrite_budget(self):
        read_bytes = 2 * (FULL_FLASH_BYTES + 16) + 4
        other_s = COMMIT_WAIT_S + CONTROL_AND_CLOSE_S
        if not self.resume:
            read_bytes += 2 * (END-BASE)
            other_s += ERASE_WAIT_S + len(self.expected_words) * PROGRAM_WORD_S
        # 擦除前为提交、两遍整片读回、复核及关闭预留时间。
        needed = BUDGET_FACTOR * (read_bytes / FULL_FLASH_BYTES * self.full_read_s + other_s)
        elapsed = time.monotonic() - self.started
        self.prewrite_budget = {'elapsed_s': elapsed, 'remaining_s': self.timeout_s-elapsed,
                                'required_s': needed, 'full_read_s': self.full_read_s}
        require(elapsed + needed <= self.timeout_s, 'SECTOR3_PREWRITE_BUDGET_INSUFFICIENT')

    def authorize_write(self, address, value):
        self.deadline(); require(type(value) is int and 0 <= value <= 0xffffffff and address % 4 == 0,
                                 'SECTOR3_WORD_ALIGNMENT_OR_VALUE')
        if address == KEYR:
            require(self.phase == 'UNLOCK' and self.keys == [0x45670123, 0xcdef89ab][:len(self.keys)]
                    and len(self.keys) < 2 and value == (0x45670123, 0xcdef89ab)[len(self.keys)], 'SECTOR3_KEY_SEQUENCE')
            self.keys.append(value); return
        if address == SR:
            require(value == 1 and self.phase not in ('PREFLIGHT', 'DONE'), 'SECTOR3_SR_CLEAR_DENIED'); return
        if address == CR:
            require(not self.resume or value not in (ERASE_READY, ERASE_START), 'SECTOR3_RESUME_ERASE_DENIED')
            allowed = {'ERASE_SETUP': (ERASE_READY,), 'ERASE_START': (ERASE_START,),
                       'PROGRAM': (PROGRAM,), 'STAGE_VERIFY': (0x200,), 'COMMIT': (PROGRAM,),
                       'LOCK': (0x200, LOCK), 'FAILURE_LOCK': (0x200, LOCK)}
            sequence = allowed.get(self.phase, ())
            index = self.cr_phase_counts.get(self.phase, 0)
            require(index < len(sequence) and value == sequence[index], 'SECTOR3_CR_SCOPE')
            self.cr_phase_counts[self.phase] = index+1
            if value == ERASE_START:
                require(self.erases == 0, 'SECTOR3_SECOND_ERASE_DENIED'); self.erases += 1
            self.cr_history.append(value); return
        if address == ACR:
            require(self.original_acr is not None, 'SECTOR3_ACR_PHASE')
            off = self.original_acr & ~0x400
            seq = {'CACHE_DISABLE': [off, off | 0x1000, off], 'CACHE_RESTORE': [self.original_acr],
                   'CACHE_FAILURE_RESTORE': [off, off | 0x1000, off, self.original_acr]}.get(self.phase, [])
            old = [v for p, v in self.acr_history if p == self.phase]
            require(len(old) < len(seq) and value == seq[len(old)], 'SECTOR3_ACR_SEQUENCE')
            self.acr_history.append((self.phase, value)); return
        require(BASE <= address < END, 'SECTOR3_WRITE_ADDRESS_DENIED')
        if address == COMMIT:
            require(self.phase == 'COMMIT' and self.stage_verified and (self.resume or self.erase_completed)
                    and self.commits == 0 and value == COMMIT_VALUE, 'SECTOR3_COMMIT_DENIED')
            self.commits += 1; return
        require(not self.resume and self.erase_completed and self.phase == 'PROGRAM'
                and len(self.words) < len(self.expected_words)
                and (address, value) == self.expected_words[len(self.words)], 'SECTOR3_PROGRAM_WORD_SCOPE')
        self.words.append(address)

    def write(self, address, value):
        self.io.write32(address, value)

    def ready(self, limit=5):
        start = time.monotonic()
        while True:
            self.deadline(); status = self.io.read32(SR)
            require(not status & ERRORS, 'SECTOR3_FLASH_ERROR')
            if not status & BUSY:
                if status & 1: self.write(SR, 1)
                return
            require(time.monotonic()-start <= limit, 'SECTOR3_FLASH_BUSY_TIMEOUT')
            time.sleep(.001)

    def run(self, observed_before, observed_options):
        require(observed_before == self.before and observed_options == self.options, 'SECTOR3_BEFORE_DRIFT')
        if self.resume:
            self.verify_stage(observed_before[plan.START:plan.END])
        self.check_prewrite_budget()
        initial_sr, initial_cr = self.io.read32(SR), self.io.read32(CR)
        require(not initial_sr & (BUSY | ERRORS), 'SECTOR3_INITIAL_ERROR_OR_BUSY')
        require(initial_cr in (LOCK, LOCK | 0x200), 'SECTOR3_INITIAL_CONTROL')
        self.original_acr = self.io.read32(ACR)
        require(not self.original_acr & 0x1800, 'SECTOR3_CACHE_RESET_ALREADY_SET')
        self.phase = 'CACHE_DISABLE'
        off = self.original_acr & ~0x400
        for value in (off, off | 0x1000, off):
            self.write(ACR, value); require(self.io.read32(ACR) == value, 'SECTOR3_CACHE_DISABLE_VERIFY')
        self.phase = 'UNLOCK'; self.write(KEYR, 0x45670123); self.write(KEYR, 0xcdef89ab)
        require(not self.io.read32(CR) & LOCK, 'SECTOR3_CONTROLLER_UNLOCK_FAILED')
        self.ready()
        if not self.resume:
            self.erase_and_program_stage()
        self.phase = 'COMMIT'; self.write(CR, PROGRAM)
        require(self.io.read32(CR) == PROGRAM and self.io.read(COMMIT, 4) == b'\xff'*4,
                'SECTOR3_COMMIT_PRECONDITION')
        self.write(COMMIT, COMMIT_VALUE); self.ready(COMMIT_WAIT_S)
        self.phase = 'LOCK'; self.write(CR, 0x200); self.write(CR, LOCK)
        require(self.io.read32(CR) == LOCK, 'SECTOR3_CONTROLLER_NOT_RELOCKED')
        self.phase = 'FINAL_VERIFY'
        actual, options = self.io.read(0x08000000, 1048576), self.io.read(0x1fffc000, 16)
        require(actual == self.after and options == self.options, 'SECTOR3_FINAL_FULL_OR_OPTIONS_DRIFT')
        require(self.erases == int(not self.resume) and self.commits == 1
                and len(self.words) == len(self.expected_words), 'SECTOR3_ACTION_COUNTS')
        self.phase = 'CACHE_RESTORE'; self.write(ACR, self.original_acr)
        require(self.io.read32(ACR) == self.original_acr, 'SECTOR3_ACR_RESTORE_VERIFY')
        self.phase = 'DONE'; self.verified_full = actual; self.verified_options = options
        return {'status': 'SECTOR3_BYTE_VERIFY_COMPLETE_NOT_BOOT_VERIFIED', 'phase': self.operation,
                'erase_start_commands': self.erases, 'stage1_program_words': len(self.words), 'commit_word_writes': self.commits,
                'all_Download_APIs': 0, 'after_full_sha256': plan.sha(actual), 'options_sha256': plan.sha(options),
                'original_ACR_restored': True, 'ordinary_FLASH_CR_unlock_not_RDP_unlock': True}

    def erase_and_program_stage(self):
        self.phase = 'ERASE_SETUP'; self.write(CR, ERASE_READY)
        require(self.io.read32(CR) == ERASE_READY, 'SECTOR3_ERASE_CONTROL_READBACK')
        self.phase = 'ERASE_START'; self.write(CR, ERASE_START); self.ready(ERASE_WAIT_S)
        require(self.io.read(BASE, END-BASE) == b'\xff'*(END-BASE), 'SECTOR3_ERASE_FULL_VERIFY')
        self.erase_completed = True
        self.phase = 'PROGRAM'; self.write(CR, PROGRAM)
        require(self.io.read32(CR) == PROGRAM, 'SECTOR3_PROGRAM_CONTROL_READBACK')
        for address, value in self.expected_words:
            self.write(address, value); self.ready()
        self.phase = 'STAGE_VERIFY'; self.write(CR, 0x200)
        self.verify_stage(self.io.read(BASE, END-BASE))

    def verify_stage(self, stage):
        require(stage == self.stage and stage[20:24] == b'\xff'*4, 'SECTOR3_STAGE1_VERIFY')
        require(plan.record_crc(stage[:336]) == int.from_bytes(stage[16:20], 'little'), 'SECTOR3_STAGE1_CRC')
        self.stage_verified = True

    def failure_lock(self):
        # 只做授权内PG清除/重锁，绝不再写NVM；忙或链路错误时保持UNKNOWN，不盲写控制器。
        require(not self.io.read32(SR) & BUSY, 'SECTOR3_FAILURE_STILL_BUSY_NO_CLEANUP')
        self.phase = 'FAILURE_LOCK'; self.write(CR, 0x200); self.write(CR, LOCK)
        require(self.io.read32(CR) == LOCK, 'SECTOR3_FAILURE_RELOCK_FAILED')
        if self.original_acr is not None and self.acr_history:
            self.phase = 'CACHE_FAILURE_RESTORE'; off = self.original_acr & ~0x400
            for value in (off, off | 0x1000, off, self.original_acr):
                self.write(ACR, value); require(self.io.read32(ACR) == value, 'SECTOR3_FAILURE_ACR_RESTORE')
