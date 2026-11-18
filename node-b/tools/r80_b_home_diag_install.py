"""R80 B 板 J-Link 单会话安装。默认只核对主机原件。"""

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
SCOPE = 'R80_B_HOME_DIAG_APP012_INSTALL'
CARD = app.ROOT / 'node-b/docs/PI-REVIEW/R80-B-HOME-DIAG-REVIEW-AND-INSTALL-CARD-20261118.md'
CARD_SHA = 'b1fa0da171cb50ace61cf333623232d0d9970e585c48d3f69d53e9c1545256d7'
BEFORE_BIN = '24612613b307558975c84ff3f763f5fd61439a1b60ac30744184e5a2eca0db0d'
BEFORE_FULL = '8b2cd047e9b09b715ef340591c2ae9b051b6bf84691697071e75fa4863d6ee60'
CANDIDATE = 'e9f34d78215a57e14a54255f84d8c8ba22b1c5aa8ee0056f97400f59993a5b77'
EXPECTED_FULL = '7d0e617ed609585e216a8aa258da63767ae8d289d2ec0da11cb7d539756d7d44'
PRIOR = recovery.PRIVATE / 'R78-B-diag-install-20261118T012656388Z/probe'


def bindings():
    return {**app.bindings(), Path(__file__).name: app.raw.sha(__file__),
            Path(supervisor.__file__).name: app.raw.sha(supervisor.__file__)}


def inputs(candidate):
    require(app.raw.sha(CARD) == CARD_SHA, 'R80_CARD_DRIFT')
    require(app.raw.sha(app.DLL) == app.raw.DLL_SHA, 'R80_DLL_DRIFT')
    original = recovery.read(PRIOR / 'after-full-private.bin', False)
    require(sha(original) == BEFORE_FULL, 'R80_FULL_BASELINE')
    require(sha(original[:40360]) == BEFORE_BIN, 'R80_APPLICATION_BASELINE')
    options = recovery.read(PRIOR / 'after-options-private.bin', False)
    identity = json.loads(recovery.read(PRIOR / 'identity-after-private.json', False))
    image = Path(candidate).read_bytes()
    require(len(image) == 40600, 'R80_CANDIDATE_LENGTH')
    manifest, payload = recovery.make_plan('B', original, original, options, options,
                                           identity, identity, image, CANDIDATE)
    require(manifest['sectors'] == [0, 1, 2], 'R80_SECTOR_SCOPE')
    require(manifest['files']['expected-full-private.bin']['sha256'] == EXPECTED_FULL, 'R80_EXPECTED_FULL_DRIFT')
    return manifest, payload


def authorize(auth, out, *flags):
    require(not any(flags), 'R80_EXTERNAL_ACTION_FORBIDDEN')
    require(auth.get('enabled') is True and auth.get('owner_approved') is True
            and auth.get('scope') == SCOPE and auth.get('phase') == 'install', 'R80_AUTH_REQUIRED')
    require(auth.get('card_sha256') == CARD_SHA and auth.get('tools_sha256') == bindings(),
            'R80_AUTH_BINDING')
    require(auth.get('session_timeout_s') == 180 and auth.get('probe_sessions') == 1
            and auth.get('retries') == 0 and auth.get('expires_unix', 0) > time.time(), 'R80_SESSION_BUDGET')
    require(auth.get('site') == {'B_only_powered': True, 'JLink_on_B': True, 'no_human': True},
            'R80_SITE_NOT_READY')
    require(Path(auth['output']).resolve() == out.resolve(), 'R80_OUTPUT_BINDING')
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
            require(first == second, 'R80_FULL_DOUBLE_READ_MISMATCH')
            require(self.before_reads[0] == BEFORE_FULL and sha(first[:40360]) == BEFORE_BIN,
                    'R80_LIVE_BASELINE_DRIFT')
            require(time.monotonic() - self.started < 65, 'R80_PREWRITE_BUDGET')
        return first


def worker(auth_path, out, auth, manifest, payload):
    mark = json.loads(recovery.read(auth_path.with_suffix('.used'), False))
    require(mark['authorization_sha256'] == sha(recovery.read(auth_path, False)), 'R80_SINGLE_USE')
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
    require(args.authorization and args.out, 'R80_AUTH_OUT_REQUIRED')
    if args.worker:
        auth = json.loads(recovery.read(args.authorization, False))
        return worker(args.authorization, args.out, auth, *authorize(auth, args.out))
    return supervisor.supervise(args.authorization, args.out, backend=__import__(__name__))


if __name__ == '__main__':
    raise SystemExit(main())
