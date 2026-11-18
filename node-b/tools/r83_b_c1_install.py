"""R83 B 板 J-Link 单会话安装。默认只核对主机原件。"""

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
SCOPE = 'R83_B_C1_APP012_INSTALL'
CARD = app.ROOT / 'node-b/docs/PI-REVIEW/R83-B-C1-ALGO-AND-MQTT-CAPTURE-CARD-20261118.md'
CARD_SHA = '4e0e1851e5278d6f960574edd277f0284db9b424d71a1064de5d1cdcb35e3562'
BEFORE_BIN = 'e9f34d78215a57e14a54255f84d8c8ba22b1c5aa8ee0056f97400f59993a5b77'
BEFORE_FULL = '7d0e617ed609585e216a8aa258da63767ae8d289d2ec0da11cb7d539756d7d44'
CANDIDATE = '1c28707fa215f2ee068750440cc670cddc8e9629f45d20927fc2676ac168642b'
EXPECTED_FULL = 'a40ad7633b4c2acaa8db0fbb229d635e747fad148f67266610789ac032ce560f'
PRIOR = recovery.PRIVATE / 'R80-B-home-diag-install-20261118T021923587Z/probe'


def bindings():
    return {**app.bindings(), Path(__file__).name: app.raw.sha(__file__),
            Path(supervisor.__file__).name: app.raw.sha(supervisor.__file__)}


def inputs(candidate):
    require(app.raw.sha(CARD) == CARD_SHA, 'R83_CARD_DRIFT')
    require(app.raw.sha(app.DLL) == app.raw.DLL_SHA, 'R83_DLL_DRIFT')
    original = recovery.read(PRIOR / 'after-full-private.bin', False)
    require(sha(original) == BEFORE_FULL, 'R83_FULL_BASELINE')
    require(sha(original[:40600]) == BEFORE_BIN, 'R83_APPLICATION_BASELINE')
    options = recovery.read(PRIOR / 'after-options-private.bin', False)
    identity = json.loads(recovery.read(PRIOR / 'identity-after-private.json', False))
    image = Path(candidate).read_bytes()
    require(len(image) == 40420, 'R83_CANDIDATE_LENGTH')
    manifest, payload = recovery.make_plan('B', original, original, options, options,
                                           identity, identity, image, CANDIDATE)
    require(manifest['sectors'] == [0, 1, 2], 'R83_SECTOR_SCOPE')
    require(manifest['files']['expected-full-private.bin']['sha256'] == EXPECTED_FULL, 'R83_EXPECTED_FULL_DRIFT')
    return manifest, payload


def authorize(auth, out, *flags):
    require(not any(flags), 'R83_EXTERNAL_ACTION_FORBIDDEN')
    require(auth.get('enabled') is True and auth.get('owner_approved') is True
            and auth.get('scope') == SCOPE and auth.get('phase') == 'install', 'R83_AUTH_REQUIRED')
    require(auth.get('card_sha256') == CARD_SHA and auth.get('tools_sha256') == bindings(),
            'R83_AUTH_BINDING')
    require(auth.get('session_timeout_s') == 180 and auth.get('probe_sessions') == 1
            and auth.get('retries') == 0 and auth.get('expires_unix', 0) > time.time(), 'R83_SESSION_BUDGET')
    require(auth.get('site') == {'B_only_powered': True, 'JLink_on_B': True, 'no_human': True},
            'R83_SITE_NOT_READY')
    require(Path(auth['output']).resolve() == out.resolve(), 'R83_OUTPUT_BINDING')
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
            require(first == second, 'R83_FULL_DOUBLE_READ_MISMATCH')
            require(self.before_reads[0] == BEFORE_FULL and sha(first[:40600]) == BEFORE_BIN,
                    'R83_LIVE_BASELINE_DRIFT')
            require(time.monotonic() - self.started < 65, 'R83_PREWRITE_BUDGET')
        return first


def worker(auth_path, out, auth, manifest, payload):
    mark = json.loads(recovery.read(auth_path.with_suffix('.used'), False))
    require(mark['authorization_sha256'] == sha(recovery.read(auth_path, False)), 'R83_SINGLE_USE')
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
    require(args.authorization and args.out, 'R83_AUTH_OUT_REQUIRED')
    if args.worker:
        auth = json.loads(recovery.read(args.authorization, False))
        return worker(args.authorization, args.out, auth, *authorize(auth, args.out))
    return supervisor.supervise(args.authorization, args.out, backend=__import__(__name__))


if __name__ == '__main__':
    raise SystemExit(main())
