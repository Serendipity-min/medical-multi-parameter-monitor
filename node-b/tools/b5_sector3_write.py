"""G2-B/R-CFG专用受限写入器；默认仅计划，当前轮不授权任何原生执行。"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import time

import b4_recovery as recovery
import b5_g2ro as ro
import b5_sector3_plan as planner
from b5_sector3_write_protocol import DapBridge, Engine, require, BASE, END, COMMIT, ACR, KEYR, SR, CR

ROOT = Path(__file__).resolve().parents[2]
PROVISION = 'B5_G2B_SECTOR3_PROVISION_COMMIT_LAST_RAW_MEMAP'
RESTORE = 'B5_R_CFG_SECTOR3_ORIGINAL_FIRST_RAW_MEMAP'
ELF_SHA = '3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8'
SYMBOL_SHA = 'fbf88b80076b6b508cc49b225067e9daf775d9c1c9ffeaeb559f9100ac365716'
FRESH_SHA = 'f614271c83b8b6f11992531537ea49ab6434f6f2a7c2481f1cced7ae55f1cad1'
RAM_STATE, RCC_CR, RCC_CFGR = 0x20001918, 0x40023800, 0x40023808
FILES = {'sector3-original-private.bin', 'sector3-uncommitted-private.bin', 'sector3-committed-private.bin',
         'record336-committed-private.bin', 'record336-uncommitted-private.bin',
         'expected-full-uncommitted-private.bin', 'expected-full-B5-new-config-private.bin',
         'expected-full-R-APP-only-private.bin', 'expected-full-R-CFG-only-private.bin',
         'expected-full-fully-restored-private.bin', 'original-full-private.bin', 'app-before-private.bin',
         'options-private.bin', 'identity-private.json', 'manifest-private.json'}
READS = {a: set(s) for a, s in ro.READS.items()}
READS.update({BASE: {16384}, COMMIT: {4}, ACR: {4}, RCC_CR: {4}, RCC_CFGR: {4}, RAM_STATE: {4}})
DAP_CALLS = {'JLINKARM_CORESIGHT_Configure', 'JLINKARM_CORESIGHT_ReadAPDPReg', 'JLINKARM_CORESIGHT_WriteAPDPReg'}


def sha(blob): return hashlib.sha256(blob).hexdigest()


def bindings():
    names = ('b5_sector3_write.py', 'b5_sector3_write_protocol.py', 'b5_sector3_write_supervisor.py',
             'b5_sector3_plan.py', 'b5_g2ro.py', 'b5_g2ro_supervisor.py', 'c_b4_closeout_readonly.py',
             'readback_b.py', 'runtime_state_b.py', 'live_state_b.py', 'resp_exploratory.py', 'b4_recovery.py')
    return {name: sha((ROOT/'node-b/tools'/name).read_bytes()) for name in names}


def plan():
    return {'enabled': False, 'owner_approved': False, 'scopes': [PROVISION, RESTORE],
            'tools_sha256': bindings(), 'DLL_sha256': ro.raw.DLL_SHA,
            'sector_range': [BASE, END], 'session_timeout_s': 180, 'probe_sessions': 1,
            'erase_start_max': 1, 'commit_write_max': 1, 'reset_max': 1, 'Go_max': 1, 'Halt_max': 1,
            'BeginDownload_EndDownload_and_highlevel_memory_writes': 0,
            'raw_AP_DP_bridge_hardware_validated': False,
            'AP_index_derivation': 'ADI_WORD_INDEX_CSW0_TAR1_DRW3_DP_SELECT2_AP0_BANK0_IDR_BANKF0_REG3',
            'raw_bridge_readonly_crosscheck_before_any_FLASH_unlock': True,
            'independent_before_flash_and_options_reads': 2, 'independent_after_flash_and_options_reads': 2,
            'commit_remaining_session_reserve_s': 110,
            'SELECT_policy': 'NEVER_READ_DP2_RESEND_CANONICAL_AP0_BANK0_ON_EXIT_RESTORE_READABLE_CSW_TAR',
            'entry_runtime_state_hex': {'provision': ['00000000'], 'restore_config': ['00000000', '00000101']},
            'post_reset_runtime_state_hex': '00000000',
            'actual_execution_in_current_round': 'NOT_AUTHORIZED', 'R_APP_scope_supported': False}


def load_package(folder, expected_binding_sha):
    folder = recovery.protected(Path(folder), False)
    raw = recovery.read(folder/'binding-private.json', False)
    require(sha(raw) == expected_binding_sha, 'S3_PACKAGE_BINDING_SHA')
    binding = json.loads(raw)
    require(binding.get('schema') == 'B5_SECTOR3_BOUND_PACKAGE_V1' and set(binding.get('files', {})) == FILES,
            'S3_PACKAGE_SCHEMA_OR_FILES')
    require({p.name for p in folder.iterdir()} == FILES | {'binding-private.json'}, 'S3_PACKAGE_EXTRA_FILES')
    require(binding.get('hardware_execution_enabled') is False and binding.get('latest_power_state_recheck_required') is True,
            'S3_PACKAGE_DISABLED_PLAN_REQUIRED')
    require(binding.get('source_fresh_read_binding_sha256') == FRESH_SHA, 'S3_FRESH_SOURCE_BINDING')
    require(binding.get('restore_order_for_execution') == 'R_CFG_FIRST_THEN_SEPARATELY_AUTHORIZED_R_APP',
            'S3_RESTORE_ORDER')
    require(binding.get('runtime_state') == {'address': RAM_STATE, 'bytes': 4, 'disarmed_expected_hex': '00000000',
            'ELF_sha256': ELF_SHA, 'symbols_sha256': SYMBOL_SHA}, 'S3_ELF_ABI_BINDING')
    require(binding.get('planner_sha256') == sha(Path(planner.__file__).read_bytes()), 'S3_PLANNER_SOURCE')
    blobs = {}
    for name in FILES:
        blob = recovery.read(folder/name, False); meta = binding['files'][name]
        require(len(blob) == meta['bytes'] and sha(blob) == meta['sha256'], 'S3_PACKAGE_PAYLOAD_SHA')
        blobs[name] = blob
    require(sha(blobs['manifest-private.json']) == binding['plan_manifest_sha256'], 'S3_PLAN_MANIFEST_SHA')
    original, app = blobs['original-full-private.bin'], blobs['app-before-private.bin']
    generation, minimum, fields = planner.parse_record(blobs['record336-committed-private.bin'])
    mqtt = {'gateway_id': 'GW-B5-001', 'username': fields['username'].decode('ascii'),
            'client_id': fields['client_id'].decode('ascii'), 'host': fields['host'].decode('utf8'),
            'password': fields['password'].decode('utf8'), 'port': 8883}
    manifest, rebuilt = planner.build_plan(original, app, mqtt, minimum)
    require(manifest == json.loads(blobs['manifest-private.json']) and
            all(blobs[name] == data for name, data in rebuilt.items()), 'S3_REBUILT_PLAN_DRIFT')
    require((binding.get('generation_from'), binding.get('generation_to'), generation) == (3, 4, 4)
            and binding.get('minimum_epoch') == minimum, 'S3_GENERATION_OR_EPOCH_BINDING')
    require(binding.get('gateway_id') == 'GW-B5-001' and binding.get('username') == 'b5-gateway'
            and binding.get('client_id') == 'b5-c-isolated' and binding.get('port') == 8883, 'S3_ROLE_BINDING')
    require(binding.get('source_original_full_sha256') == sha(original) and binding.get('source_app_full_sha256') == sha(app),
            'S3_SOURCE_IMAGES')
    identity = json.loads(blobs['identity-private.json']); recovery.identity_check(identity)
    require(identity['optcr'] & (1 << 19), 'S3_WRITE_PROTECTED_NO_UNLOCK')
    require(len(blobs['options-private.bin']) == 16 and sha(blobs['options-private.bin']) == ro.OPTIONS_SHA,
            'S3_OPTIONS_SIZE_OR_SHA')
    return binding, blobs, identity


def entry_runtime_state(a):
    allowed = {'provision': ('00000000',), 'restore_config': ('00000000', '00000101')}
    value = a.get('entry_runtime_state_hex')
    require(value in allowed.get(a.get('phase'), ()), 'S3_ENTRY_RUNTIME_STATE_NOT_ALLOWED')
    return bytes.fromhex(value)


def authorize(a, out):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') in (PROVISION, RESTORE),
            'S3_OWNER_AUTH_REQUIRED')
    require(a.get('tools_sha256') == bindings() and a.get('DLL_sha256') == ro.raw.DLL_SHA, 'S3_TOOL_OR_DLL_DRIFT')
    require(time.time() < a.get('expires_unix', 0), 'S3_AUTH_EXPIRED')
    phase = 'provision' if a['scope'] == PROVISION else 'restore_config'
    require(a.get('phase') == phase and a.get('board') == 'C', 'S3_SCOPE_PHASE')
    entry_runtime_state(a)
    require(a.get('session_timeout_s') == 180 and a.get('probe_sessions') == 1 and a.get('retries') == 0,
            'S3_SESSION_BOUND')
    require(a.get('failure_cleanup_scope') == 'PG_CLEAR_CR_LOCK_AND_ORIGINAL_ACR_IF_IDLE_ONLY' and a.get('nonhuman_mock') is True,
            'S3_CLEANUP_AND_SOURCE')
    require(Path(a.get('output', '')).resolve() == Path(out).resolve(), 'S3_OUTPUT_BINDING')
    site_raw = recovery.read(Path(a['site_record']), False)
    require(sha(site_raw) == a.get('site_record_sha256'), 'S3_SITE_SHA')
    site = json.loads(site_raw)
    require(site.get('JLink_target') == 'C' and all(site.get(k) is True for k in
            ('latest_power_state_checked', 'ESP_electrically_isolated', 'A_bus_disconnected', 'no_human',
             'C_power_ready', 'USB_and_CAN_state_frozen', 'BOOT_and_RESET_untouched')), 'S3_SITE_NOT_READY')
    binding, blobs, identity = load_package(a['package'], a['package_binding_sha256'])
    if phase == 'provision':
        before, after, stage = blobs['app-before-private.bin'], blobs['expected-full-B5-new-config-private.bin'], blobs['sector3-uncommitted-private.bin']
    else:
        before, after = blobs['expected-full-B5-new-config-private.bin'], blobs['app-before-private.bin']
        data = blobs['sector3-original-private.bin']; stage = data[:20]+b'\xff'*4+data[24:]
    require(a.get('before_full_sha256') == sha(before) and a.get('after_full_sha256') == sha(after), 'S3_AUTH_IMAGES')
    recovery.protected(Path(out).parent, False)
    return binding, blobs, identity, before, after, stage


class NativeLink(ro.ReadLink):
    def __init__(self, out, word_count):
        self.actions = {}; self.sdk_limit = 2048+80*(word_count+1)
        self.native_policy_counts = {}
        self.before_verified = self.post_verified = self.boot_vector_verified = False
        self.dap_select = self.dap_tar = self.dap_csw = None; self.raw_target_grant = None
        super().__init__(out)
        self.dll.JLINKARM_Halt.restype = C.c_int; self.dll.JLINKARM_Reset.restype = C.c_int
        self.dll.JLINKARM_CORESIGHT_Configure.argtypes = [C.c_char_p]
        self.dll.JLINKARM_CORESIGHT_Configure.restype = C.c_int
        self.dll.JLINKARM_CORESIGHT_ReadAPDPReg.argtypes = [C.c_uint8, C.c_uint8, C.POINTER(C.c_uint32)]
        self.dll.JLINKARM_CORESIGHT_ReadAPDPReg.restype = C.c_int
        self.dll.JLINKARM_CORESIGHT_WriteAPDPReg.argtypes = [C.c_uint8, C.c_uint8, C.c_uint32]
        self.dll.JLINKARM_CORESIGHT_WriteAPDPReg.restype = C.c_int

    def call(self, name, *args, timeout=5):
        require(name in ro.old.runtime.CALLS | DAP_CALLS | {'JLINKARM_Halt', 'JLINKARM_Reset', 'JLINKARM_Go'},
                'S3_NATIVE_FUNCTION_DENIED')
        require(self.sdk_calls < self.sdk_limit, 'S3_SDK_BUDGET')
        if name == 'JLINKARM_ExecCommand':
            command = args[0].decode('ascii')
            require(command in ro.COMMANDS or command in ('DisableFlashDL', 'DisableFlashBPs', 'SetResetType = 0'),
                    'S3_NATIVE_COMMAND_DENIED')
            if command == 'SetRestartOnClose = 1': require(self.verified_running_flash, 'S3_CLOSE_NOT_VERIFIED')
            limits = {'SetRestartOnClose 0': 6, 'SetRestartOnClose = 1': 2,
                      'DisableFlashDL': 1, 'DisableFlashBPs': 1, 'SetResetType = 0': 1}
            if command in limits:
                require(self.native_policy_counts.get(command, 0) < limits[command], 'S3_NATIVE_POLICY_BUDGET')
                self.native_policy_counts[command] = self.native_policy_counts.get(command, 0)+1
            if command in ('DisableFlashDL', 'DisableFlashBPs'):
                require(self.actions.get('JLINKARM_Halt') == 1 and not self.post_verified, 'S3_RAW_POLICY_PHASE')
            if command == 'SetResetType = 0': require(self.post_verified, 'S3_RESET_POLICY_BEFORE_VERIFY')
        if name == 'JLINKARM_ReadMemEx':
            require(args[1] in READS.get(args[0], set()) and args[3] == 0, 'S3_NATIVE_READ_SCOPE')
        if name in ('JLINKARM_GetRegisterList', 'JLINKARM_GetRegisterName', 'JLINKARM_ReadReg'):
            require(self.register_reads_allowed and self.post_verified, 'S3_CORE_REG_READ_DENIED')
        if name in ('JLINKARM_Halt', 'JLINKARM_Reset', 'JLINKARM_Go'):
            require(self.actions.get(name, 0) == 0, 'S3_NATIVE_ACTION_LIMIT')
            require(self.before_verified if name == 'JLINKARM_Halt' else
                    self.post_verified if name == 'JLINKARM_Reset' else self.boot_vector_verified,
                    'S3_NATIVE_ACTION_BEFORE_VERIFY')
            self.actions[name] = 1
        if name == 'JLINKARM_CORESIGHT_Configure': require(args == (b'',), 'S3_DAP_CONFIG_STRING')
        if name.endswith('APDPReg'):
            reg, ap = args[:2]; require((ap == 0 and reg == 2) or (ap == 1 and reg in (0, 1, 3)), 'S3_DAP_REG_SCOPE')
            if name == 'JLINKARM_CORESIGHT_ReadAPDPReg': require(ap == 1, 'S3_DAP_DP_SELECT_IS_NOT_READABLE')
            if name == 'JLINKARM_CORESIGHT_WriteAPDPReg' and ap == 1 and reg == 3:
                require(self.dap_select == 0 and self.dap_csw is not None and self.dap_csw & 0x37 == 2
                        and self.raw_target_grant == (self.dap_tar, args[2]), 'S3_DAP_DRW_NOT_GRANTED')
        self.sdk_calls += 1; self.gate()
        deadline = time.monotonic()+timeout
        self.events.write(json.dumps({'operation': name, 'active': True, 'deadline_monotonic': deadline})+'\n'); self.events.flush()
        result = getattr(self.dll, name)(*args)
        # 先保存原生返回，再检查SDK错误回调/期限，错误路径也不丢失真实整数返回。
        self.io.write(json.dumps({'operation': name, 'native_return_int': result if isinstance(result, int) else None,
                                  'return_type': type(result).__name__})+'\n'); self.io.flush()
        self.events.write(json.dumps({'operation': name, 'active': False})+'\n'); self.events.flush()
        if name.endswith('APDPReg') and result >= 0:
            value = args[2] if name.endswith('WriteAPDPReg') else C.cast(args[2], C.POINTER(C.c_uint32)).contents.value
            reg, ap = args[:2]
            if ap == 0 and reg == 2: self.dap_select = value
            if ap == 1 and self.dap_select == 0:
                if reg == 0: self.dap_csw = value
                if reg == 1: self.dap_tar = value
        require(time.monotonic() <= deadline, 'S3_NATIVE_CALL_TIMEOUT'); self.gate()
        return result

    def read(self, address, size):
        require(size in READS.get(address, set()), 'S3_NATIVE_READ_SCOPE')
        buffer = (C.c_uint8*size)()
        returned = self.call('JLINKARM_ReadMemEx', address, size, buffer, 0, timeout=45 if size == 1048576 else 5)
        require(returned == size, 'S3_NATIVE_SHORT_READ'); return bytes(buffer)


class NativeBus:
    def __init__(self, link): self.link = link
    def read(self, reg, ap):
        require(ap and reg in (0, 1, 3), 'S3_DAP_DP_SELECT_IS_NOT_READABLE')
        value = C.c_uint32()
        result = self.link.call('JLINKARM_CORESIGHT_ReadAPDPReg', reg, int(ap), C.byref(value))
        require(result >= 0, 'S3_DAP_READ_NATIVE_ERROR'); return value.value
    def write(self, reg, ap, value):
        result = self.link.call('JLINKARM_CORESIGHT_WriteAPDPReg', reg, int(ap), value)
        require(result >= 0, 'S3_DAP_WRITE_NATIVE_ERROR')
    def grant_target_write(self, address, value):
        self.link.raw_target_grant = None if address is None else (address, value)


class NativeIO:
    def __init__(self, link, bridge): self.link, self.bridge = link, bridge
    def bind_guard(self, guard): self.bridge.guard = guard
    def read32(self, address): return self.bridge.read32(address)
    def write32(self, address, value): self.bridge.write32(address, value)
    def read(self, address, size):
        require(self.bridge.state_restored, 'S3_DAP_STATE_NOT_RESTORED'); return self.link.read(address, size)


def save(out, name, data):
    with (out/name).open('xb') as f: f.write(data)
    recovery.protected(out/name, False); require((out/name).read_bytes() == data, 'S3_DISK_VERIFY')


def execute(link, out, auth, loaded):
    _, blobs, reference, before, after, stage = loaded
    expected_runtime = entry_runtime_state(auth)
    link.open(); seen = ro.raw.identity(link); recovery.identity_check(seen)
    require(seen == reference, 'S3_WRONG_UID_OR_PROTECTION'); ro.raw.write_json(out/'identity-before-private.json', seen)
    ro.raw.write_json(out/'entry-sticky-private.json', {'DHCSR': link.u32(ro.SYSTEM['DHCSR'])})
    state = ro.old.snapshot(link); ro.raw.write_json(out/'entry-private.json', state); ro.old.check_running(link, state)
    link.set_close_resume(True)
    pairs = []
    for index in (1, 2):
        actual, options = link.read(0x08000000, 1048576), link.read(0x1fffc000, 16)
        save(out, f'before-full-{index}-private.bin', actual); save(out, f'before-options-{index}-private.bin', options)
        require(actual == before and options == blobs['options-private.bin'], 'S3_CURRENT_FULL_OR_OPTIONS_DRIFT')
        pairs.append((actual, options))
    require(pairs[0] == pairs[1], 'S3_BEFORE_DOUBLE_READ_MISMATCH')
    require(sha(actual[:planner.APP_BYTES]) == planner.APP_SHA and link.read(RAM_STATE, 4) == expected_runtime,
            'S3_ENTRY_RUNTIME_STATE_MISMATCH')
    require(link.u32(RCC_CR) & (1 << 17) and link.u32(RCC_CFGR) & 0xfc == 4, 'S3_HCLK_NOT_FROZEN_HSE8_DIV1')
    probe = json.loads((out/'probe-status-private.json').read_text('utf8'))
    require(3000 <= probe['voltage_mv'] <= 3600, 'S3_VOLTAGE_FOR_PSIZE32')
    link.before_verified = True
    link.set_close_resume(False); require(link.call('JLINKARM_Halt', timeout=3) == 0, 'S3_HALT_FAILED')
    require(link.u32(ro.SYSTEM['DHCSR']) & ro.raw.HALT, 'S3_HALT_NOT_CONFIRMED'); link.u32(ro.SYSTEM['DHCSR']); link.stable_halt()
    link.verified_running_flash = False
    require(link.read(RAM_STATE, 4) == expected_runtime, 'S3_ARMED_CHANGED_AFTER_HALT')
    require(link.u32(RCC_CR) & (1 << 17) and link.u32(RCC_CFGR) & 0xfc == 4, 'S3_HCLK_CHANGED_AFTER_HALT')
    link.policy('DisableFlashDL'); link.policy('DisableFlashBPs')
    require(link.call('JLINKARM_CORESIGHT_Configure', b'') >= 0, 'S3_DAP_CONFIG_NATIVE_ERROR')
    bridge = DapBridge(NativeBus(link))
    result = bridge.probe(link.u32(0xe000ed00), link.read(0x08000000, 64), link.u32(CR), link.u32(SR))
    require(link.u32(0xe000ed00) == bridge.read32(0xe000ed00) and
            link.read(0x08000000, 64) == actual[:64] and link.u32(CR) == bridge.read32(CR),
            'S3_RAW_SDK_MIXED_READ_CROSSCHECK')
    ro.raw.write_json(out/'raw-bridge-preflight-private.json', result)
    engine = Engine(NativeIO(link, bridge), before, after, stage, options, auth['phase'], started_monotonic=link.started)
    link.active_engine = engine
    result = engine.run(actual, options)
    actual, options = engine.verified_full, engine.verified_options
    save(out, 'after-full-1-private.bin', actual); save(out, 'after-options-1-private.bin', options)
    require(actual == after and options == blobs['options-private.bin'], 'S3_POST_FULL_OR_OPTIONS_DRIFT')
    second_full, second_options = link.read(0x08000000, 1048576), link.read(0x1fffc000, 16)
    save(out, 'after-full-2-private.bin', second_full); save(out, 'after-options-2-private.bin', second_options)
    require(second_full == actual and second_options == options, 'S3_AFTER_DOUBLE_READ_MISMATCH')
    seen = ro.raw.identity(link); recovery.identity_check(seen); ro.raw.write_json(out/'identity-after-private.json', seen)
    require(seen == reference, 'S3_POST_IDENTITY_DRIFT')
    link.post_verified = True; link.policy('SetResetType = 0')
    require(link.call('JLINKARM_Reset') == 0, 'S3_NORMAL_RESET_FAILED')
    core = ro.old.runtime.core_if_halted(link); ro.raw.write_json(out/'reset-core-private.json', core)
    registers = core.get('registers', {})
    require((registers.get('R15', 0) & ~1) == (int.from_bytes(after[4:8], 'little') & ~1)
            and registers.get('MSP') == int.from_bytes(after[:4], 'little'), 'S3_RESET_REAL_PC_MSP_MISMATCH')
    require(not (link.u32(ro.SYSTEM['CFSR']) | link.u32(ro.SYSTEM['HFSR'])), 'S3_RESET_FAULT')
    link.boot_vector_verified = True; link.call('JLINKARM_Go'); time.sleep(.2)
    link.u32(ro.SYSTEM['DHCSR'])
    for _ in range(3): ro.old.check_running(link, ro.old.snapshot(link)); time.sleep(.1)
    require(link.read(RAM_STATE, 4) == bytes(4), 'S3_NOT_DISARMED_AFTER_BOOT')
    link.set_close_resume(True)
    result.update(status='SECTOR3_FULL_VERIFY_AND_DISARMED_BOOT_PASS', exit_code=0, actions=link.actions,
                  raw_bridge_preflight='PASSED_IN_THIS_FUTURE_TRANSACTION_NOT_FROM_OFFLINE', no_network_arm_command=True)
    return result


def worker(authorization, out):
    auth_raw = recovery.read(authorization, False); auth = json.loads(auth_raw); loaded = authorize(auth, out)
    mark = json.loads(recovery.read(authorization.with_suffix('.used'), False))
    require(mark.get('authorization_sha256') == sha(auth_raw), 'S3_SUPERVISOR_MARKER')
    require(type(mark.get('started_monotonic')) in (int, float) and mark['started_monotonic'] <= time.monotonic(),
            'S3_SUPERVISOR_CLOCK_BINDING')
    out.mkdir(exist_ok=False); recovery.protected(out, False)
    link = None; result = {'status': 'STOP', 'exit_code': 1, 'automatic_retry_or_rollback': False}
    try:
        stage = loaded[-1]; count = sum(stage[i:i+4] != b'\xff'*4 for i in range(0, 16384, 4) if i != 20)
        link = NativeLink(out, count); link.started = min(link.started, mark['started_monotonic'])
        result = execute(link, out, auth, loaded)
    except BaseException as error:
        result.update(status='STOP', exit_code=1, error_type=type(error).__name__)
        if link and getattr(link, 'active_engine', None): result['failure_engine_phase'] = link.active_engine.phase
        text = str(error); ro.raw.write_json(out/'failure-private.json', {'error_type': type(error).__name__,
            'reason': text if text.startswith(('S3_', 'SECTOR3_', 'DAP_', 'C_RO_')) and text.replace('_', '').isalnum() else 'ERROR_TEXT_SUPPRESSED',
            'error_text_sha256': sha(text.encode())})
        if link and getattr(link, 'active_engine', None) and not link.post_verified:
            try:
                engine = link.active_engine
                if (engine.keys or engine.acr_history) and engine.phase != 'DONE' and link.u32(ro.SYSTEM['DHCSR']) & ro.raw.HALT:
                    engine.failure_lock(); result['failure_cleanup'] = 'PG_CLEARED_CR_LOCKED_ACR_RESTORED_NO_NVM_WRITE'
            except BaseException as cleanup: result['failure_cleanup_error_type'] = type(cleanup).__name__
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled: link.set_close_resume(False)
            except BaseException as error: result.update(exit_code=1, close_policy_error_type=type(error).__name__)
            finally:
                try: link.close()
                except BaseException as error: result.update(exit_code=1, close_error_type=type(error).__name__)
            result.update(sdk_calls=link.sdk_calls, actions=link.actions, close_resume=link.close_resume_enabled)
            if getattr(link, 'active_engine', None):
                engine = link.active_engine
                result.update(erase_start_attempts=engine.erases, stage1_word_attempts=len(engine.words),
                              commit_word_attempts=engine.commits, ordinary_KEYR_attempts=len(engine.keys),
                              ACR_control_attempts=len(engine.acr_history), final_engine_phase=engine.phase,
                              failure_did_not_authorize_retry_or_rollback=True)
        ro.raw.write_json(out/'receipt-private.json', result)
        for path in out.iterdir():
            if path.is_file(): recovery.protected(path, False)
    print(json.dumps({k: result[k] for k in ('status', 'exit_code')})); return result['exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true'); parser.add_argument('--worker', action='store_true')
    parser.add_argument('--authorization', type=Path); parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.plan or not args.worker: print(json.dumps(plan(), indent=2)); return 0
    try:
        require(args.authorization is not None and args.out is not None, 'S3_USE_SUPERVISOR')
        return worker(args.authorization, args.out)
    except BaseException as error:
        print(json.dumps({'status': 'STOP_BEFORE_NATIVE', 'error_type': type(error).__name__, 'exit_code': 1})); return 1


if __name__ == '__main__': raise SystemExit(main())
