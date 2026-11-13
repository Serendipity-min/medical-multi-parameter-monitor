"""M1-P0独立B采集薄入口；现场CLI禁用，复用原BLink/快照/原码格式。"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'B5_M1_NODE_B_MULTIRATE_165S_R1'
MATRIX = ROOT/'node-b/docs/CODEX-M0-MULTIRATE-20261031/MULTIRATE-MATRIX.proposed.json'
PRIVATE = Path('E:/medical-monitor-node-b-precan-private/20261023')
BIN_SHA = '1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d'
AXF_SHA = 'e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7'
SYMBOLS_SHA = '07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8'
FULL_SHA = '9ff8133d06330a4b05cb15d26bfb51b6f7e1197014692c5267d178d744f4287d'
OPTIONS_SHA = '52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687'
BLOCK_BYTES = 5692
RAM = {'bio': (0x20001d20,120), 'adc': (0x20000614,48), 'registers': (0x20000644,12),
       'CAN': (0x2000377c,44), 'temperature': (0x20004c78,64)}
SLOTS = 0x2000216c
BUDGET = {'preflight_s':75, 'capture_s':165, 'cleanup_s':20, 'session_s':260,
          'supervisor_s':265, 'native_read_s':5, 'native_full_read_s':45, 'native_close_s':5,
          'sdk_calls':20000, 'close_reserved_calls':64, 'blocks':3304, 'poll_s':.05, 'diagnostic_s':.5}
TRUSTED_PI_KEY_SHA256 = None  # 尚未由PI配置；不能从授权JSON/命令行自取信任根。


def sha(data): return hashlib.sha256(data).hexdigest()
def need(ok, code):
    if not ok: raise ValueError(code)
def save(path, obj):
    with path.open('x', encoding='utf-8') as f: json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n')


def plan(run_id='M1-E60-R1'):
    matrix = json.loads(MATRIX.read_text(encoding='utf-8'))
    run = next((r for r in matrix['execution_order'] if r['run_id']==run_id), None)
    need(run is not None, 'M1_UNKNOWN_RUN')
    condition = next(c for c in matrix['conditions'] if c['id']==run['condition'])
    return {'schema':'M1_CAPTURE_PLAN_R1','scope':SCOPE,'enabled':False,'run_id':run_id,
            'condition':condition['id'],'target':condition['target'],'matrix_sha256':sha(MATRIX.read_bytes()),
            'M0_card':run['disabled_card'],'M0_card_sha256':run['disabled_card_sha256'],
            'BIN_bytes':41012,'BIN_sha256':BIN_SHA,'AXF_sha256':AXF_SHA,'symbols_sha256':SYMBOLS_SHA,
            'RAM':RAM,'slots':SLOTS,'block_bytes':BLOCK_BYTES,'budget':BUDGET,
            'warmup_ms':[0,45000],'evaluation_ms':[45000,165000],
            'RESP50':'derived seq%5; retain original CH1/CH2 250Hz',
            'trust_root':'NOT_CONFIGURED','field_execution':'DISABLED_IN_P0','native_side_effects':'UNRESOLVED'}


def plan_hash(run_id):return sha(json.dumps(plan(run_id),sort_keys=True,separators=(',',':')).encode())


def tool_bindings():
    found={};pending=[Path(__file__),Path(__file__).with_name('b5_m1_review.py')]
    while pending:
        path=pending.pop();name=path.relative_to(ROOT).as_posix()
        if name in found:continue
        data=path.read_bytes();found[name]=sha(data)
        for node in ast.walk(ast.parse(data.decode('utf-8-sig'))):
            modules=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for module in modules:
                source=ROOT/'node-b/tools'/(module.split('.')[0]+'.py')
                if source.is_file() and source.relative_to(ROOT).as_posix() not in found:pending.append(source)
    return found


def verify_signed_card(raw, signature, public_key, trusted_pin, expected, now):
    """纯验签/绑定校验；expected和pin必须由可信调用方固定，不能取自来件。"""
    need(trusted_pin is not None and sha(public_key)==trusted_pin, 'M1_UNTRUSTED_PI_KEY')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, raw)
    a = json.loads(raw)
    required = {'scope','run_id','plan_sha256','repo_commit','repo_tree','tools_sha256','DLL_sha256',
                'bundle_sha256','site_sha256','cold_start_sha256','output','manual_stop_responsibility'}
    need(set(expected)==required and expected['scope']==SCOPE, 'M1_INCOMPLETE_TRUSTED_BINDING')
    need(all(a.get(k)==v for k,v in expected.items()), 'M1_SIGNED_BINDING_DRIFT')
    need(a.get('enabled') is True and a.get('sessions')==1 and a.get('retries')==0, 'M1_DISABLED_OR_COUNT')
    need(a.get('not_before',now+1)<=now<a.get('expires',0), 'M1_AUTH_TIME')
    need(a.get('sdk_residual_risk_acknowledged') is True, 'M1_NATIVE_RISK_NOT_ACKNOWLEDGED')
    need(isinstance(a.get('nonce'),str) and 16<=len(a['nonce'])<=128, 'M1_NONCE')
    need(all(expected[k] for k in required), 'M1_EMPTY_BINDING')
    return a


def consume_nonce(directory, raw, a):
    marker = directory/(sha((SCOPE+'\0'+a['nonce']).encode())+'.used')
    save(marker, {'scope':SCOPE,'run_id':a['run_id'],'authorization_sha256':sha(raw)})
    return marker


def seal_capture(out, raw, signature, public_key, expected):
    for name,data in [('authorization-private.json',raw),('authorization-signature.bin',signature),('authorization-public-key.bin',public_key)]:
        with (out/name).open('xb') as f:f.write(data)
    save(out/'B/input-hashes-private.json',{p.name:sha(p.read_bytes()) for p in (out/'B').iterdir() if p.is_file()})
    save(out/'authorization-binding-private.json',{'scope':SCOPE,'run_id':expected['run_id'],
        'authorization_sha256':sha(raw),'signature_sha256':sha(signature),'public_key_sha256':sha(public_key),
        'cold_start_sha256':expected['cold_start_sha256'],'nonce_ledger_consumed':True,
        'capture_input_manifest_sha256':sha((out/'B/input-hashes-private.json').read_bytes())})


def run_authorized_capture(raw, signature, public_key, trusted_pin, expected, reference, factory, nonce_directory,
                           *, clock=time.monotonic, sleep=time.sleep, now=time.time):
    a=verify_signed_card(raw,signature,public_key,trusted_pin,expected,now())
    need(expected['plan_sha256']==plan_hash(a['run_id']), 'M1_PLAN_BINDING')
    need(reference['cold_start_sha256']==expected['cold_start_sha256'], 'M1_COLD_RECORD_BINDING')
    out=Path(expected['output']);need(not out.exists(), 'M1_OUTPUT_EXISTS')
    consume_nonce(nonce_directory,raw,a)
    result=capture_window(factory,out,reference,clock=clock,sleep=sleep)
    seal_capture(out,raw,signature,public_key,expected)
    return result


def validate_bundle(bundle):
    """只接纳已安装的同次制品链；路径由受限bundle提供，原件只读。"""
    for key, expected in [('BIN',BIN_SHA),('AXF',AXF_SHA),('symbols',SYMBOLS_SHA)]:
        need(sha(Path(bundle[key]).read_bytes())==expected, 'M1_ARTIFACT_'+key.upper())
    need(bundle['BIN_bytes']==41012 and bundle['RAM']=={k:list(v) for k,v in RAM.items()}
         and bundle['slots']==SLOTS, 'M1_SYMBOL_MAPPING')
    need(bundle['full_sha256']==FULL_SHA and bundle['options_sha256']==OPTIONS_SHA,'M1_INSTALLED_REFERENCE_DRIFT')


def link_class():
    # 仅由未来已授权调用方在验签、nonce消耗之后构造；P0 CLI没有该路径。
    from b5_g3_devices import BLink
    import readback_b
    class M1Link(BLink):
        def __init__(self,out,root):
            self.phase='preflight';self.deadline=time.monotonic()+BUDGET['preflight_s']
            super().__init__(out,root,profile={'RAM':RAM,'slots':SLOTS,'UART_ring':0x20004878})
            from runtime_state_b import SYSTEM
            self.allowed_reads={a:{4} for a in SYSTEM.values()}
            self.allowed_reads.update({0xe000ed00:{4},0xe0042000:{4},0x40023c14:{4},0x40023c0c:{4},
                0x40023c10:{4},
                0x1fff7a10:{12},0x1fff7a22:{2},0x1fffc000:{16},0x08000000:{64,41012,1048576},
                0:{64},0x40006418:{4},SLOTS:{BLOCK_BYTES}})
            for address,size in RAM.values():self.allowed_reads.setdefault(address,set()).add(size)
        def gate(self):
            need(not (self.root/'STOP').exists(), 'M1_OPERATOR_STOP')
            need(time.monotonic()<=self.deadline, 'M1_PHASE_TIMEOUT')
            need(time.monotonic()-self.started<=BUDGET['session_s'], 'M1_SESSION_TIMEOUT')
            need(not self.error, 'M1_NATIVE_CALLBACK_ERROR')
        def call(self,name,*args,timeout=5):
            limit=BUDGET['sdk_calls']-(0 if self.phase=='closing' else BUDGET['close_reserved_calls'])
            need(self.sdk_calls<limit, 'M1_SDK_BUDGET')
            counts=getattr(self,'m1_counts',{});key=None;maximum=None
            if name in ('JLINKARM_OpenEx','JLINKARM_Connect','JLINKARM_EMU_GetNumDevices','JLINKARM_SelectUSB'):
                key=name;maximum=1
            if name=='JLINKARM_ReadMemEx' and args[:2] in ((0x08000000,1048576),(0x08000000,41012),(0x1fffc000,16),(SLOTS,BLOCK_BYTES)):
                key=args[:2];maximum=BUDGET['blocks'] if key==(SLOTS,BLOCK_BYTES) else 1
            if key is not None:
                need(counts.get(key,0)<maximum,'M1_NATIVE_OPERATION_COUNT');counts[key]=counts.get(key,0)+1;self.m1_counts=counts
            return super().call(name,*args,timeout=timeout)
    return M1Link


def native_link(out,root):return link_class()(out,root)


def capture_window(factory, out, reference, *, clock=time.monotonic, sleep=time.sleep):
    """受信调用方先验签/消耗nonce；factory用于隔离原生设备和离线测试。"""
    import b4_runtime as live
    import readback_b as raw
    from b5_g3_contract import decode_block
    out.mkdir(exist_ok=False);b=out/'B';b.mkdir()
    link=None;started=clock()
    result={'status':'M1_STOP','exit_code':1,'Close_attempted':False,'Close_completed':False,
            'native_side_effects':'UNRESOLVED','post_Close_state':'UNKNOWN_NOT_OBSERVED','retries':0,
            'explicit_RESET_HALT_GO_Flash_START':0}
    try:
        link=factory(b,out);need(not (out/'STOP').exists(),'M1_OPERATOR_STOP');link.open()
        identity=raw.identity(link);raw.check_identity(identity);save(b/'identity-private.json',identity)
        need(identity==reference['identity'], 'M1_WRONG_BOARD')
        save(b/'entry-sticky-private.json',{'DHCSR':link.u32(live.ro.SYSTEM['DHCSR'])})
        full=link.read(0x08000000,1048576);(b/'full-private.bin').write_bytes(full)
        options=link.read(0x1fffc000,16);(b/'options-private.bin').write_bytes(options)
        need(sha(full)==reference['full_sha256'] and sha(full[:41012])==reference['BIN_sha256'], 'M1_FIRMWARE_DRIFT')
        need(sha(options)==reference['options_sha256'], 'M1_OPTIONS_DRIFT')
        first=live.snapshot(link,b,'entry',RAM)
        maximum_uptime=reference['maximum_cold_start_uptime_ms']
        need(maximum_uptime is None or first['bio']['last_sample_ms']<=maximum_uptime, 'M1_COLD_BOOT_NOT_FRESH')
        sleep(2)
        ready=live.snapshot(link,b,'ready',RAM);live.assess(first,ready)
        need(clock()-started<=BUDGET['preflight_s'], 'M1_PREFLIGHT_TIMEOUT')
        capture_started=clock();capture_io_s=reference.get('capture_io_s',BUDGET['capture_s'])
        link.phase='capture'
        # 原码窗仍165秒；负责人台架路线单独留I/O余量，总会话内预留原收尾预算。
        link.deadline=min(capture_started+capture_io_s,started+BUDGET['session_s']-BUDGET['cleanup_s'])
        previous=None;anchor=None;high_previous=None;last=ready;n=0;next_diag=capture_started
        with (b/'blocks-private.bin').open('xb') as blocks, (b/'blocks-private.jsonl').open('x',encoding='utf-8') as index, \
             (b/'diagnostics-private.jsonl').open('x',encoding='utf-8') as diag:
            while True:
                need(not (out/'STOP').exists(), 'M1_OPERATOR_STOP')
                need(clock()<link.deadline and n<BUDGET['blocks'], 'M1_CAPTURE_BUDGET')
                before=clock();state=link.u32(live.ro.SYSTEM['DHCSR'])
                need(not state&(raw.HALT|raw.LOCKUP|raw.RESET), 'M1_CPU_CHANGED')
                block=link.read(SLOTS,BLOCK_BYTES);need(len(block)==BLOCK_BYTES,'M1_BLOCK_SHORT_READ')
                blocks.write(block);blocks.flush()
                index.write(json.dumps({'kind':'B_BLOCK','data':{'index':n,'offset':n*BLOCK_BYTES,
                    'read_start':before,'read_end':clock(),'sha256':sha(block)}})+'\n');index.flush()
                frames={seq:frame for seq,frame,_ in decode_block(block)[0]}
                need(bool(frames), 'M1_NO_RAW_FRAMES')
                if previous is not None and anchor is None:
                    stable=[(s,f) for s,f in frames.items() if previous.get(s)==f]
                    need(bool(stable), 'M1_NO_STABLE_ANCHOR')
                    seq,frame=min(stable);anchor={'seq':seq,'ms':struct.unpack_from('<I',frame,20)[0]}
                    save(b/'window-private.json',{'schema':'M1_RAW_WINDOW_R1','anchor':anchor,
                        'duration_ms':165000,'warmup_ms':45000,'evaluation_ms':120000,
                        'source':'FIRST_QUALIFIED_RAW_NOT_FIRST_VALID_HR'})
                high=max(struct.unpack_from('<I',f,20)[0] for f in frames.values())
                need(high_previous is None or high>=high_previous, 'M1_RAW_BOOT_OR_TICK_RESTART')
                if clock()>=next_diag:
                    current=live.snapshot(link,b,'diag-'+str(n),RAM);live.assess(last,current);last=current
                    diag.write(json.dumps({'kind':'B_DIAG','data':current})+'\n');diag.flush();next_diag+=.5
                n+=1
                # 两次读均覆盖评价末端，保证稳定槽边界；最老原码锚有约半秒环形缓冲余量。
                if anchor and high_previous is not None and high_previous>=anchor['ms']+165000 and high>=anchor['ms']+165000:break
                previous=frames;high_previous=high
                sleep(max(0,.05-(clock()-before)))
        capture_elapsed=clock()-capture_started;need(capture_elapsed<=capture_io_s, 'M1_CAPTURE_OVERRUN')
        link.phase='closing';link.deadline=clock()+BUDGET['cleanup_s']
        final=live.snapshot(link,b,'final',RAM);live.assess(last,final)
        need(sha(link.read(0x08000000,41012))==reference['BIN_sha256'], 'M1_POST_IMAGE_DRIFT')
        need(raw.identity(link)==reference['identity'], 'M1_POST_IDENTITY_DRIFT')
        link.final_close_verified=True;link.set_close_resume(True)
        result.update(status='M1_CAPTURED_REVIEW_PENDING',exit_code=0,blocks=n,anchor=anchor,
                      capture_host_s=capture_elapsed,full_sha256=sha(full))
    except (Exception,KeyboardInterrupt,SystemExit) as error:
        if link:link.verified_running_flash=False;link.final_close_verified=False
        reason=str(error);code=reason if reason.startswith(('M1_','G3_','B4_','C_RO_','RESP_')) and reason.replace('_','').isalnum() else 'PRIVATE_ERROR'
        result.update(reason=code,error_type=type(error).__name__,error_sha256=sha(reason.encode()))
        if code in ('M1_OPERATOR_STOP','M1_CAPTURE_BUDGET','M1_PHASE_TIMEOUT','M1_SDK_BUDGET'):result['exit_code']=4
        save(b/'failure-private.json',{'type':type(error).__name__,'reason':reason})
    finally:
        if link is not None:
            result['Close_attempted']=True
            try:
                before_close=clock();link.close();result['Close_completed']=True
                need(clock()-before_close<=BUDGET['native_close_s'],'M1_CLOSE_TIMEOUT')
            except Exception as error:
                result.update(status='M1_STOP',exit_code=1,close_error_type=type(error).__name__)
        result['elapsed_s']=clock()-started
        if clock()-started>BUDGET['session_s']:result.update(status='M1_STOP',exit_code=4,reason='M1_SESSION_TIMEOUT')
        save(b/'receipt-private.json',result)
    return result


def watch_worker(child, root, *, clock=time.monotonic, sleep=time.sleep):
    started=clock();reason=None;monitor_error=None
    try:
        while child.poll() is None:
            if (root/'STOP').exists():reason='M1_OPERATOR_STOP'
            elif clock()-started>BUDGET['supervisor_s']:reason='M1_SUPERVISOR_HARD_STOP'
            heartbeat=root/'B/heartbeat-events.jsonl'
            if heartbeat.exists():
                rows=heartbeat.read_text(encoding='utf-8').splitlines()
                # 只读完整心跳行；并发末行未写完不能伪装SDK超时。
                for line in reversed(rows):
                    try:event=json.loads(line);break
                    except json.JSONDecodeError:continue
                else:event={}
                if event.get('active') and clock()>event['deadline_monotonic']:reason='M1_NATIVE_TIMEOUT'
            if reason:child.kill();break
            sleep(.05)
    except BaseException as error:
        # 监视器本身失败/被中断也先终止唯一worker，不遗留SDK进程继续运行。
        reason='M1_SUPERVISOR_MONITOR_ERROR';monitor_error=type(error).__name__
        if child.poll() is None:child.kill()
    native=child.wait(timeout=5)
    return {'worker_native_exit_code':native,'supervisor_exit_code':2 if monitor_error else 4 if reason else native,'reason':reason,
            'monitor_error_type':monitor_error,
            'Close_completed':'UNKNOWN_PROCESS_KILLED' if reason else 'SEE_WORKER_RECEIPT','target_state':'UNKNOWN','retries':0}


def field_bindings(a):
    """仅在固定PI信任根验签通过后读取本次EFS绑定；不查询C或云端。"""
    def private_file(name):
        path=Path(name).resolve()
        need(path.is_relative_to(PRIVATE.resolve()) and path.is_file() and path.stat().st_file_attributes&0x4000,'M1_PRIVATE_REFERENCE_REQUIRED')
        return path
    bundle_path=private_file(a['bundle_file']);bundle=json.loads(bundle_path.read_text());validate_bundle(bundle)
    for role in ('identity','full','options'):
        file=private_file(bundle[role+'_reference'])
        need(sha(file.read_bytes())==bundle[role+'_reference_sha256'],'M1_REFERENCE_FILE_SHA')
    site_path=private_file(a['site_file']);cold_path=private_file(a['cold_start_file'])
    site=json.loads(site_path.read_text());cold=json.loads(cold_path.read_text());p=plan(a['run_id'])
    required=('B_only_topology_approved','JLink_on_B','nonhuman_source','no_human','B_USB_disconnected',
              'SKX_battery_no_charge_USB','manual_emergency_cutoff_ready')
    need(all(site.get(k) is True for k in required),'M1_SITE_NOT_READY')
    is_ecg=p['condition'].startswith('E')
    need(site.get('source_mode')==('NORMAL_ECG' if is_ecg else 'RESP') and site.get('target_rate')==p['target'],'M1_SOURCE_TARGET')
    need(site.get('L_lead')==('LA' if is_ecg else 'LL') and site.get('R_lead')=='RA' and site.get('F_lead')=='RL','M1_SOURCE_LEADS')
    if is_ecg:need(site.get('ECG_amplitude_mV')==1 and site.get('waveform_type_confirmed') is True,'M1_ECG_MENU')
    else:need(site.get('RESP_amplitude')=='1.5R' and site.get('waveform_period_bpm')==30 and site.get('apnea_s')==0,'M1_RESP_MENU')
    need(cold.get('run_id')==a['run_id'] and cold.get('cold_start_completed') is True
         and bool(cold.get('independent_boot_epoch')) and 0<=time.time()-cold.get('power_on_unix',0)<=120,'M1_INDEPENDENT_COLD_START')
    output=Path(a['output']).resolve()
    need(output.is_relative_to(PRIVATE.resolve()) and output.parent.is_dir() and output.parent.stat().st_file_attributes&0x4000,'M1_OUTPUT_EFS')
    def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode().strip()
    need(not git('status','--porcelain'),'M1_WORKTREE_NOT_FROZEN')
    expected={'scope':SCOPE,'run_id':p['run_id'],'plan_sha256':plan_hash(p['run_id']),
        'repo_commit':git('rev-parse','HEAD'),'repo_tree':git('rev-parse','HEAD^{tree}'),
        'tools_sha256':tool_bindings(),'DLL_sha256':'632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff',
        'bundle_sha256':sha(bundle_path.read_bytes()),'site_sha256':sha(site_path.read_bytes()),
        'cold_start_sha256':sha(cold_path.read_bytes()),'output':str(output),'manual_stop_responsibility':site['manual_stop_responsibility']}
    reference={'identity':json.loads(Path(bundle['identity_reference']).read_text()),'full_sha256':FULL_SHA,
        'BIN_sha256':BIN_SHA,'options_sha256':OPTIONS_SHA,'maximum_cold_start_uptime_ms':120000,
        'cold_start_sha256':expected['cold_start_sha256']}
    return expected,reference


def field_command(args):
    # P0固定根未配置时先拒止，既不读取自填授权，也不构造/加载SDK。
    if TRUSTED_PI_KEY_SHA256 is None:
        print(json.dumps({'status':'M1_P0_FIELD_DISABLED','exit_code':2,'trust_root':'NOT_CONFIGURED'}));return 2
    try:
        need(args.authorization and args.signature and args.public_key,'M1_SIGNED_FILES_REQUIRED')
        raw=args.authorization.read_bytes();sig=args.signature.read_bytes();public=args.public_key.read_bytes()
        need(sha(public)==TRUSTED_PI_KEY_SHA256,'M1_UNTRUSTED_PI_KEY')
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(public).verify(sig,raw)
        a=json.loads(raw);expected,reference=field_bindings(a)
        verify_signed_card(raw,sig,public,TRUSTED_PI_KEY_SHA256,expected,time.time())
        ledger=PRIVATE/'m1-used-nonces';ledger.mkdir(exist_ok=True)
        need(ledger.stat().st_file_attributes&0x4000,'M1_NONCE_LEDGER_EFS')
        name=sha((SCOPE+'\0'+a['nonce']).encode());marker=ledger/(name+'.used');out=Path(expected['output'])
        if args.worker:
            need(json.loads(marker.read_text())=={'scope':SCOPE,'run_id':a['run_id'],'authorization_sha256':sha(raw)},'M1_PARENT_MARKER')
            save(ledger/(name+'.worker-used'),{'authorization_sha256':sha(raw),'run_id':a['run_id']})
            result=capture_window(native_link,out,reference)
            seal_capture(out,raw,sig,public,expected)
            return result['exit_code']
        need(not out.exists(),'M1_OUTPUT_EXISTS');consume_nonce(ledger,raw,a)
        command=[sys.executable,'-X','utf8',str(Path(__file__)),'--worker','--authorization',str(args.authorization),
                 '--signature',str(args.signature),'--public-key',str(args.public_key)]
        with out.with_name(out.name+'-worker.log').open('xb') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            result=watch_worker(child,out)
        out.mkdir(exist_ok=True);save(out/'supervisor-private.json',result)
        print(json.dumps(result));return result['supervisor_exit_code']
    except Exception as error:
        print(json.dumps({'status':'M1_ENTRY_REJECT_OR_TOOL_ERROR','exit_code':2,'type':type(error).__name__}));return 2


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-id',default='M1-E60-R1')
    p.add_argument('--plan',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--authorization',type=Path);p.add_argument('--worker',action='store_true')
    p.add_argument('--signature',type=Path);p.add_argument('--public-key',type=Path)
    a=p.parse_args()
    if a.execute or a.worker:
        return field_command(a)
    print(json.dumps(plan(a.run_id)));return 0


if __name__=='__main__':raise SystemExit(main())
