"""R89 B 板 J-Link 单会话安装。默认只核对主机原件。"""

import argparse
import json
import time
from pathlib import Path

import b4_recovery as recovery
import b4_swd_install as app
import b5_sector3_write_supervisor as supervisor

ro = app.readonly
require = recovery.require
sha = recovery.digest
SCOPE = 'R89_B_C2_APP012_INSTALL'
CARD = app.ROOT / 'node-b/docs/PI-REVIEW/R89-B-C2-AND-RESP-CAL-CARD-20261118.md'
CARD_SHA = '947951ffd748cf3ca063844c3305652048473b89477a3ea20fcc08775b5d7492'
BEFORE_BIN = '1c28707fa215f2ee068750440cc670cddc8e9629f45d20927fc2676ac168642b'
BEFORE_FULL = 'a40ad7633b4c2acaa8db0fbb229d635e747fad148f67266610789ac032ce560f'
CANDIDATE = 'f81063c9392a46924a1156d9851a24e47cc36f406b0980f5cfdbf7093093c540'
EXPECTED_FULL = '887e466e78cd4333a305e7318ac05677a17fa89feb84282906d68118a7174757'
PRIOR = recovery.PRIVATE / 'R83-B-C1-install-20261118T064149320Z/probe'


def bindings():
    return {**app.bindings(), Path(__file__).name: app.raw.sha(__file__),
            Path(supervisor.__file__).name: app.raw.sha(supervisor.__file__)}


def inputs(candidate):
    require(app.raw.sha(CARD) == CARD_SHA, 'R89_CARD_DRIFT')
    require(app.raw.sha(app.DLL) == app.raw.DLL_SHA, 'R89_DLL_DRIFT')
    original = recovery.read(PRIOR / 'after-full-private.bin', False)
    require(sha(original) == BEFORE_FULL, 'R89_FULL_BASELINE')
    require(sha(original[:40420]) == BEFORE_BIN, 'R89_APPLICATION_BASELINE')
    options = recovery.read(PRIOR / 'after-options-private.bin', False)
    identity = json.loads(recovery.read(PRIOR / 'identity-after-private.json', False))
    image = recovery.read(candidate, False)
    require(len(image) == 40576, 'R89_CANDIDATE_LENGTH')
    manifest, payload = recovery.make_plan('B', original, original, options, options,
                                           identity, identity, image, CANDIDATE)
    require(manifest['sectors'] == [0, 1, 2], 'R89_SECTOR_SCOPE')
    require(manifest['files']['expected-full-private.bin']['sha256'] == EXPECTED_FULL, 'R89_EXPECTED_FULL_DRIFT')
    return manifest, payload


def authorize(auth, out, *flags):
    require(not any(flags), 'R89_EXTERNAL_ACTION_FORBIDDEN')
    require(auth.get('enabled') is True and auth.get('owner_approved') is True
            and auth.get('scope') == SCOPE and auth.get('phase') == 'install', 'R89_AUTH_REQUIRED')
    require(auth.get('card_sha256') == CARD_SHA and auth.get('tools_sha256') == bindings(),
            'R89_AUTH_BINDING')
    require(auth.get('session_timeout_s') == 180 and auth.get('probe_sessions') == 1
            and auth.get('retries') == 0 and auth.get('expires_unix', 0) > time.time(), 'R89_SESSION_BUDGET')
    require(auth.get('site') == {'B_only_powered': True, 'JLink_on_B': True, 'no_human': True},
            'R89_SITE_NOT_READY')
    require(Path(auth['output']).resolve() == out.resolve(), 'R89_OUTPUT_BINDING')
    recovery.protected(out.parent, False)
    return inputs(auth['candidate'])


class InstallLink(app.InstallLink):
    before_reads = None

    def read(self, address, size):
        first = super().read(address, size)
        if (address, size) == (recovery.FLASH_BASE, recovery.FLASH_SIZE) and self.before_reads is None:
            app.save(self.out, 'before-full-1-private.bin', first)
            second = super().read(address, size)
            app.save(self.out, 'before-full-2-private.bin', second)
            self.before_reads = [sha(first), sha(second)]
            require(first == second, 'R89_FULL_DOUBLE_READ_MISMATCH')
            require(self.before_reads[0] == BEFORE_FULL and sha(first[:40420]) == BEFORE_BIN,
                    'R89_LIVE_BASELINE_DRIFT')
            require(time.monotonic() - self.started < 65, 'R89_PREWRITE_BUDGET')
        return first


def worker(auth_path, out, auth, manifest, payload):
    mark = json.loads(recovery.read(auth_path.with_suffix('.used'), False))
    require(mark['authorization_sha256'] == sha(recovery.read(auth_path, False)), 'R89_SINGLE_USE')
    out.mkdir(exist_ok=False)
    recovery.protected(out, False)
    link = None
    result = {'status': 'STOP', 'exit_code': 1}
    try:
        link = InstallLink(out, recovery.APP_LIMIT)
        link.started = mark['started_monotonic']
        result = app.execute(link, out, dict(auth, board='B'), manifest, payload)
    except (RuntimeError, ValueError, OSError) as error:
        if link:
            link.verified_running_flash = False
        result['stop_reason'] = str(error) if str(error).replace('_', '').isalnum() else type(error).__name__
        app.raw.write_json(out / 'failure-private.json', {'reason': str(error)})
    finally:
        if link:
            try:
                if not link.verified_running_flash and link.close_resume_enabled:
                    link.set_close_resume(False)
            except (RuntimeError, ValueError, OSError) as error:
                result.update(exit_code=1, close_policy_error=type(error).__name__)
            finally:
                try:
                    link.close()
                    result['Close_completed'] = True
                except (RuntimeError, ValueError, OSError) as error:
                    result.update(exit_code=1, Close_completed=False, close_error=type(error).__name__)
            result.update(native_actions=link.counts, sdk_calls=link.sdk_calls,
                          before_full_sha256=link.before_reads, download_started=link.download_started)
        result.update(scope=SCOPE, automatic_retry_or_restore=False)
        app.raw.write_json(out / 'receipt-private.json', result)
    return result['exit_code']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path)
    p.add_argument('--authorization', type=Path)
    p.add_argument('--out', type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()
    if not args.execute and not args.worker:
        manifest, _ = inputs(args.candidate)
        print(json.dumps({'enabled': False, 'scope': SCOPE, 'sectors': manifest['sectors'],
                          'expected_full_sha256': manifest['files']['expected-full-private.bin']['sha256'],
                          'tools_sha256': bindings()}))
        return 0
    require(args.authorization and args.out, 'R89_AUTH_OUT_REQUIRED')
    if args.worker:
        auth = json.loads(recovery.read(args.authorization, False))
        return worker(args.authorization, args.out, auth, *authorize(auth, args.out))
    return supervisor.supervise(args.authorization, args.out, backend=__import__(__name__))


if __name__ == '__main__':
    raise SystemExit(main())
