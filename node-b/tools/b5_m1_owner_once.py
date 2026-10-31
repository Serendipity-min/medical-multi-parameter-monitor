"""负责人直接授权的一次ECG60台架入口；不是PI签署，不修改原PI入口。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_m1_entry as m

AUTHORITY = 'OWNER_DIRECT_ECG60_ONCE_20261031'
PUBLIC_SHA256 = 'c3d73409d3668951c6929b285f866d8c942b709c10197ec7b8fc4251a6b64fe9'
NONCE_SHA256 = 'a3547a8e4f088211b36d5a97d2e65c1f4bfd9d736a9431b6ed8bb9115c3abeea'
TOPOLOGY = 'B_READ_ONLY_C_POWERED_CAN_BACKGROUND'


def private_file(name):
    path = Path(name).resolve()
    m.need(path.is_relative_to(m.PRIVATE.resolve()) and path.is_file()
           and path.stat().st_file_attributes & 0x4000, 'M1_OWNER_PRIVATE_FILE')
    return path


def bindings(a):
    bundle_path = private_file(a['bundle_file'])
    bundle = json.loads(bundle_path.read_text()); m.validate_bundle(bundle)
    for role in ('identity', 'full', 'options'):
        path = private_file(bundle[role+'_reference'])
        m.need(m.sha(path.read_bytes()) == bundle[role+'_reference_sha256'], 'M1_REFERENCE_FILE_SHA')
    site_path = private_file(a['site_file']); cold_path = private_file(a['cold_start_file'])
    site = json.loads(site_path.read_text()); cold = json.loads(cold_path.read_text())
    required = ('owner_approved_topology', 'JLink_on_B', 'nonhuman_source', 'no_human',
                'B_USB_disconnected', 'SKX_battery_no_charge_USB', 'manual_emergency_cutoff_ready',
                'sdk_residual_risk_acknowledged', 'C_J5_powered', 'CAN_B_C_connected',
                'C_USB_disconnected')
    m.need(all(site.get(k) is True for k in required), 'M1_OWNER_SITE_NOT_READY')
    m.need(site.get('topology') == TOPOLOGY and site.get('B_C_electrically_isolated') is False,
           'M1_OWNER_TOPOLOGY')
    m.need(site.get('source_mode') == 'NORMAL_ECG' and site.get('target_rate') == 60
           and site.get('ECG_amplitude_mV') == 1 and site.get('waveform_type_confirmed') is True
           and (site.get('R_lead'), site.get('L_lead'), site.get('F_lead')) == ('RA', 'LA', 'RL'),
           'M1_OWNER_ECG60_MENU')
    m.need(cold.get('run_id') == 'M1-E60-R1' and cold.get('cold_start_completed') is True
           and bool(cold.get('independent_boot_epoch'))
           and 0 <= time.time()-cold.get('power_on_unix', 0) <= 120, 'M1_INDEPENDENT_COLD_START')
    output = Path(a['output']).resolve()
    m.need(output.is_relative_to(m.PRIVATE.resolve()) and output.parent.is_dir()
           and output.parent.stat().st_file_attributes & 0x4000, 'M1_OUTPUT_EFS')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=m.ROOT).decode().strip()
    m.need(not git('status', '--porcelain'), 'M1_WORKTREE_NOT_FROZEN')
    tools = m.tool_bindings()
    tools[Path(__file__).relative_to(m.ROOT).as_posix()] = m.sha(Path(__file__).read_bytes())
    expected = {'scope': m.SCOPE, 'run_id': 'M1-E60-R1', 'plan_sha256': m.plan_hash('M1-E60-R1'),
                'repo_commit': git('rev-parse', 'HEAD'), 'repo_tree': git('rev-parse', 'HEAD^{tree}'),
                'tools_sha256': tools, 'DLL_sha256': '632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff',
                'bundle_sha256': m.sha(bundle_path.read_bytes()), 'site_sha256': m.sha(site_path.read_bytes()),
                'cold_start_sha256': m.sha(cold_path.read_bytes()), 'output': str(output),
                'manual_stop_responsibility': site['manual_stop_responsibility']}
    reference = {'identity': json.loads(Path(bundle['identity_reference']).read_text()),
                 'full_sha256': m.FULL_SHA, 'BIN_sha256': m.BIN_SHA, 'options_sha256': m.OPTIONS_SHA,
                 'maximum_cold_start_uptime_ms': 120000, 'cold_start_sha256': expected['cold_start_sha256']}
    return expected, reference


def verify(args):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    raw = private_file(args.authorization).read_bytes()
    sig = private_file(args.signature).read_bytes(); public = private_file(args.public_key).read_bytes()
    m.need(m.sha(public) == PUBLIC_SHA256, 'M1_OWNER_UNTRUSTED_KEY')
    Ed25519PublicKey.from_public_bytes(public).verify(sig, raw)
    a = json.loads(raw)
    m.need(a.get('authority') == AUTHORITY and a.get('PI_independent_signature') is False
           and a.get('run_id') == 'M1-E60-R1'
           and m.sha(a.get('nonce', '').encode()) == NONCE_SHA256, 'M1_OWNER_ONCE_SCOPE')
    expected, reference = bindings(a)
    m.verify_signed_card(raw, sig, public, PUBLIC_SHA256, expected, time.time())
    return raw, sig, public, a, expected, reference


def execute(args):
    raw, sig, public, a, expected, reference = verify(args)
    ledger = m.PRIVATE/'m1-used-nonces'; ledger.mkdir(exist_ok=True)
    m.need(ledger.stat().st_file_attributes & 0x4000, 'M1_NONCE_LEDGER_EFS')
    name = m.sha((m.SCOPE+'\0'+a['nonce']).encode()); out = Path(expected['output'])
    if args.worker:
        m.need(json.loads((ledger/(name+'.used')).read_text()) ==
               {'scope': m.SCOPE, 'run_id': a['run_id'], 'authorization_sha256': m.sha(raw)}, 'M1_PARENT_MARKER')
        m.save(ledger/(name+'.worker-used'), {'authorization_sha256': m.sha(raw), 'run_id': a['run_id']})
        result = m.capture_window(m.native_link, out, reference)
        m.seal_capture(out, raw, sig, public, expected)
        return result['exit_code']
    m.need(not out.exists(), 'M1_OUTPUT_EXISTS'); m.consume_nonce(ledger, raw, a)
    command = [sys.executable, '-X', 'utf8', str(Path(__file__)), '--worker', '--authorization',
               str(args.authorization), '--signature', str(args.signature), '--public-key', str(args.public_key)]
    with out.with_name(out.name+'-worker.log').open('xb') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        result = m.watch_worker(child, out)
    out.mkdir(exist_ok=True); m.save(out/'supervisor-private.json', result)
    print(json.dumps(result)); return result['supervisor_exit_code']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true'); p.add_argument('--worker', action='store_true')
    for name in ('authorization', 'signature', 'public-key'):
        p.add_argument('--'+name, type=Path)
    a = p.parse_args()
    if not (a.execute or a.worker):
        print(json.dumps({'authority': AUTHORITY, 'PI_root_changed': False, 'run_id': 'M1-E60-R1',
                          'nonce_sha256': NONCE_SHA256, 'execute_requires_signed_current_card': True})); return 0
    try:
        m.need(a.authorization and a.signature and a.public_key, 'M1_SIGNED_FILES_REQUIRED')
        return execute(a)
    except (Exception, KeyboardInterrupt) as error:
        reason = str(error)
        print(json.dumps({'status': 'M1_OWNER_REJECT_OR_TOOL_ERROR', 'exit_code': 2,
                          'type': type(error).__name__, 'error_sha256': m.sha(reason.encode()),
                          'code': reason if reason.startswith('M1_') and reason.replace('_', '').isalnum() else 'PRIVATE_ERROR'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
