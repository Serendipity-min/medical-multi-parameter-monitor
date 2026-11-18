"""限时录制 NODE-B 的 MQTT 遥测和状态。"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import ssl
import time
import uuid


BASE = 'mpm/v1/GW-C-001/NODE-B'
TOPICS = [(BASE + '/telemetry/+', 0), (BASE + '/status', 0)]


class CaptureError(RuntimeError):
    pass


def create_client(config):
    import paho.mqtt.client as mqtt

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f'r83-readonly-{stamp}-{uuid.uuid4().hex[:8]}',
                         clean_session=True, protocol=mqtt.MQTTv311, reconnect_on_failure=False)
    client.username_pw_set(config['username'], config['password'])
    if config.get('tls', True):
        context = ssl.create_default_context(cafile=config.get('ca_file') or None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        client.tls_set_context(context)
    elif config['host'] not in ('127.0.0.1', '::1'):
        raise CaptureError('PLAIN_MQTT_REQUIRES_LOOPBACK')
    client.connect_timeout = 8
    return client


def capture(config, output, seconds):
    client = create_client(config)
    start = time.monotonic()
    subscribed = False
    subscription_id = None
    lines = 0
    digest = hashlib.sha256()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        def connected(client, userdata, flags, reason, properties):
            nonlocal subscription_id
            if reason.is_failure:
                raise CaptureError('CONNECT_REJECTED')
            rc, subscription_id = client.subscribe(TOPICS)
            if rc != 0:
                raise CaptureError('SUBSCRIBE_FAILED')

        def subscription(client, userdata, mid, reasons, properties):
            nonlocal subscribed
            if mid != subscription_id or len(reasons) != len(TOPICS) or any(r.is_failure for r in reasons):
                raise CaptureError('SUBSCRIBE_REJECTED')
            subscribed = True
            print(json.dumps({'state': 'SUBSCRIBED', 'utc_ms': time.time_ns() // 1_000_000}), flush=True)

        def message(client, userdata, msg):
            nonlocal lines
            topic = msg.topic
            prefix = BASE + '/telemetry/'
            suffix = topic[len(prefix):] if topic.startswith(prefix) else ''
            if topic != BASE + '/status' and (not suffix or '/' in suffix):
                raise CaptureError('UNEXPECTED_TOPIC')
            row = {'ts_ms': time.time_ns() // 1_000_000, 'topic': topic,
                   'payload': msg.payload.decode('utf-8')}
            data = (json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
            stream.write(data)
            digest.update(data)
            lines += 1

        client.on_connect = connected
        client.on_subscribe = subscription
        client.on_message = message
        status = 'COMPLETE'
        failure = None
        try:
            if client.connect(config['host'], config.get('port', 8883), keepalive=15) != 0:
                raise CaptureError('CONNECT_FAILED')
            while (remaining := seconds - (time.monotonic() - start)) > 0:
                if not subscribed and time.monotonic() - start > 15:
                    raise CaptureError('SUBACK_TIMEOUT')
                if client.loop(timeout=min(remaining, 1.0)) != 0:
                    raise CaptureError('NETWORK_LOOP_FAILED')
        except KeyboardInterrupt:
            status = 'OPERATOR_END'
        except (CaptureError, OSError, ValueError) as exc:
            status = 'FAILED'
            failure = str(exc) if isinstance(exc, CaptureError) else type(exc).__name__
        finally:
            client.disconnect()
        if not subscribed and failure is None:
            status, failure = 'FAILED', 'NO_SUBACK'
    return {'state': status, 'error': failure, 'lines': lines, 'sha256': digest.hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--seconds', type=int, default=3600)
    args = p.parse_args()
    if not 1 <= args.seconds <= 3600:
        p.error('--seconds must be in 1..3600')
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        config = json.loads(args.config.read_text(encoding='utf-8-sig'))
        result = capture(config, args.out, args.seconds)
    except (CaptureError, ImportError, OSError, ValueError, KeyError, TypeError) as exc:
        result = {'state': 'FAILED', 'error': type(exc).__name__}
    print(json.dumps(result), flush=True)
    return int(result['state'] == 'FAILED')


if __name__ == '__main__':
    raise SystemExit(main())
