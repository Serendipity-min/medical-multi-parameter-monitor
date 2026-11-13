"""B2-0 脱机 profile 与观察门禁；不包含硬件连接、读取或写入入口。"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = '438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae'
BIO_SOURCE = '3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7'
SCHEMA = 'BIO_V2_FIELD_OFFLINE_PLAN_1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def tool_files():
    # 同时冻结既有解析器；旧硬件入口不在本工具中调用。
    paths = [Path(__file__), ROOT/'node-b/acquisition/工具/stable_slot_export.py']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def validate_profile(profile, arm, abi):
    require(profile['schema'] == SCHEMA, 'OLD_PROFILE')
    require(profile['record_status'] == 'OFFLINE_PREPARED_NOT_AUTHORIZED', 'STATUS')
    require(profile['firmware_binding'] == abi['firmware_binding'], 'ARTIFACT_BINDING')
    require(profile['firmware_binding']['BIO_V2.bin']['sha256'] == CANDIDATE, 'BIN')
    require(profile['tools_sha256'] == tool_files(), 'TOOL_DRIFT')
    source = ROOT/'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c'
    require(profile['bio_source_sha256'] == sha(source) == BIO_SOURCE, 'SOURCE_DRIFT')
    for name, relative in [('BIO_V2.bin', 'firmware/OBJ/BIO_V2.bin'),
                           ('BIO_V2.axf', 'firmware/OBJ/BIO_V2.axf'), ('symbols.txt', 'symbols.txt')]:
        p = Path(arm)/relative
        binding = profile['firmware_binding'][name]
        require(p.stat().st_size == binding['bytes'] and sha(p) == binding['sha256'], 'ARTIFACT_DRIFT')
    # 地址必须同时满足 SRAM 边界和本次 ARM ABI，不能只校验“落在 RAM 里”。
    layout = profile['layout']
    for name, length in [('diag', 120), ('slots', 3072), ('adc_stats', 48),
                         ('register_readback', 12), ('head', 4), ('tail', 4)]:
        region = layout[name]
        address = int(region['address'], 0)
        require(region['bytes'] == length and address % 4 == 0
                and 0x20000000 <= address < address+length <= 0x20020000, 'ADDRESS_RANGE')
        expected = abi[name] if isinstance(abi[name], dict) else {'address': abi[name], 'bytes': 4}
        require(region == expected, 'ABI_LAYOUT_MISMATCH')
    require(layout['diag']['tag'] == '0x324f4942' and layout['diag']['abi_version'] == 2, 'ABI_TAG')
    require(profile['device_binding'] == {'uid': None, 'flash_sha256': None,
            'capacity_bytes': None, 'options_sha256': None}, 'PUBLIC_DEVICE_IDENTITY')
    require(profile['hardware_actions'] == [], 'NO_HARDWARE_PERMISSION')
    return 'PASS_OFFLINE_ONLY'


def check_observation(expected, observed):
    """仅检查外部提供的记录；返回值不能作为现场许可或原码完整性证明。"""
    require(expected['uid'] is not None and expected['flash_sha256'] is not None, 'UNBOUND_DEVICE')
    require(observed['uid'] == expected['uid'], 'UID_MISMATCH')
    require(observed['flash_sha256'] == expected['flash_sha256'], 'FLASH_MISMATCH')
    require(observed['abi_tag'] == 0x324f4942 and observed['abi_version'] == 2, 'ABI_MISMATCH')
    # 活动 RAM 读取跨代或未确认末尾时，不接受为稳定的完整采集。
    require(observed['boot_before'] == observed['boot_after'] != '', 'CROSS_GENERATION')
    require(observed['diag_sequence_before'] == observed['diag_sequence_after'], 'TORN_DIAG')
    require(observed['tail_halt_confirmed'] is True and observed['resume_confirmed'] is True,
            'UNCONFIRMED_END')
    return 'METADATA_CONSISTENT_NOT_ACCURACY_PROOF'


def prepare(arm, abi):
    profile = {'schema': SCHEMA, 'record_status': 'OFFLINE_PREPARED_NOT_AUTHORIZED',
               'data_source': 'ENGINEERING_NONHUMAN', 'firmware_binding': abi['firmware_binding'],
               'bio_source_sha256': BIO_SOURCE, 'tools_sha256': tool_files(),
               'device_binding': {'uid': None, 'flash_sha256': None,
                                  'capacity_bytes': None, 'options_sha256': None},
               'hardware_actions': [], 'layout': {},
               'collector_status': 'NOT_IMPLEMENTED_FOR_BIO_V2_DO_NOT_USE_LEGACY_CAPTURE',
               'diag_coherence': 'LIVE_UNCOORDINATED_OBSERVATIONAL_ONLY',
               'peak_events': 'OFFLINE_REPLAY_REQUIRED_NO_PER_BEAT_EVENT_LOG_IN_FIRMWARE',
               'state_regions_plan': [{'address': '0x20000000', 'bytes': 2048},
                                      {'address': abi['diag']['address'], 'bytes': 120}],
               'tail_plan': {'address': '0x20000000', 'bytes': 131072,
                             'requires_confirmed_halt': True, 'published_slots': 127}}
    for name in ('diag', 'slots', 'adc_stats', 'register_readback', 'head', 'tail'):
        profile['layout'][name] = copy.deepcopy(abi[name]) if isinstance(abi[name], dict) else {
            'address': abi[name], 'bytes': 4}
    validate_profile(profile, arm, abi)
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm-build', required=True, type=Path)
    parser.add_argument('--abi-receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    abi = json.loads(args.abi_receipt.read_text(encoding='utf-8'))
    require(abi['host_arm_layout_equal'] is True and abi['hardware_access'] is False, 'ABI_AUDIT')
    profile = prepare(args.arm_build, abi)
    # 独占创建，保留旧 profile 与失败原件，不覆盖已签发材料。
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(profile, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': 'PASS_OFFLINE_ONLY', 'profile_sha256': sha(args.output),
                      'hardware_access': False}))


if __name__ == '__main__':
    sys.exit(main())
