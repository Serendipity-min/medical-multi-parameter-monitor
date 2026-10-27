"""本次ESP在板豁免附件：复用冻结安装器；独立MEM-AP只读入口，默认禁用。"""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import time

import b4_swd_install as app
import b4_recovery as recovery
import b5_g2ro as ro
import b5_sector3_write as config
import b5_sector3_write_supervisor as supervision

ROOT = Path(__file__).resolve().parents[2]
INSTALL = 'B5_G2A_C012_OWNER_ESP_PRESENT_POWERED_EXCEPTION'
BRIDGE = 'B5_G2B_MEMAP_READONLY_NO_HALT_NO_FLASH_UNLOCK'
CARD = 'node-b/docs/AUTH-B5-G2A-FRESH-001-R2.md'
AFTER = '3eaf583a703137b09665da5d2bfd7e860cd3a2208bf659b631d7ee4d0541545c'
PACKAGE = '3782fc9caa0f921cc51001191df0ac90e2633710e89f56bae017d2e3d35e73fc'
RAM = config.RAM_STATE
require = recovery.require
sha = config.sha


def bindings():
    return {**app.bindings(), **config.bindings(),
            'b5_g2_site.py': sha(Path(__file__).read_bytes())}


def authorize(a, out):
    require(a.get('enabled') is True and a.get('owner_approved') is True
            and a.get('scope') in (INSTALL, BRIDGE), 'SITE_OWNER_SCOPE_REQUIRED')
    require(a.get('tools_sha256') == bindings() and a.get('DLL_sha256') == ro.raw.DLL_SHA, 'SITE_TOOL_DRIFT')
    require(a.get('expires_unix', 0) > time.time() and a.get('session_timeout_s') == 180
            and a.get('probe_sessions') == 1 and a.get('retries') == 0, 'SITE_TIME_OR_SESSION')
    require(Path(a.get('output', '')).resolve() == out.resolve(), 'SITE_OUTPUT_BINDING')
    require(a.get('card_sha256') == sha((ROOT/CARD).read_bytes()), 'SITE_CARD_DRIFT')
    evidence = recovery.read(Path(a['site_record']), False)
    require(sha(evidence) == a.get('site_record_sha256'), 'SITE_FACTS_SHA')
    site = json.loads(evidence)
    require(site.get('JLink_target') == 'C' and site.get('C_power') == 'J5_ON_OWNER_REPORTED'
            and site.get('C_USB') == 'DISCONNECTED_OWNER_REPORTED', 'SITE_C_CONNECTION')
    require(a.get('ESP_present_powered_exception_approved') is True
            and a.get('ESP_isolated') is False and site.get('ESP_isolated') is False
            and site.get('owner_isolation_waiver') == '批准豁免', 'SITE_ESP_EXCEPTION_REQUIRED')
    require(a.get('board') == 'C' and a.get('nonhuman_mock') is True, 'SITE_C_MOCK_ONLY')
    require(a.get('manifest_sha256') == PACKAGE, 'SITE_FROZEN_PACKAGE')
    m, payload = recovery.load_package(Path(a['package']), PACKAGE, False)
    require(m['sectors'] == [0, 1, 2] and m['erase_end_exclusive'] == 0x0800c000
            and m['candidate_sha256'] == config.planner.APP_SHA, 'SITE_APP_SCOPE')
    require(sha(payload['before-full-private.bin']) == ro.CURRENT_SHA
            and sha(payload['expected-full-private.bin']) == AFTER, 'SITE_IMAGES')
    if a['scope'] == INSTALL:
        require(a.get('phase') == 'install', 'SITE_INSTALL_ONLY')
    else:
        require(a.get('phase') == 'bridge_readonly', 'SITE_BRIDGE_ONLY')
        raw = recovery.read(Path(a['G2A_receipt']), False)
        require(sha(raw) == a.get('G2A_receipt_sha256'), 'SITE_G2A_RECEIPT_SHA')
        result = json.loads(raw)
        require(result.get('status') == 'G2A_INSTALL_VERIFIED_DISARMED_PASS' and result.get('exit_code') == 0
                and result.get('full_flash_sha256') == AFTER, 'SITE_G2A_NOT_PASSED')
    recovery.protected(out.parent, False)
    return m, payload


class InstallLink(app.InstallLink):
    def __init__(self, out, size):
        super().__init__(out, size)
        ro.ReadLink.install_log_filters(self)

    def call(self, name, *args, timeout=5):
        if name == 'JLINKARM_ReadMemEx' and args[:2] == (RAM, 4):
            require(self.fully_verified and args[3] == 0 and self.sdk_calls < 1600, 'SITE_RAM_BEFORE_VERIFY')
            self.sdk_calls += 1
            returned = ro.raw.Link.call(self, name, *args, timeout=timeout)
            self.io.write(json.dumps({'operation': name, 'address': hex(RAM), 'bytes': 4,
                                      'native_return_int': returned})+'\n'); self.io.flush()
            return returned
        return super().call(name, *args, timeout=timeout)

    def read(self, address, size):
        if (address, size) == (RAM, 4):
            value = (C.c_uint8*4)()
            require(self.call('JLINKARM_ReadMemEx', RAM, 4, value, 0) == 4, 'SITE_RAM_SHORT_READ')
            return bytes(value)
        return super().read(address, size)


class BridgeLink(config.NativeLink):
    def __init__(self, out):
        super().__init__(out, 0)

    def install_log_filters(self):
        callback = C.CFUNCTYPE(None, C.c_char_p)
        def logged(data):
            if data:
                value = {'sdk_text_sha256': sha(data), 'bytes': len(data),
                         'monotonic_s': time.monotonic(), 'inflight_host_API': getattr(self, 'active_api', None)}
                self.log.write((json.dumps(value)+'\n').encode()); self.log.flush()
        def failed(data): logged(data); self.error = True
        self.logger, self.error_callback = callback(logged), callback(failed)

    def call(self, name, *args, timeout=5):
        require(name in ro.CALLS | (config.DAP_CALLS-{'JLINKARM_CORESIGHT_Configure'}), 'SITE_RO_ACTION_DENIED')
        if name.endswith('APDPReg'): require(not getattr(self, 'raw_failed', False), 'SITE_RO_RAW_STOP_LATCHED')
        if name == 'JLINKARM_CORESIGHT_WriteAPDPReg':
            reg, ap, value = args
            require((ap == 0 and reg == 2 and value in (0, 0xf0)) or (ap == 1 and reg in (0, 1)),
                    'SITE_RO_TARGET_WRITE_DENIED')
        previous = getattr(self, 'active_api', None); self.active_api = name
        try:
            result = super().call(name, *args, timeout=timeout)
            if name.endswith('APDPReg') and result < 0: self.raw_failed = True
            return result
        except BaseException:
            if name.endswith('APDPReg'): self.raw_failed = True
            raise
        finally: self.active_api = previous

    def close(self):
        previous = getattr(self, 'active_api', None); self.active_api = 'JLINKARM_Close'
        try: return super().close()
        finally: self.active_api = previous

    def read(self, address, size):
        require(size in config.READS.get(address, set()), 'SITE_RO_READ_SCOPE')
        data = (C.c_uint8*size)()
        returned = self.call('JLINKARM_ReadMemEx', address, size, data, 0,
                             timeout=45 if size == 1048576 else 5)
        self.io.write(json.dumps({'address': hex(address), 'requested': size, 'returned': returned})+'\n')
        self.io.flush()
        require(returned >= 0, 'SITE_SDK_MEMORY_NATIVE_ERROR')
        require(returned == size, 'SITE_SDK_POSITIVE_SHORT_READ')
        return bytes(data)


def bridge_readonly(link, out, payload):
    reference = json.loads(payload['identity-private.json'])
    link.open()
    first = ro.raw.identity(link); require(first == reference, 'SITE_WRONG_C_IDENTITY')
    ro.raw.write_json(out/'identity-before-private.json', first)
    ro.raw.write_json(out/'entry-sticky-private.json', {'DHCSR': link.u32(ro.SYSTEM['DHCSR'])})
    state = ro.old.snapshot(link); ro.raw.write_json(out/'entry-private.json', state); ro.old.check_running(link, state)
    before = link.read(0x08000000, 1048576); options = link.read(0x1fffc000, 16)
    config.save(out, 'before-full-private.bin', before); config.save(out, 'before-options-private.bin', options)
    require(before == payload['expected-full-private.bin'] and options == payload['options-private.bin'], 'SITE_BEFORE_DRIFT')
    require(link.read(RAM, 4) == bytes(4), 'SITE_NOT_DISARMED')
    # 复用已连接的目标；Configure会重新初始化接口，不能混入当前SDK会话。
    require(link.call('JLINKARM_IsConnected') == 1, 'SITE_SDK_NOT_CONNECTED')
    sdk = (link.u32(0xe000ed00), link.read(0x08000000, 64), link.u32(config.CR), link.u32(config.SR))
    link.verified_running_flash = False
    bridge = config.DapBridge(config.NativeBus(link))
    proof = bridge.probe(*sdk)
    # 验证原始AP退出后SDK仍读到同一对象；不调用Engine或绑定任何目标写权限。
    require(bridge.state_restored and link.u32(0xe000ed00) == bridge.read32(0xe000ed00)
            and link.read(0x08000000, 64) == before[:64], 'SITE_BRIDGE_SDK_STATE_DRIFT')
    config.save(out, 'after-full-private.bin', link.read(0x08000000, 1048576))
    config.save(out, 'after-options-private.bin', link.read(0x1fffc000, 16))
    require((out/'after-full-private.bin').read_bytes() == before
            and (out/'after-options-private.bin').read_bytes() == options, 'SITE_AFTER_DRIFT')
    last = ro.raw.identity(link); ro.raw.write_json(out/'identity-after-private.json', last)
    require(first == last and link.read(RAM, 4) == bytes(4), 'SITE_POST_IDENTITY_OR_DISARMED')
    state = ro.old.snapshot(link); ro.raw.write_json(out/'exit-private.json', state); ro.old.check_running(link, state)
    link.set_close_resume(True)
    ro.raw.write_json(out/'raw-bridge-proof-private.json', proof)
    return {'status': 'G2B_MEMAP_READONLY_CROSSCHECK_PASS', 'exit_code': 0,
            'full_flash_sha256': sha(before), 'options_sha256': sha(options),
            'SDK_and_raw_DAP_readonly_match': True, 'DP_SELECT_canonical0_CSW_TAR_restored': True,
            'explicit_reset_halt_go': 0, 'Flash_unlock_erase_program_and_target_memory_writes': 0,
            'G2B_config_write': 'NOT_AUTHORIZED_NOT_RUN'}


def worker(a, auth_path, out, m, payload):
    mark = json.loads(recovery.read(auth_path.with_suffix('.used'), False))
    require(mark.get('authorization_sha256') == sha(recovery.read(auth_path, False)), 'SITE_SINGLE_USE_MARKER')
    out.mkdir(exist_ok=False); recovery.protected(out, False)
    link = None; result = {'status': 'STOP', 'exit_code': 1, 'automatic_retry_or_recovery': False}
    try:
        link = InstallLink(out, 49152) if a['scope'] == INSTALL else BridgeLink(out)
        link.started = min(link.started, mark['started_monotonic'])
        if a['scope'] == INSTALL:
            result = app.execute(link, out, a, m, payload)
            config.save(out, 'disarmed-state-private.bin', link.read(RAM, 4))
            require((out/'disarmed-state-private.bin').read_bytes() == bytes(4), 'SITE_NOT_DISARMED_AFTER_INSTALL')
            result.update(status='G2A_INSTALL_VERIFIED_DISARMED_PASS', DISARMED=True)
        else:
            result = bridge_readonly(link, out, payload)
    except BaseException as error:
        reason = str(error)
        if link and a['scope'] == BRIDGE: link.verified_running_flash = False
        result.update(status='STOP', exit_code=1, error_type=type(error).__name__)
        ro.raw.write_json(out/'failure-private.json', {'reason': reason if reason.isupper() and reason.replace('_', '').isalnum()
                                                     else 'SUPPRESSED', 'error_text_sha256': sha(reason.encode())})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled: link.set_close_resume(False)
            except BaseException as error: result.update(exit_code=1, close_policy_error_type=type(error).__name__)
            finally:
                try: link.close()
                except BaseException as error: result.update(exit_code=1, close_error_type=type(error).__name__)
            result.update(sdk_calls=link.sdk_calls, actions=getattr(link, 'actions', getattr(link, 'counts', {})),
                          close_resume_policy=link.close_resume_enabled)
        result.update(scope=a['scope'], ESP_isolated=False, ESP_isolation_waived_by_owner=True,
                      ESP_autonomous_network='UNKNOWN_NO_AT_COMMANDS', B5START=0, cloud_service_actions=0)
        ro.raw.write_json(out/'receipt-private.json', result)
        for path in out.iterdir():
            if path.is_file(): recovery.protected(path, False)
    print(json.dumps({'status': result['status'], 'exit_code': result['exit_code']})); return result['exit_code']


def supervise(auth_path, out):
    raw = recovery.read(auth_path, False); a = json.loads(raw); authorize(a, out)
    require(not out.exists(), 'SITE_OUTPUT_EXISTS'); started = time.monotonic()
    ro.raw.write_json(auth_path.with_suffix('.used'), {'authorization_sha256': sha(raw), 'scope': a['scope'],
                                                    'started_monotonic': started, 'started_unix': time.time()})
    command = [sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--worker',
               '--authorization', str(auth_path), '--out', str(out)]
    with out.with_name(out.name+'-worker-private.log').open('xb') as log:
        recovery.protected(out.with_name(out.name+'-worker-private.log'), False)
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try: result = supervision.watch(child, out, started_monotonic=started)
        except BaseException as error:
            result = {'reason': 'SUPERVISOR_EXCEPTION', 'error_type': type(error).__name__,
                      'supervisor_exit_code': 1, 'target_state': 'UNKNOWN_NO_RECONNECT_CLEANUP'}
        finally:
            if child.poll() is None: child.kill()
            child.wait(timeout=5)
        result['worker_exit_code'] = child.returncode
    out.mkdir(exist_ok=True); ro.raw.write_json(out/'supervisor-private.json', result)
    recovery.protected(out/'supervisor-private.json', False)
    print(json.dumps(result)); return result['supervisor_exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', type=Path); parser.add_argument('--out', type=Path)
    parser.add_argument('--worker', action='store_true'); parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.worker and not args.execute:
        print(json.dumps({'enabled': False, 'scopes': [INSTALL, BRIDGE], 'tools_sha256': bindings()})); return 0
    try:
        require(args.authorization and args.out, 'SITE_AUTH_AND_OUTPUT_REQUIRED')
        a = json.loads(recovery.read(args.authorization, False)); m, payload = authorize(a, args.out)
        return worker(a, args.authorization, args.out, m, payload) if args.worker else supervise(args.authorization, args.out)
    except BaseException as error:
        print(json.dumps({'status': 'STOP_BEFORE_TARGET', 'error_type': type(error).__name__, 'exit_code': 1})); return 1


if __name__ == '__main__': raise SystemExit(main())
