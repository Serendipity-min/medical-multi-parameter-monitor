"""P1-B薄入口候选。CLI现场默认拒止；只读核心由已授权调用方提供适配器。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

ROOT=Path(__file__).resolve().parents[2]
SCOPE={b:'CODEX_P1B_READONLY_'+b for b in ('B','C')}
IMAGES={'B':(40928,'a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2',
                'ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae'),
        'C':(49132,'72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab',
                '9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd')}
SHA=lambda data:hashlib.sha256(data).hexdigest()
STATE={'DHCSR':0xe000edf0,'VTOR':0xe000ed08,'CFSR':0xe000ed28,'HFSR':0xe000ed2c,'PCSR':0xe000101c}


def need(ok,reason):
    if not ok:raise ValueError(reason)


def plan(board):
    return {'enabled':False,'scope':SCOPE[board],'board':board,'field_status':'P1B_FIELD_NOT_AUTHORIZED',
            'target_definition':'HISTORICAL_P1B0_BASELINE_NOT_A_CURRENT_HARDWARE_CLAIM',
            'tool_sha256':SHA(Path(__file__).read_bytes()),'trust_root':'NOT_CONFIGURED',
            'full_flash':[0x08000000,1048576,1],'options':[0x1fffc000,16,1],
            'identity_state_source':'existing G3 BLink/CLink exact whitelist',
            'session_s':90,'full_read_s':45,'other_call_s':5,'retries':0}


def verify_mock_authorization(raw,signature,public_key,pinned_key_sha,expected,now):
    """只做数学验签与绑定校验；生产信任根尚未配置，CLI不据此放行。"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    required={'board','repo_commit','repo_tree','tools_sha256','DLL_sha256','identity_reference_sha256',
              'options_reference_sha256','full_flash_sha256','reads','budget','site_sha256',
              'manual_responsibility','sdk_policy'}
    need(set(expected)==required,'P1B_INCOMPLETE_TRUSTED_BINDING')
    need(pinned_key_sha is not None and SHA(public_key)==pinned_key_sha,'P1B_UNTRUSTED_KEY')
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature,raw)
    a=json.loads(raw)
    board=expected['board']
    need(board in SCOPE and a.get('board')==board and a.get('scope')==SCOPE[board],'P1B_BOARD_SCOPE')
    need(a.get('not_before',now+1)<=now<a.get('expires',0),'P1B_AUTH_TIME')
    for key,value in expected.items():need(a.get(key)==value,'P1B_BINDING_'+key.upper())
    need(a.get('sdk_risk_acknowledged') is True,'P1B_SDK_RISK_NOT_ACKNOWLEDGED')
    need(isinstance(a.get('nonce'),str) and 16<=len(a['nonce'])<=128,'P1B_NONCE')
    return a


def consume_mock_nonce(directory,raw,a,*,execution_context):
    need(execution_context=='OFFLINE_MOCK','P1B_NONCE_CONTEXT')
    marker={'authorization_sha256':SHA(raw),'board':a['board'],'scope':a['scope'],'nonce_sha256':SHA(a['nonce'].encode())}
    path=directory/(marker['nonce_sha256']+'.used')
    with path.open('x',encoding='utf-8') as stream:json.dump(marker,stream,sort_keys=True)
    return path


def validate_worker_marker(path,raw,a):
    marker=json.loads(path.read_text())
    need(marker=={'authorization_sha256':SHA(raw),'board':a['board'],'scope':a['scope'],
                  'nonce_sha256':SHA(a['nonce'].encode())},'P1B_PARENT_MARKER_MISMATCH')


def read_state(link,image_bytes,save_state):
    s={key:link.u32(address) for key,address in STATE.items()}
    pcs=[s['PCSR'],link.u32(STATE['PCSR']),link.u32(STATE['PCSR'])]
    s['pc_samples']=pcs;save_state(s)
    need(not s['DHCSR']&((1<<17)|(1<<19)|(1<<25)),'P1B_CPU_HALT_LOCKUP_RESET')
    need(not(s['CFSR']|s['HFSR']),'P1B_CPU_FAULT')
    need(s['VTOR'] in (0,0x08000000),'P1B_CPU_ROM_OR_VTOR')
    need(not any(0x1fff0000<=p<0x1fff7800 for p in pcs),'P1B_CPU_ROM')
    need(any(0x08000000<=p<0x08000000+image_bytes for p in pcs),'P1B_RUNNING_PC_NOT_PROVEN')
    return s


def capture(link,board,reference,save,*,clock=time.monotonic):
    """复用已审Link；调用方承担当期真实授权，函数不接收授权JSON或制造token。"""
    need(board in IMAGES,'P1B_BOARD')
    started=clock();size,image_sha,full_sha=IMAGES[board]
    r={'board':board,'status':'STOP_TARGET_NO_RECOVERY','exit_code':1,'Close_attempted':False,
       'Close_completed':False,'last_known_target':'UNKNOWN','SDK_residual_risk':'UNRESOLVED',
       'explicit_reset_halt_go_writes':0,'retries':0}
    try:
        link.open()
        # 复用旧工具的身份读取，不调用含Halt/Go的acquire。
        import readback_b as raw
        identity=raw.identity(link);save('identity-private.json',identity)
        need(identity==reference['identity'],'P1B_WRONG_BOARD_IDENTITY')
        r['identity_matches']=True
        sticky=link.u32(STATE['DHCSR']);save('entry-sticky-private.json',{'DHCSR':sticky})
        state=read_state(link,size,lambda state:save('entry-state-private.json',state))
        r['last_known_target']='RUNNING_FLASH_OBSERVED_BEFORE_CLOSE'
        full=link.read(0x08000000,1048576);save('full-private.bin',full)
        options=link.read(0x1fffc000,16);save('options-private.bin',options)
        need(SHA(full)==full_sha and SHA(full[:size])==image_sha,'P1B_FLASH_IDENTITY_DRIFT')
        need(SHA(options)==reference['options_sha256'],'P1B_OPTIONS_DRIFT')
        if state['VTOR']==0:need(link.read(0,64)==full[:64],'P1B_VECTOR_ALIAS')
        if board=='C':
            flags=link.read(reference['flags_address'],4);save('flags-private.bin',flags)
            need(flags==bytes(4),'P1B_C_NOT_DISARMED')
        final=read_state(link,size,lambda state:save('exit-state-private.json',state))
        need(clock()-started<=90,'P1B_SESSION_TIMEOUT')
        r.update(status=board+'_HISTORICAL_FLASH_OPTIONS_IDENTITY_MATCH',exit_code=0,
                 full_flash_sha256=SHA(full),options_sha256=SHA(options))
    except BaseException as error:
        reason=str(error)
        safe=reason.startswith(('P1B_','G3_','LIVE_','PROBE_','POLICY_','SDK_','RUNTIME_','TARGET_')) and re.fullmatch(r'[A-Z0-9_]+',reason)
        r.update(reason=reason if safe else 'PRIVATE_ERROR_SUPPRESSED',
                 error_type=type(error).__name__,error_sha256=SHA(reason.encode()),
                 last_known_target='UNKNOWN_OR_STOPPED_NO_RECOVERY',manual_power_policy_required=True)
    finally:
        r['Close_attempted']=True
        r['native_Close_expected']=bool(getattr(link,'opened',False))
        try:
            link.close();r['Close_completed']=True
        except BaseException as error:
            r.update(status='STOP_TARGET_NO_RECOVERY',exit_code=1,Close_completed=False,close_error_type=type(error).__name__,manual_power_policy_required=True)
        r['target_state_after_Close']='UNKNOWN_NOT_OBSERVED'
        r['elapsed_s']=clock()-started
        save('receipt-private.json',r)
    return r


def killed_receipt(last_known):
    return {'status':'STOP_TARGET_NO_RECOVERY','exit_code':1,'Close_attempted':'UNKNOWN_PROCESS_KILLED',
            'Close_completed':False,'last_known_target':last_known,'target_state_after_Close':'UNKNOWN',
            'manual_power_policy_required':True,'retries':0}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board',choices=('B','C'),default='B')
    parser.add_argument('--plan',action='store_true');parser.add_argument('--execute',action='store_true')
    parser.add_argument('--authorization',type=Path);args=parser.parse_args()
    if args.execute:
        print(json.dumps({'status':'P1B_FIELD_NOT_AUTHORIZED','exit_code':1}));return 1
    print(json.dumps(plan(args.board)));return 0


if __name__=='__main__':raise SystemExit(main())
