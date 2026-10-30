"""新增ECG/RR/TEMP分路工程范围；不修改或追补原G3 TEMP INVALID判据。"""
import base64
import json
from pathlib import Path
import re
import time
import b5_g3_contract as g
import b5_b_temp_update as update
import b5_b_temp_readonly as temp

SCOPE='B5_SEPARATE_CHANNEL_CLOUD_WINDOW'
CARD=g.ROOT/'node-b/docs/AUTH-B5-TEMP-AND-SEPARATE-CHANNELS-001-R2.md'
CONTINUE_CARD=g.ROOT/'node-b/docs/AUTH-B5-TEMP-AND-SEPARATE-CHANNELS-001-R3.md'
FINAL_CARD=g.ROOT/'node-b/docs/AUTH-B5-C-EGRESS-FINAL-THREE-WINDOWS-001-R1.md'
FINAL_SCOPES={name:'B5_FINAL_'+name+'_R1' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R2=g.ROOT/'node-b/docs/AUTH-B5-C-EGRESS-FINAL-THREE-WINDOWS-001-R2.md'
FINAL_SCOPES_R2={name:'B5_FINAL_'+name+'_R2' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R3=g.ROOT/'node-b/docs/AUTH-B5-C-EGRESS-DIAGNOSTIC-001-R3.md'
FINAL_SCOPES_R3={name:'B5_FINAL_'+name+'_R3' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R4=g.ROOT/'node-b/docs/AUTH-B5-C-REPAIR-R4-BATCH.md'
FINAL_SCOPES_R4={name:'B5_FINAL_'+name+'_R4' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R4TC=g.ROOT/'node-b/docs/AUTH-B5-C-REPAIR-R4-TIME-CLOSE-SUPPLEMENT.md'
FINAL_SCOPES_R4TC={name:'B5_FINAL_'+name+'_R4TC' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R4D=g.ROOT/'node-b/docs/AUTH-B5-C-REPAIR-R4-DIAGNOSTICS-SUPPLEMENT.md'
FINAL_SCOPES_R4D={name:'B5_FINAL_'+name+'_R4D' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R4TB=g.ROOT/'node-b/docs/AUTH-B5-C-REPAIR-R4-TIME-BOOTSTRAP-SUPPLEMENT.md'
FINAL_SCOPES_R4TB={name:'B5_FINAL_'+name+'_R4TB' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R4TI=g.ROOT/'node-b/docs/AUTH-B5-C-REPAIR-R4-TIME-INIT-SUPPLEMENT.md'
FINAL_SCOPES_R4TI={'ECG60':'B5_FINAL_ECG60_R4TI'}
FINAL_CARD_R5=g.ROOT/'node-b/docs/AUTH-B5-GEMINI-R5-THREE-WINDOWS.md'
FINAL_SCOPES_R5={name:'B5_FINAL_'+name+'_R5' for name in ('ECG60','TEMP_OBJECT','RR15')}
FINAL_CARD_R6=g.ROOT/'node-b/docs/AUTH-B5-R6-THREE-WINDOWS.md'
FINAL_SCOPES_R6={name:'B5_FINAL_'+name+'_R6' for name in ('ECG60','TEMP_OBJECT','RR15')}
PROFILES=('ECG60','TEMP_OBJECT','RR15')
# 历史基线 Node-B 固件指纹 (40928 字节)
B_PROFILE={'BIN_bytes':40928,'BIN_sha256':update.CANDIDATE_BIN,'slots':0x2000216c,
           'UART_ring':0x20004878,'RAM':temp.RAM}
B_ELF='e0433f3246e3e9aa422365834ceeae7e2e3c68360164a8bb583d7a45f4700ed1'
B_SYMBOLS='4c3e2ab42a3379c615924d8af4deb7e81207554bc1ef3d9e9ac79e977c9ecfcf'
# R6 候选微调度 Node-B 固件指纹 (41012 字节)
B_CANDIDATE_R6_BIN='1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d'
B_ELF_R6='e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7'
B_SYMBOLS_R6='07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8'
B_PROFILE_R6={'BIN_bytes':41012,'BIN_sha256':B_CANDIDATE_R6_BIN,'slots':0x2000216c,
              'UART_ring':0x20004878,'RAM':temp.RAM}
CLOUD_PACKAGE_SHA='dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0'
SOURCE_ECG=dict(g.SOURCE)
# RR15 模拟器工况：主呼吸率【RR】= 15 bpm（严禁设为 30 bpm！），阻抗变化量 1.5R，阻抗基准心率/周期菜单 30 bpm，窒息 0s
SOURCE_RR={'mode':'RESP','RR_bpm':15,'amplitude_menu_R':1.5,'waveform_period_bpm':30,'apnea_s':0,
           'leads':{'R':'RA','L':'LL/F','F':'RL/N','LA':'EMPTY'},'battery_no_USB':True,'no_human':True}

def criteria(profile):
    g.require(profile in PROFILES,'CHANNEL_PROFILE')
    c=dict(g.CRITERIA)
    c.update(profile=profile,TEMP='OBJECT_ENGINEERING_VALID' if profile=='TEMP_OBJECT' else 'OBSERVE_INDEPENDENTLY',
             expected_valid=['ECG','HR'] if profile=='ECG60' else ['RESP','RR'] if profile=='RR15' else ['TEMP'],
             HR_range=[58,62] if profile=='ECG60' else None,RR_range=[14,16] if profile=='RR15' else None,
             temperature_quantity='NONHUMAN_OBJECT_SURFACE',temperature_reference=None,
             temperature_accuracy='NOT_CALIBRATED',temperature_wire_time='NODE_SCALAR_REPORT_UTC_SECONDS',
             temperature_frame_age_max_ms=2500)
    if profile=='RR15':c['HR']='INVALID';c['RR']='VALID';c['ECG']='INVALID'
    return c

def ready_streams(streams,profile):
    if profile not in PROFILES:return False
    required=criteria(profile)['expected_valid']
    if any(n not in streams or streams[n]['validity']!='VALID' for n in required):return False
    if profile=='ECG60':return 58<=streams['HR']['value']<=62
    if profile=='RR15':return 14<=streams['RR']['value']<=16 and streams['HR']['validity']=='INVALID'
    return isinstance(streams['TEMP']['value'],(int,float)) and 0<=streams['TEMP']['value']<=100

def assert_snapshot(s,profile):
    g.require(profile in PROFILES,'CHANNEL_PROFILE')
    g.require(s.get('gateway_id')=='GW-B5-001' and s.get('nodes',{}).get('NODE-A')=='OFFLINE','CHANNEL_WSS_NAMESPACE')
    for x in s.get('streams',[]):
        g.require(x.get('source')=='MOCK' and x.get('synthetic') is True,'CHANNEL_WSS_SOURCE')
        if x['validity']!='VALID':g.require(x.get('value') is None and not x.get('samples'),'CHANNEL_WSS_INVALID_MASK')

def validate(a,*,execution_context='FIELD'):
    g.require(execution_context in ('FIELD','OFFLINE_MOCK'),'CHANNEL_EXECUTION_CONTEXT')
    g.require(a.get('enabled') is True and a.get('owner_approved') is True and
              a.get('scope') in (SCOPE,*FINAL_SCOPES.values(),*FINAL_SCOPES_R2.values(),*FINAL_SCOPES_R3.values(),*FINAL_SCOPES_R4.values(),*FINAL_SCOPES_R4TC.values(),*FINAL_SCOPES_R4D.values(),*FINAL_SCOPES_R4TB.values(),*FINAL_SCOPES_R4TI.values(),*FINAL_SCOPES_R5.values(),*FINAL_SCOPES_R6.values()),'CHANNEL_OWNER')
    profile=a.get('channel_profile');g.require(profile in PROFILES,'CHANNEL_PROFILE')
    final=a.get('scope') in (*FINAL_SCOPES.values(),*FINAL_SCOPES_R2.values(),*FINAL_SCOPES_R3.values(),*FINAL_SCOPES_R4.values(),*FINAL_SCOPES_R4TC.values(),*FINAL_SCOPES_R4D.values(),*FINAL_SCOPES_R4TB.values(),*FINAL_SCOPES_R4TI.values(),*FINAL_SCOPES_R5.values(),*FINAL_SCOPES_R6.values())
    final_card=FINAL_CARD_R6 if a.get('scope') in FINAL_SCOPES_R6.values() else FINAL_CARD_R5 if a.get('scope') in FINAL_SCOPES_R5.values() else FINAL_CARD_R4TI if a.get('scope') in FINAL_SCOPES_R4TI.values() else FINAL_CARD_R4TB if a.get('scope') in FINAL_SCOPES_R4TB.values() else FINAL_CARD_R4D if a.get('scope') in FINAL_SCOPES_R4D.values() else FINAL_CARD_R4TC if a.get('scope') in FINAL_SCOPES_R4TC.values() else FINAL_CARD_R4 if a.get('scope') in FINAL_SCOPES_R4.values() else FINAL_CARD_R3 if a.get('scope') in FINAL_SCOPES_R3.values() else FINAL_CARD_R2 if a.get('scope') in FINAL_SCOPES_R2.values() else FINAL_CARD
    final_scopes=FINAL_SCOPES_R6 if final_card==FINAL_CARD_R6 else FINAL_SCOPES_R5 if final_card==FINAL_CARD_R5 else FINAL_SCOPES_R4TI if final_card==FINAL_CARD_R4TI else FINAL_SCOPES_R4TB if final_card==FINAL_CARD_R4TB else FINAL_SCOPES_R4D if final_card==FINAL_CARD_R4D else FINAL_SCOPES_R4TC if final_card==FINAL_CARD_R4TC else FINAL_SCOPES_R4 if final_card==FINAL_CARD_R4 else FINAL_SCOPES_R3 if final_card==FINAL_CARD_R3 else FINAL_SCOPES_R2 if final_card==FINAL_CARD_R2 else FINAL_SCOPES
    if final:g.require(a['scope']==final_scopes.get(profile) and a.get('require_source_STOP_state') is True,'CHANNEL_FINAL_OBJECT')
    version=None
    if final:
        version='R6' if final_card==FINAL_CARD_R6 else 'R5' if final_card==FINAL_CARD_R5 else 'R4TI' if final_card==FINAL_CARD_R4TI else 'R4TB' if final_card==FINAL_CARD_R4TB else 'R4D' if final_card==FINAL_CARD_R4D else 'R4TC' if final_card==FINAL_CARD_R4TC else 'R4' if final_card==FINAL_CARD_R4 else 'R3' if final_card==FINAL_CARD_R3 else 'R2' if final_card==FINAL_CARD_R2 else 'R1'
    if version=='R6':
        expected_b_elf=B_ELF_R6
        expected_b_symbols=B_SYMBOLS_R6
        expected_b_bin_bytes=B_PROFILE_R6['BIN_bytes']
        expected_b_bin_sha=B_PROFILE_R6['BIN_sha256']
        active_b_profile=B_PROFILE_R6
    else:
        expected_b_elf=B_ELF
        expected_b_symbols=B_SYMBOLS
        expected_b_bin_bytes=B_PROFILE['BIN_bytes']
        expected_b_bin_sha=update.CANDIDATE_BIN
        active_b_profile=B_PROFILE
    g.require(a.get('tools_sha256')==g.bindings() and a.get('criteria')==criteria(profile),'CHANNEL_FROZEN_BINDING')
    g.require(a.get('environment')==g.environment(),'CHANNEL_ENVIRONMENT')
    selected=a.get('execution_card',CARD.name)
    g.require(selected in (CARD.name,CONTINUE_CARD.name,FINAL_CARD.name,FINAL_CARD_R2.name,FINAL_CARD_R3.name,FINAL_CARD_R4.name,FINAL_CARD_R4TC.name,FINAL_CARD_R4D.name,FINAL_CARD_R4TB.name,FINAL_CARD_R4TI.name,FINAL_CARD_R5.name,FINAL_CARD_R6.name),'CHANNEL_CARD')
    g.require((selected in (FINAL_CARD.name,FINAL_CARD_R2.name,FINAL_CARD_R3.name,FINAL_CARD_R4.name,FINAL_CARD_R4TC.name,FINAL_CARD_R4D.name,FINAL_CARD_R4TB.name,FINAL_CARD_R4TI.name,FINAL_CARD_R5.name,FINAL_CARD_R6.name))==final and (not final or selected==final_card.name),'CHANNEL_FINAL_CARD')
    card=final_card if final else CARD if selected==CARD.name else CONTINUE_CARD
    g.require(a.get('card_sha256')==g.sha(card.read_bytes()),'CHANNEL_CARD')
    if version=='R6':
        # 离线调用上下文不能由授权JSON选择；现场在P1-A期间始终拒止。
        g.require(execution_context=='OFFLINE_MOCK' and a.get('execution_mode')=='OFFLINE_MOCK',
                  'CHANNEL_R6_FIELD_EXECUTION_BLOCKED_UNSIGNED_FREEZE')
    if selected in (CONTINUE_CARD.name,FINAL_CARD.name,FINAL_CARD_R2.name,FINAL_CARD_R3.name,FINAL_CARD_R4.name,FINAL_CARD_R4TC.name,FINAL_CARD_R4D.name,FINAL_CARD_R4TB.name,FINAL_CARD_R4TI.name,FINAL_CARD_R5.name,FINAL_CARD_R6.name):
        g.require(a.get('reset_confirmation')=='SERIAL_DISARMED_AFTER_INTENT' and
                  a.get('owner_manual_reset_preapproved') is True,'CHANNEL_RESET_CONFIRMATION')
    else:g.require(a.get('reset_confirmation') in (None,'OWNER_CHAT'),'CHANNEL_RESET_CONFIRMATION')
    g.require(a.get('expires_unix',0)>time.time() and a.get('retries')==0,'CHANNEL_EXPIRY')
    g.require(a.get('B5START_allowed') is True and a.get('start_max')==1 and
              a.get('precommon_ntp_retries_max') in (0,2),'CHANNEL_START_ONCE')
    g.require(a.get('operator_wait_extra_s')==180 and a.get('host_cancel_cleanup_s')==10,'CHANNEL_WAIT_BUDGET')
    g.require(a.get('test_service_expiry_unix',0)>time.time()+805,'CHANNEL_CLOUD_RESIDENCY')
    g.require(a.get('DLL_sha256')==temp.raw.DLL_SHA,'CHANNEL_DLL')
    raw=g.private.read(Path(a['bundle']),False);g.require(g.sha(raw)==a['bundle_sha256'],'CHANNEL_BUNDLE')
    bundle=json.loads(raw)
    for key in ('B_identity','B_full','B_options','C_identity','C_full','C_options','B_ELF','B_symbols','cloud_package','cloud_credentials'):
        ref=bundle[key];g.require(g.sha(g.private.read(Path(ref['path']),False))==ref['sha256'],'CHANNEL_REFERENCE_DRIFT')
    g.require(bundle['B_ELF']['sha256']==expected_b_elf and bundle['B_symbols']['sha256']==expected_b_symbols,'CHANNEL_B_ABI')
    before=g.private.read(Path(bundle['B_full']['path']),False)
    g.require(len(before)>=expected_b_bin_bytes and g.sha(before[:expected_b_bin_bytes])==expected_b_bin_sha,'CHANNEL_B_IMAGE')
    proofraw=g.private.read(Path(a['B_install_receipt']),False);proof=json.loads(proofraw)
    g.require(g.sha(proofraw)==a['B_install_receipt_sha256'] and proof.get('exit_code')==0 and
              proof.get('status')=='B_TEMP_INSTALL_FULL_VERIFY_AND_FLASH_BOOT_PASS' and proof.get('Close_completed') is True and
              proof.get('full_flash_sha256')==bundle['B_full']['sha256'],'CHANNEL_B_INSTALL')
    if 'candidate_bin_sha256' in proof:
        g.require(proof['candidate_bin_sha256']==expected_b_bin_sha,'CHANNEL_B_INSTALL_CANDIDATE')
    ro_raw=g.private.read(Path(a['B_temperature_receipt']),False);ro=json.loads(ro_raw)
    g.require(g.sha(ro_raw)==a['B_temperature_receipt_sha256'] and ro.get('exit_code')==0 and
              ro.get('status')=='B_TEMP_READONLY_CAPTURED' and ro.get('new_valid_frames',0)>0 and
              ro.get('Close_completed') is True and ro.get('full_flash_sha256')==bundle['B_full']['sha256'],'CHANNEL_B_TEMP_INPUT')
    cfull=g.expected_c_full(a,bundle)
    if final:
        frozen=json.loads((g.ROOT/('node-b/evidence/'+('B5-C-REPAIR-R4/TIME-INIT-R1' if version in ('R4TI','R5','R6') else 'B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2' if version=='R4TB' else 'B5-C-REPAIR-R4/DIAGNOSTICS-R1' if version=='R4D' else 'B5-C-REPAIR-R4/TIME-CLOSE-R1' if version=='R4TC' else 'B5-C-REPAIR-R4' if version=='R4' else 'B5-C-EGRESS-FINAL-'+version)+'/candidate.json')).read_text())
        g.require(frozen['status']=='FROZEN_SOFTWARE_PASS' and cfull==frozen['expected_new_full_sha256'] and
                  g.load(a['C_application_binding'])['candidate_sha256']==frozen['BIN_sha256'],'CHANNEL_FINAL_CANDIDATE')
    cproof_raw=g.private.read(Path(a['C_preflight_receipt']),False);cp=json.loads(cproof_raw)
    g.require(g.sha(cproof_raw)==a['C_preflight_receipt_sha256'] and cp.get('exit_code')==0 and
              cp.get('status')=='C_CURRENT_B5_CONFIG_DISARMED_READONLY_PASS' and cp.get('full_sha256')==cfull and
              time.time()-cp['observed_unix']<=(86400 if version=='R5' else 3600),'CHANNEL_C_PREFLIGHT')
    P=g.load(bundle['cloud_package']['path'])
    g.require(bundle['cloud_package']['sha256']==CLOUD_PACKAGE_SHA,'CHANNEL_CLOUD_PACKAGE')
    g.require(all(g.sha(base64.b64decode(P['sources']['backend/app/'+n]))==v
                  for n,v in g.environment()['Backend_sources'].items()),'CHANNEL_BACKEND_DRIFT')
    blob=g.private.read(Path(a['site_record']),False);g.require(g.sha(blob)==a['site_record_sha256'],'CHANNEL_SITE_SHA')
    site=json.loads(blob);expected=SOURCE_RR if profile=='RR15' else SOURCE_ECG
    g.require(site.get('source')==expected and site.get('temperature_source')=='GY641V3_NONHUMAN_OBJECT_NO_REFERENCE','CHANNEL_SOURCE')
    g.require(site.get('JLink_target')=='B' and site.get('C_USB_connector')=='USB_UART/USB232' and
              site.get('C_USB_port')==a.get('COM') and re.fullmatch(r'COM[1-9][0-9]{0,4}',a.get('COM','')),'CHANNEL_ROUTE')
    g.require(all(site.get(k) is True for k in ('COM_confirmed','C_J5','B_J5','CAN_GND_unchanged','A_disconnected',
              'INMP441_TTS_disconnected','ESP_present_powered_exception','operator_ready_manual_cutoff',
              'one_C_reset_preplanned_only','B_USB_disconnected','exclusive_test_namespace')),'CHANNEL_SITE_FACTS')
    g.require(a.get('observer_username')=='b5-observer' and a.get('observer_client_id','').startswith('b5-g3-observer-') and
              len(a['observer_client_id'])<=60,'CHANNEL_OBSERVER_IDENTITY')
    g.private.protected(Path(a['output']).parent,False)
    bundle['_B_profile']=active_b_profile;bundle['_expected_C_full_sha256']=cfull
    if final:bundle['_require_source_STOP_state']=True
    return bundle,site
