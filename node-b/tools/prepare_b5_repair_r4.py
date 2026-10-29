"""R4离线候选/精确回退冻结；不加载SDK或访问设备/网络。原件只写受限EFS。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid
import b4_recovery as recovery
import b5_g3_contract as g
import b5_c_app_update as install
import b5_channel_profiles as channels

ROOT=g.ROOT
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--repeat',type=Path,required=True);parser.add_argument('--time-close-successor',action='store_true');args=parser.parse_args()
    pointer=json.loads((ROOT/'node-b/build/b5-egress-final-r1-pointer.json').read_text('utf8'))
    root=Path(pointer['root'])/('repair-r4-'+uuid.uuid4().hex[:8]);root.mkdir();recovery.protected(root,False)
    public=ROOT/'node-b/evidence/B5-C-REPAIR-R4'
    if args.time_close_successor:public=public/'TIME-CLOSE-R1'
    public.mkdir(exist_ok=False)
    def pub(name,data):
        raw=recovery.encoded(data);(public/name).write_bytes(raw);g.write_private(root/('public-'+name),raw)
    reports=[json.loads((p/'receipt.json').read_text('utf8')) for p in (args.build,args.repeat)]
    assert all(r['status']=='PASS' for r in reports)
    assert reports[0]['artifact_sha256']==reports[1]['artifact_sha256']
    assert reports[0]['source_sha256']==reports[1]['source_sha256'] and reports[0]['header_sha256']==reports[1]['header_sha256']
    image=(args.build/'B5_CLOUD_MOCK_GATEWAY.bin').read_bytes();assert 32768<len(image)<=49152
    predecessor=json.loads((ROOT/'node-b/build/b5-repair-r4-pointer.json').read_text('utf8')) if args.time_close_successor else None
    oldbinding=g.load(predecessor['binding'] if predecessor else pointer['diagnostic_R3_binding'])
    _,oldfiles=recovery.load_package(Path(oldbinding['package']),oldbinding['manifest_sha256'],False)
    if predecessor:
        proof=Path(predecessor['install_output'])/'receipt-private.json';receipt=g.load(proof)
        before=g.private.read(Path(predecessor['install_output'])/'after-full-private.bin',False)
        assert receipt['exit_code']==0 and receipt['DISARMED'] and receipt['Close_completed']
        assert sha(before)==receipt['full_flash_sha256']==install.BEFORE_REPAIR_R4
        oldbinding.update(before_full_sha256=sha(before),before_flags_address=oldbinding['flags_address'],
            prior_install_receipt=str(proof),prior_install_receipt_sha256=sha(proof.read_bytes()))
    else:before=oldfiles['before-full-private.bin'];assert sha(before)==install.BEFORE_FINAL_R2
    ident=json.loads(oldfiles['identity-private.json']);options=oldfiles['options-private.bin']
    manifest,files=recovery.make_plan('C',before,before,options,options,ident,ident,image,sha(image))
    package=root/'application-package';package.mkdir()
    for name,raw in files.items():g.write_private(package/name,raw)
    g.save(package/'manifest-private.json',manifest);manifest_sha=sha((package/'manifest-private.json').read_bytes())
    recovery.load_package(package,manifest_sha,False)
    assert files['restore-sectors-private.bin']+files['expected-full-private.bin'][49152:]==before
    artifacts=root/'candidate';artifacts.mkdir()
    for name in ('B5_CLOUD_MOCK_GATEWAY.bin','B5_CLOUD_MOCK_GATEWAY.elf','gateway.map','symbols.txt','receipt.json','executed-builder.py','build.log'):
        g.write_private(artifacts/name,(args.build/name).read_bytes())
    symbols=(artifacts/'symbols.txt').read_bytes()
    table={n:int(a,16) for a,n in re.findall(r'^([0-9a-fA-F]+)\s+\w\s+(\w+)\s*$',symbols.decode(),re.M)}
    flags=table['mqtt_connected'];assert [table[x] for x in ('mqtt_connected','network_open','stopped','armed')]==list(range(flags,flags+4))
    binding=dict(oldbinding,package=str(package),manifest_sha256=manifest_sha,candidate_bytes=len(image),candidate_sha256=sha(image),
        after_full_sha256=sha(files['expected-full-private.bin']),ELF=str(artifacts/'B5_CLOUD_MOCK_GATEWAY.elf'),
        ELF_sha256=sha((artifacts/'B5_CLOUD_MOCK_GATEWAY.elf').read_bytes()),symbols=str(artifacts/'symbols.txt'),
        symbols_sha256=sha(symbols),flags_address=flags)
    g.save(root/'binding-private.json',binding);binding_sha=sha((root/'binding-private.json').read_bytes())
    install.load_binding(root/'binding-private.json',binding_sha)
    compiled={k.replace('\\','/'):v for k,v in {**reports[0]['source_sha256'],**reports[0]['header_sha256']}.items()};archive=root/'compiled-source';archive.mkdir()
    external={Path(arg).name:Path(arg) for row in reports[0]['commands'] for arg in row['argv']
              if arg.endswith('.c') and Path(arg).is_file()}
    for name,digest in compiled.items():
        source=external[Path(name).name] if name.startswith('external-sdk/') else ROOT/name
        raw=source.read_bytes();assert sha(raw)==digest
        target=archive/name;target.parent.mkdir(parents=True,exist_ok=True);g.write_private(target,raw)
    source_sha=sha(recovery.encoded(dict(sorted(compiled.items()))))
    old_report=json.loads((Path(pointer['fallback_r2_build'])/'receipt.json').read_text('utf8'))
    old_manifest={k.replace('\\','/'):v for k,v in {**old_report['source_sha256'],**old_report['header_sha256']}.items()}
    old_archive=Path(pointer['fallback_r2_root'])/'deployed46584-source'
    delta={};r3_delta={}
    for name,digest in old_manifest.items():
        assert sha((old_archive/name).read_bytes())==digest
        if name.startswith('external-sdk/'):continue
        original=subprocess.check_output(['git','show','6835d8646e7b52464a6ad2188b88b916241068be:'+name],cwd=ROOT)
        if sha(original)!=digest:r3_delta[name]=dict(deployed=digest,R3=sha(original))
        if name in compiled and compiled[name]!=digest:delta[name]=dict(deployed=digest,R4=compiled[name])
    pub('source-alignment.json',dict(deployed_C_bytes=48888 if predecessor else 46584,historical_comparison_C_bytes=46584,archived_inputs_verified=len(old_manifest),
        R3_not_installed=True,R3_changed_inputs=r3_delta,R4_changed_compiled_inputs=delta,
        source_manifest_sha256=source_sha,compiled_inputs=compiled))
    gcc=Path(reports[0]['commands'][0]['argv'][0]);size=subprocess.check_output([str(gcc.with_name('arm-none-eabi-size.exe')),
        str(args.build/'B5_CLOUD_MOCK_GATEWAY.elf')]).decode()
    su=[]
    for p in args.build.glob('*.su'):
        for line in p.read_text('utf8').splitlines():
            cols=line.split('\t')
            if len(cols)>=3:su.append(dict(function=cols[0].rsplit(':',1)[-1],bytes=int(cols[1]),kind=cols[2]))
    su.sort(key=lambda x:x['bytes'],reverse=True)
    resources=dict(BIN_bytes=len(image),application_limit=49152,flash_remaining=49152-len(image),
        native_size_output=size,heap_bytes=24576,stack_reserved_bytes=8192,
        bss_bytes=table['_ebss']-table['_sbss'],data_bytes=table['_edata']-table['_sdata'],
        heap_end=hex(table['_heap_end']),MSP_top=hex(table['_estack']),
        gap_above_heap_and_reserved_stack=table['_estack']-table['_heap_end']-8192,
        largest_static_frames=su[:12],runtime_high_water='NOT_RUN_NEW_CANDIDATE',
        static_frame_is_not_transitive_stack_proof=True)
    pub('resources.json',resources)
    candidate=dict(status='FROZEN_SOFTWARE_PASS',BIN_bytes=len(image),BIN_sha256=sha(image),ELF_sha256=binding['ELF_sha256'],
        symbols_sha256=binding['symbols_sha256'],source_manifest_sha256=source_sha,
        predecessor_full_sha256=sha(before),expected_new_full_sha256=binding['after_full_sha256'],
        package_manifest_sha256=manifest_sha,binding_sha256=binding_sha,flags_address=hex(flags),
        double_build_identical=True,actual_installation='NOT_RUN',ECG60='NOT_PASS',TEMP_OBJECT='NOT_RUN',RR15='NOT_RUN',
        sector3_options_sector7_sector11='PRESERVED_BY_EXACT_PACKAGE',physical_power_off='NOT_CONFIRMED')
    pub('candidate.json',candidate)
    (public/'C-R4.bin').write_bytes(image)
    for key,destination in [('b5-repair-r4-host-latest.json','AT-combination'),('b5-egress-final-host-latest.json','regression'),('b5-egress-TLS-latest.json','local-TLS')]:
        record=json.loads((ROOT/'node-b/build'/key).read_text('utf8'));out=Path(record['out']);r=json.loads((out/'receipt.json').read_text('utf8'))
        assert r['status']=='PASS',destination
        if destination=='local-TLS':assert all(sha((ROOT/n).read_bytes())==h for n,h in r['source_sha256'].items())
        # TLS记录有完整编译源映射，但没有凭据/真实端点；其他原件按文件SHA保留。
        g.write_private(root/(destination+'-receipt-private.json'),(out/'receipt.json').read_bytes())
        pub(destination+'.json',r)
        for f in out.glob('*.log'):g.write_private(root/(destination+'-'+f.name),f.read_bytes())
    templates=root/'disabled-object-authorizations';templates.mkdir()
    card=ROOT/'node-b/docs'/('AUTH-B5-C-REPAIR-R4-TIME-CLOSE-SUPPLEMENT.md' if predecessor else 'AUTH-B5-C-REPAIR-R4-BATCH.md')
    template_dir=Path(pointer['diagnostic_R3_authorization_templates'])
    for f in template_dir.glob('*.json'):
        a=json.loads(f.read_text('utf8'));a.update(enabled=False,owner_approved=False,expires_unix=0,
            binding=str(root/'binding-private.json'),binding_sha256=binding_sha)
        if a.get('channel_profile'):
            profile=a['channel_profile'];a.update(scope=(channels.FINAL_SCOPES_R4TC if predecessor else channels.FINAL_SCOPES_R4)[profile],execution_card=card.name,
                C_application_card=card.name,card_sha256=sha(card.read_bytes()),tools_sha256=g.bindings(),
                C_application_binding=str(root/'binding-private.json'),C_application_binding_sha256=binding_sha,
                C_application_install_receipt='PENDING_REAL_R4_INSTALL',C_application_install_receipt_sha256=None,
                C_preflight_receipt='PENDING_REAL_R4_READONLY',C_preflight_receipt_sha256=None,
                site_record='PENDING_OWNER_CURRENT_FACTS',site_record_sha256=None,
                bundle='PENDING_FRESH_R4_BUNDLE',bundle_sha256=None,output=str(root/('window-'+profile)))
        else:a.update(card_name=card.name,card_sha256=sha(card.read_bytes()),tools_sha256=install.bindings(),
                site_record='PENDING_OWNER_CURRENT_FACTS',site_record_sha256=None,output=str(root/f.stem.replace('disabled-private','attempt')))
        g.save(templates/f.name,a)
    pub('object-bindings.json',dict(card_sha256=sha(card.read_bytes()),tools_sha256=g.bindings(),install_tools_sha256=install.bindings(),
        disabled_templates={f.name:sha(f.read_bytes()) for f in templates.glob('*.json')},enabled=False,
        install_scope=install.SCOPE,restore_scope=install.RESTORE,window_scopes=channels.FINAL_SCOPES_R4TC if predecessor else channels.FINAL_SCOPES_R4,
        current_owner_facts='ALL_POWER_OFF_REPORTED' if predecessor else 'JLINK_B_USB_C_BOTH_POWERED_WIRING_UNCHANGED',
        site_gate='PENDING_ONE_BATCH_CONFIRMATION_AND_COLD_TRANSFER_COMPLETION',
        cloud_state='NOT_FRESHLY_OBSERVED_THIS_OFFLINE_PHASE',B5START_attempts=0))
    g.save(root/'freeze-private.json',dict(candidate=candidate,resources=resources,builds=[str(args.build),str(args.repeat)]))
    (ROOT/'node-b/build'/('b5-repair-r4-time-close-pointer.json' if predecessor else 'b5-repair-r4-pointer.json')).write_text(json.dumps(dict(root=str(root),binding=str(root/'binding-private.json'),
        binding_sha256=binding_sha,templates=str(templates),public=str(public),build=str(args.build),repeat=str(args.repeat)))+'\n','utf8')
    print(json.dumps(dict(status='OFFLINE_FROZEN_HARDWARE_NOT_RUN',BIN_bytes=len(image),BIN_sha256=sha(image),
        expected_full_sha256=binding['after_full_sha256'],compiled_inputs=len(compiled))))

if __name__=='__main__':main()
