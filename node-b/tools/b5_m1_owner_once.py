"""负责人直接授权的固定RR批次的单次台架入口；不是PI签署。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_m1_entry as m

AUTHORITY = 'OWNER_DIRECT_RESP_BATCH15_20261031'
PUBLIC_SHA256 = 'd3d4d120edb0c2b7138d6662ffb8b283a4b4ada6d0e678c0fc538590e058c5f3'
AUTHORIZED_RUNS = {'M1-R18-R3': {'target': 18,
               'nonce_sha256': '2808790c690de02e539651b7ba9dc5a14f766e3701146beeff5c5884eb275dbc'},
 'M1-R30-R3': {'target': 30,
               'nonce_sha256': '06e9270b826aec479d934c59aa0ff6f99242cdfb70e618e6b965b3805a1f1b8d'},
 'M1-R15-R3': {'target': 15,
               'nonce_sha256': 'a53e127a62b67d6daedaf14a7f4cd4e9b8b52241e09e7e15feb272e24acfc909'},
 'M1-R24-R3': {'target': 24,
               'nonce_sha256': 'd73f8a5b07f0de6b4107babf9c665c0e69063ad986367d823b5d8896955c6b9d'},
 'M1-R12-R3': {'target': 12,
               'nonce_sha256': '25826830f0fa14b437efc50957b1e25a9526a1311ebc7a166306526b7d072fb3'}}
TOPOLOGY = 'B_READ_ONLY_C_POWERED_CAN_BACKGROUND'


def private_file(name):
    path = Path(name).resolve()
    m.need(path.is_relative_to(m.PRIVATE.resolve()) and path.is_file()
           and path.stat().st_file_attributes & 0x4000, 'M1_OWNER_PRIVATE_FILE')
    return path


def bindings(a):
    run_id = a['run_id']; target = AUTHORIZED_RUNS[run_id]['target']
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
    m.need(site.get('source_mode') == 'RESP' and site.get('target_rate') == target
           and site.get('waveform_type_confirmed') is True
           and (site.get('R_lead'), site.get('L_lead'), site.get('F_lead')) == ('RA', 'LL', 'RL'),
           'M1_OWNER_RESP_SOURCE')
    m.need(site.get('RESP_amplitude') == '1.5R' and site.get('waveform_period_bpm') == 30
           and site.get('apnea_s') == 0, 'M1_OWNER_RESP_MENU')
    m.need(cold.get('run_id') == run_id and cold.get('cold_start_completed') is True
           and bool(cold.get('independent_boot_epoch')), 'M1_INDEPENDENT_COLD_START')
    output = Path(a['output']).resolve()
    m.need(output.is_relative_to(m.PRIVATE.resolve()) and output.parent.is_dir()
           and output.parent.stat().st_file_attributes & 0x4000, 'M1_OUTPUT_EFS')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=m.ROOT).decode().strip()
    m.need(not git('status', '--porcelain'), 'M1_WORKTREE_NOT_FROZEN')
    tools = m.tool_bindings()
    tools[Path(__file__).relative_to(m.ROOT).as_posix()] = m.sha(Path(__file__).read_bytes())
    expected = {'scope': m.SCOPE, 'run_id': run_id, 'plan_sha256': m.plan_hash(run_id),
                'repo_commit': git('rev-parse', 'HEAD'), 'repo_tree': git('rev-parse', 'HEAD^{tree}'),
                'tools_sha256': tools, 'DLL_sha256': '632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff',
                'bundle_sha256': m.sha(bundle_path.read_bytes()), 'site_sha256': m.sha(site_path.read_bytes()),
                'cold_start_sha256': m.sha(cold_path.read_bytes()), 'output': str(output),
                'manual_stop_responsibility': site['manual_stop_responsibility']}
    reference = {'identity': json.loads(Path(bundle['identity_reference']).read_text()),
                 'full_sha256': m.FULL_SHA, 'BIN_sha256': m.BIN_SHA, 'options_sha256': m.OPTIONS_SHA,
                 'maximum_cold_start_uptime_ms': None, 'capture_io_s': 180,
                 'cold_start_sha256': expected['cold_start_sha256']}
    return expected, reference


def verify(args):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    raw = private_file(args.authorization).read_bytes()
    sig = private_file(args.signature).read_bytes(); public = private_file(args.public_key).read_bytes()
    m.need(m.sha(public) == PUBLIC_SHA256, 'M1_OWNER_UNTRUSTED_KEY')
    Ed25519PublicKey.from_public_bytes(public).verify(sig, raw)
    a = json.loads(raw)
    m.need(a.get('authority') == AUTHORITY and a.get('PI_independent_signature') is False
           and a.get('run_id') in AUTHORIZED_RUNS
           and m.sha(a.get('nonce', '').encode()) == AUTHORIZED_RUNS[a['run_id']]['nonce_sha256'],
           'M1_OWNER_ONCE_SCOPE')
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
        print(json.dumps({'authority': AUTHORITY, 'PI_root_changed': False,
                          'authorized_runs': list(AUTHORIZED_RUNS),
                          'execute_requires_signed_current_card': True})); return 0
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
