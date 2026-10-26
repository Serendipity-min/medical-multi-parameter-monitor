"""仅用磁盘冻结原件审查恢复布局；不加载调试器、不连接串口。"""
import base64
import hashlib
import json
from pathlib import Path
import socket
import ssl
import struct
import zlib

import b4_recovery as recovery
from b5_g0_readonly import ROOT, write_private


def sha(blob): return hashlib.sha256(blob).hexdigest()


def record_check(sector):
    r = sector[:336]
    magic, version, header, size, generation, crc, committed = struct.unpack_from('<IHHIIII', r)
    valid = (magic == 0x32433348 and version == 1 and header == 24 and size == 312 and
             generation != 0 and committed == 0x54494D43 and zlib.crc32(r[:16]+r[24:]) == crc)
    payload = r[24:]
    user = payload[171:204].split(b'\0', 1)[0]
    client = payload[269:310].split(b'\0', 1)[0]
    return {'record_header_commit_crc_valid': bool(valid),
            'B5_identity_matches': user == b'b5-gateway' and client == b'b5-c-isolated',
            'generation_nonzero': bool(generation)}


def main():
    private = Path(json.loads((ROOT/'node-b/build/b5-g0-private-pointer.json').read_text())['base'])
    b5 = Path(json.loads((ROOT/'node-b/build/b5-private-pointer.json').read_text())['base'])
    old = json.loads(Path('E:/medical-monitor-node-b4-software/node-b/build/c-com15-can2-review/closeout-24104-pointer.json').read_text())
    c = Path(old['base'])/'04-new-reinstall'
    f = recovery.read(c/'after-full-private.bin', False)
    options = recovery.read(c/'after-options-private.bin', False)
    ident = json.loads(recovery.read(c/'identity-after-private.json', False))
    image = recovery.read(b5/'final-normalized-C-artifact/B5_CLOUD_MOCK_GATEWAY.bin', False)
    elf = recovery.read(b5/'final-normalized-C-artifact/B5_CLOUD_MOCK_GATEWAY.elf', False)
    assert len(f) == 1048576 and len(options) == 16
    assert sha(f) == 'b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98'
    assert len(image) == 42552 and sha(image) == 'd5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683'
    assert sha(elf) == '3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8'
    assert sha(f[:24104]) == '127ba765b8144e8f8ae98ef826ac2a98f45f8facb4021ce1888c004e5ca46547'
    recovery.identity_check(ident)
    # 同一历史检查点仅用于纯字节规划，不声称是今天两次独立读回。
    manifest, payload = recovery.make_plan('C', f, f, options, options, ident, ident, image, sha(image))
    folder = private/'C24104-frozen-layout-NOT-FRESH'; folder.mkdir()
    for name, blob in payload.items(): write_private(folder/name, blob)
    encoded = recovery.encoded(manifest)
    write_private(folder/'manifest-private.json', encoded)
    recovery.load_package(folder, sha(encoded), False)
    sections = {}
    for label, start, end in [('sector3', 0xc000, 0x10000), ('sector7', 0x60000, 0x80000), ('sector11', 0xe0000, 0x100000)]:
        blob = f[start:end]; write_private(private/(label+'-frozen-private.bin'), blob)
        sections[label] = {'bytes': len(blob), 'sha256': sha(blob), 'B5_app_preserves': blob == payload['expected-full-private.bin'][start:end]}
    # 恢复源是原24104完整镜像；真实擦写验收须另行授权，不能拿内存比较冒充演练。
    assert payload['restore-sectors-private.bin']+payload['expected-full-private.bin'][49152:] == f
    b = Path(old['B_package'])
    bmanifest = (b/'manifest-private.json').read_bytes()
    _, bpayload = recovery.load_package(b, sha(bmanifest), False)
    bfull = bpayload['expected-full-private.bin']
    assert sha(bfull) == 'a1abed50a4c4dbab142a2319d61c047bc43b6816dd62754a080e3f7e12415091'
    archive = json.loads((b5/'final-archive-manifest-r2-private.json').read_text())
    counts = 0
    for name, meta in archive.items():
        blob = recovery.read(b5/name, False)
        expected = meta['sha256'] if isinstance(meta, dict) else meta
        assert sha(blob) == expected
        counts += 1
    snapshot = json.loads((private/'ssh-stdout-private.json').read_bytes())
    source_comparison = {}
    for suffix in ('app/main.py', 'app/hub.py', 'app/models.py', 'app/mqtt_adapter.py'):
        deployed = next(base64.b64decode(v['base64']) for k, v in snapshot['files'].items() if k.endswith('/'+suffix))
        local = (ROOT/'cloud/backend'/suffix).read_bytes()
        source_comparison[suffix] = {'deployed_sha256': sha(deployed), 'reviewed_B5_sha256': sha(local),
                                    'LF_equivalent': deployed.replace(b'\r\n',b'\n') == local.replace(b'\r\n',b'\n')}
    tls = {'MQTT_CONNECT_sent': False, 'MQTT_PUBLISH_sent': False, 'connect_from': 'LOCAL_WORKSTATION_TO_CONFIGURED_BROKER', 'TLS_version_requested': 'TLS1.2'}
    cfg = snapshot['private']['backend_mqtt_config']
    try:
        context = ssl.create_default_context()
        context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((cfg['host'], cfg.get('port', 8883)), timeout=8) as sock:
            with context.wrap_socket(sock, server_hostname=cfg['host']) as conn:
                tls.update(verified=True, protocol=conn.version(), certificate_sha256=sha(conn.getpeercert(binary_form=True)),
                           not_after=conn.getpeercert().get('notAfter'))
    except Exception as e:
        tls.update(verified=False, failure_type=type(e).__name__)
    report = {'status':'FROZEN_ASSETS_VERIFIED_FRESH_READBACK_REQUIRED', 'hardware_operations':0,
              'C_current_frozen_full_sha256':sha(f), 'C_options_sha256':sha(options),
              'B_current_frozen_full_sha256':sha(bfull), 'B_options_sha256':sha(bpayload['options-private.bin']),
              'C_candidate_bytes':len(image), 'C_candidate_sha256':sha(image), 'C_candidate_ELF_sha256':sha(elf),
              'application_sectors':[0,1,2], 'erase_range':'[0x08000000,0x0800C000)',
              'offline_C24104_layout_manifest_sha256':sha(encoded),
              'offline_C24104_expected_post_install_full_sha256':sha(payload['expected-full-private.bin']),
              'layout_is_today_backup':False, 'independent_fresh_double_read_performed':False,
              'physical_restore_rehearsal':'NOT_RUN', 'old_H3_layout_superseded_as_default':True,
              'protected_sections':sections, 'current_frozen_sector3':record_check(f[49152:65536]),
              'immutable_B5_archive_files_verified':counts, 'backend_source_comparison':source_comparison,
              'external_TLS12':tls, 'private_manifest_source':'HISTORICAL_C24104_VERIFIED_READBACK_ONLY', 'exit_code':0}
    write_private(private/'assets-report-private.json', json.dumps(report, indent=2).encode())
    (ROOT/'node-b/evidence/B5-G0/assets-readonly.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report)); return 0


if __name__ == '__main__': raise SystemExit(main())
