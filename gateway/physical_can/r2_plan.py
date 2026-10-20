"""生成待审的布局/镜像/回滚计划；不访问串口，不生成或写入真实持久配置。"""
from datetime import datetime,timezone
import hashlib,json,struct,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def plan():
    out=ROOT/'gateway/physical_can/evidence/h3-r2'
    offsets=[0,0x4000,0x8000,0xC000,0x10000,0x20000,0x40000,0x60000,0x80000,0xA0000,0xC0000,0xE0000,0x100000]
    sectors=[{'sector':i,'start':0x08000000+offsets[i],'end_exclusive':0x08000000+offsets[i+1],
        'erase_bytes':offsets[i+1]-offsets[i],
        'role':'APPLICATION' if i<3 else 'PROPOSED_CONFIG_OWNER_GATE' if i==3 else 'PROTECTED_UNCHANGED' if i in (7,11) else 'UNUSED_NOT_CONFIRMED_ERASED'} for i in range(12)]
    candidates={}
    for mode,name in [('isolated','isolated-arm-result.json'),('normal','arm-result.json')]:
        p=out/('persistent-'+mode)/name;d=json.loads(p.read_text())
        if d['exit_code'] or any(s>2 for s in d['image']['erase_sectors']):raise ValueError('APP_RANGE_GATE')
        binary=ROOT/'gateway/physical_can/build'/('h3-r2-persistent-'+mode)/'gateway_physical_can.bin'
        if hashlib.sha256(binary.read_bytes()).hexdigest()!=d['image']['sha256']:raise ValueError('BUILD_BYTES_CHANGED')
        candidates[mode]={'manifest':str(p.relative_to(ROOT)),'image':d['image'],'config':d['persistent_config']}
    result={'stage':'H3-R2-1_DESIGN_REVIEW','recorded_utc':datetime.now(timezone.utc).isoformat(),
        'chip_expected':'STM32F407ZGT6_1MiB','flash_size_reobserved_this_round':False,'sectors':sectors,
        'candidate_images':candidates,'candidate_profiles_default_enabled':False,
        'storage_comparison':[
            {'option':'EXTERNAL_SECURE_STORAGE','state':'NO_INSTALLED_PROVEN_DEVICE_OR_DRIVER','decision':'REQUIRES_HARDWARE_IDENTIFICATION'},
            {'option':'DEDICATED_SECTOR3_BENCH_CONFIG','state':'SOFTWARE_CANDIDATE_ONLY','encrypted':False,
             'physical_readout_confidentiality':False,'decision':'OWNER_ACCEPTANCE_REQUIRED_FOR_SCOPED_DEVICE_CREDENTIALS'},
            {'option':'RAM_ONLY_EXISTING','state':'VERIFIED_ISOLATION_HISTORY','decision':'NOT_PERSISTENT_NOT_A_DELIVERY_SUBSTITUTE'}],
        'record':{'bytes':336,'payload_bytes':312,'version':1,'header_bytes':24,
                  'crc':'CRC32_IEEE_LAYOUT_AND_PAYLOAD_NOT_CRYPTO_AUTH','commit_word_written_last':True,
                  'ARK_key_field':False,'runtime_flash_writer':False,'invalid_record':'FAIL_CLOSED_NO_NETWORK'},
        'wear':{'erase_on_reconnect_or_boot':False,'factory_provision_only':True,
                'datasheet_endurance_min_cycles':10000,'measured_erase_count':'UNKNOWN',
                'reference':'ST DS8626 Rev12 Table42; temperature conditions apply'},
        'before_any_flash':[
            'Separate owner window with accepted credential storage policy and exact firmware/config identity',
            'Read and preserve actual C sectors0-3 (64KiB), SHA256 twice; stop if identity/readback differs',
            'Read sector7/11 and options and compare frozen protected SHA before/after',
            'No sector3 erase until its original backup is verified and its full erase range is approved'],
        'failure_rollback':[
            'Uncommitted or bad-CRC record cannot connect; do not bypass using RAM injection',
            'Restore the window-specific C sectors0-3 backup under the same owner-approved recovery scope',
            'Old normal firmware still reads protected sector11, which is known unprovisioned; cannot claim old firmware autonomously reconnects',
            'Old isolation RAM profile can only be restored as an explicit bench session, not as cold-start acceptance'],
        'cold_start_acceptance':[
            'BOOT0=GND, BOOT1 as approved, Flash vectors/HSE intact',
            'Remove host/USB/debug assistance and use independently approved supply',
            'Cloud observes a new C session and A online/B offline for >=300s',
            'Continuous physical waveform window and NIBP source acceptance are separate gates'],
        'physical_actions_run':False,'hardware_write_authorization':'NOT_GRANTED_BY_CURRENT_CONTRACT_MATRIX',
        'secure_storage_gate':'PENDING_OWNER_REVIEW_NOT_PHYSICAL_CONFIDENTIALITY_CERTIFIED','exit_code':0}
    with (out/'H3-R2-1-CONFIG-PLAN.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'plan_created':True,'hardware_actions_run':False,'candidates':{k:{'bytes':v['image']['bytes'],'sha256':v['image']['sha256']} for k,v in candidates.items()}}))


if __name__=='__main__':plan()
