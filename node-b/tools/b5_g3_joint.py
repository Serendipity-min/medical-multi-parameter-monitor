"""G3联合记录与独立监督；默认计划，本轮不得启用B5START。"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import b5_g3_contract as g


class SerialGate:
    def __init__(self):self.banner=0;self.steps=set();self.diags=[];self.stopped=False;self.sntp_metadata=None;self.network_session=None;self.precommon_ntp_failures=[]
    def consume(self,line,armed=False,ntp_failures_max=0):
        if line=='B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE':
            g.require(not armed,'G3_C_UNEXPECTED_REBOOT');self.banner+=1;g.require(self.banner==1,'G3_C_MULTIPLE_BOOTS')
        if line.startswith('GW FAIL '):
            # 仅新授权允许观察候选已有的授时端点轮换；不发送重试，原60秒就绪门不变。
            if (line=='GW FAIL SNTP_FRESH_SAMPLE' and armed and not self.startup_ready()
                    and len(self.precommon_ntp_failures)<ntp_failures_max):self.precommon_ntp_failures.append(line)
            else:raise ValueError('G3_C_NETWORK_STEP_FAILED')
        if line.startswith('GW AT_VERSION value='):
            g.require(re.fullmatch(r'[0-9.]{3,32}',line.split('=',1)[1]) is not None,'G3_AT_VERSION_FORMAT')
            self.steps.add('AT_VERSION')
        if line.startswith('GW SNTP_SAMPLE '):
            values={k:int(v) for k,v in (x.split('=') for x in line[15:].split())}
            g.require(set(values)=={'rtt_ms','uncertainty_ms','epoch','fraction','server_index'}
                      and 0<=values['rtt_ms']<=1000 and 0<=values['uncertainty_ms']<=500
                      and values['epoch']>=1577836800 and 0<=values['fraction']<1000
                      and 0<=values['server_index']<=2,'G3_SNTP_METADATA')
            self.sntp_metadata=values
        for text,key in [('GW SNTP_SAMPLE ','SNTP_SAMPLE'),('GW SNTP_VALID ','SNTP_VALID'),
                         ('GW OK CA_VERIFY','CA'),('GW OK CERT_NAME','CERT'),('GW OK SNI','SNI'),
                         ('GW OK TLS','TLS'),('GW MQTT_CONNECTED','MQTT')]:
            if (line.startswith(text) if text.endswith(' ') else line==text):self.steps.add(key)
        if line=='B5 STOPPED NO_AUTOREARM':
            g.require(armed,'G3_C_ALREADY_STOPPED');self.stopped=True
        diag=g.parse_diag(line)
        if diag:
            g.require(armed,'G3_C_ALREADY_ARMED_BEFORE_START')
            g.require(not any(diag[k] for k in ('txfail','overflow','uart_err','mqtt_fail')),'G3_C_TRANSPORT_COUNTER')
            g.require(not (diag['esr']&7) and not (diag['esr']>>16),'G3_C_TEC_REC_BOFF')
            if self.diags:g.require(diag['tick']>=self.diags[-1]['tick'],'G3_C_UPTIME_RESTART')
            if diag['session']:
                if self.network_session is not None:g.require(diag['session']==self.network_session,'G3_C_SESSION_CHANGED')
                self.network_session=diag['session']
            self.diags.append(diag)
        return diag
    def startup_ready(self):return self.steps=={'AT_VERSION','SNTP_SAMPLE','SNTP_VALID','CA','CERT','SNI','TLS','MQTT'}


def start_once(serial_port,root,a,now=None,utc_ms=None):
    g.require(a.get('B5START_allowed') is True and a.get('owner_approved') is True,'G3_START_NOT_ALLOWED')
    g.require(all((root/n).exists() for n in ('B_READY.json','NET_READY.json','C_BANNER_READY.json','ARM_BACKEND_BASELINE.json','C_RESET_OWNER_DONE.json','RESET_REQUESTED.json')),
              'G3_START_PREREQUISITES')
    at=time.monotonic() if now is None else now;banner=g.maybe(root/'C_BANNER_READY.json')
    g.require(banner is not None and 0<=at-banner['monotonic']<=g.CRITERIA['manual_reset_ack_max_s'],'G3_C_RESET_ACK_TOO_LATE_NO_START')
    attempt={'monotonic':at,'UTC_ms':int(time.time()*1000) if utc_ms is None else utc_ms,
             'bytes':8,'command_sha256':g.sha(b'B5START\n'),'authorization_scope':a.get('scope',g.G3),
             'actual_MCU_acceptance':'NOT_ESTABLISHED_BY_SERIAL_WRITE_RETURN'}
    g.save(root/'ARM_ATTEMPT.json',attempt)
    g.require(serial_port.write(b'B5START\n')==8,'G3_START_SHORT_WRITE_NO_RETRY')
    return attempt


def confirm_serial_reset(root,a,now):
    if a.get('reset_confirmation')!='SERIAL_DISARMED_AFTER_INTENT':return
    request=g.maybe(root/'RESET_REQUESTED.json')
    g.require(a.get('owner_manual_reset_preapproved') is True and request is not None
              and 0<=now-request['monotonic']<=g.prearm_seconds(a),'G3_RESET_WITHOUT_APPROVED_INTENT')
    # 仅新卡允许以随后串口启动行确认动作；不等待模型/聊天往返，不证明复位电气根因。
    g.save(root/'C_RESET_OWNER_DONE.json',{'monotonic':now,'count':1,
        'completion_basis':'PREAPPROVED_OWNER_ACTION_AND_NEW_SERIAL_DISARMED',
        'physical_reset_cause_proven':False,'owner_chat_ack_required':False})


def last_event(path):
    try:
        with Path(path).open('rb') as f:
            f.seek(0,2);size=f.tell();f.seek(max(0,size-4096));lines=f.read().splitlines()
        return json.loads(lines[-1]) if lines else {}
    except (OSError,ValueError):return {}


def record_lines(pending,stream,root,armed,stop_at):
    parts=pending.split(b'\n');texts=[x.rstrip(b'\r').decode('ascii') for x in parts[:-1]]
    # 同一读取中先完整留存各行和STOP，再裁定计数；故障仍失败，不丢后续真实停止证据。
    for text in texts:
        g.append(stream,'C_LINE',text)
        if armed and text=='B5 STOPPED NO_AUTOREARM' and stop_at is None:
            stop_at=time.monotonic();g.save(root/'C_STOP_BANNER.json',{'monotonic':stop_at})
    # 先保存同块所有原行，之后才解析可选的新源端STOP记录；解析错误不吞后续原件。
    for text in texts:
        if armed and text.startswith('B5 STOP_STATE '):
            source=g.parse_stop_state(text)
            g.save(root/'C_STOP_SOURCE_STATE.json',{'monotonic':time.monotonic(),'source':source,'raw_line_sha256':g.sha(text.encode())})
    return parts[-1],texts,stop_at


def phase_limits(arm,t0=None):
    limit=arm+g.CRITERIA['arm_hard_s']
    if t0 is not None:g.require(arm<=t0<=arm+60 and t0+360<=limit,'G3_READY_OUTSIDE_FROZEN_BUDGET')
    return {'hard':limit,'passive_end':limit+20,'cleanup_end':limit+25,
            'evaluation':None if t0 is None else [t0+45,t0+345],'tail_end':None if t0 is None else t0+360}


def joint_worker(auth_path,a,bundle):
    import serial
    import b5_g3_cloud as cloud
    root=Path(a['output']);root.mkdir(exist_ok=False);g.private.protected(root,False)
    started=time.monotonic();port=None;b_child=None;cloud_thread=None;stop=threading.Event();shared={}
    gate=SerialGate();arm=None;t0=None;C_stop_at=None;pending=b''
    receipt={'status':'STOP','exit_code':1,'B5START_attempts':0,'automatic_retry_or_rollback':False,
             'explicit_target_halt_go_reset_writes':0,'manual_preplanned_C_RESET':'OWNER_ACTION_ONLY'}
    rawfile=(root/'C-serial-raw-private.bin').open('xb');lines=(root/'C-lines-private.jsonl').open('x',encoding='utf8')
    heartbeat=(root/'joint-heartbeat.jsonl').open('x',encoding='utf8')
    serial_events=(root/'serial-API-events.jsonl').open('x',encoding='utf8')
    def serial_call(name,fn):
        serial_events.write(json.dumps({'operation':name,'active':True,'deadline_monotonic':time.monotonic()+3})+'\n');serial_events.flush()
        try:return fn()
        finally:
            serial_events.write(json.dumps({'operation':name,'active':False})+'\n');serial_events.flush()
    try:
        port=serial.Serial(port=None,baudrate=115200,bytesize=8,parity='N',stopbits=1,
          timeout=.05,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False)
        port.dtr=False;port.rts=False;port.port=a['COM'];serial_call('SERIAL_OPEN',port.open)
        g.save(root/'SERIAL_READY.json',{'monotonic':time.monotonic(),'DTR_requested':False,'RTS_requested':False,
                 'physical_pulse_absence':'NOT_PROVEN_BY_SOFTWARE_FLAGS'})
        print(json.dumps({'event':'SERIAL_OPEN_NO_ACTION_YET','B5START':0}),flush=True)
        b_log=(root/'B-worker-private.log').open('xb')
        b_child=subprocess.Popen([sys.executable,'-X','utf8',str(g.ROOT/'node-b/tools/b5_g3_devices.py'),
          '--b-worker','--authorization',str(auth_path)],stdout=b_log,stderr=subprocess.STDOUT)
        cloud_thread=threading.Thread(target=cloud.run,args=(a,root,bundle,stop,shared),daemon=True);cloud_thread.start()
        pending=b'';ended_B=False
        while True:
            now=time.monotonic();g.append(heartbeat,'JOINT_ALIVE',{'armed':arm is not None})
            g.require(not (root/'STOP').exists(),'G3_OWNER_STOP')
            g.require(not any((root/n).exists() for n in ('B_FAULT.json','CLOUD_FAULT.json')),'G3_CHILD_FAILURE')
            g.require(b_child.poll() is None or ended_B and b_child.returncode==0,'G3_B_WORKER_EXITED')
            chunk=serial_call('SERIAL_READ',lambda:port.read(512))
            if chunk:
                rawfile.write(chunk);rawfile.flush();pending+=chunk
                g.require(len(pending)<=4096,'G3_SERIAL_LINE_OVERFLOW')
                pending,texts,C_stop_at=record_lines(pending,lines,root,arm is not None,C_stop_at)
                for text in texts:
                    diag=gate.consume(text,arm is not None,a.get('precommon_ntp_retries_max',0))
                    if text=='B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE':
                        observed=time.monotonic()
                        g.save(root/'C_BANNER_READY.json',{'monotonic':observed,'line':text,'owner_preplanned_reset_count':1})
                        confirm_serial_reset(root,a,observed)
            if arm is None:
                g.require(now-started<=g.prearm_seconds(a),'G3_PREARM_TIMEOUT_NO_START')
                if all((root/n).exists() for n in ('B_READY.json','NET_READY.json')) and not (root/'RESET_REQUESTED.json').exists():
                    g.save(root/'RESET_REQUESTED.json',{'monotonic':time.monotonic(),'preplanned_C_manual_RESET_max':1})
                if all((root/n).exists() for n in ('B_READY.json','NET_READY.json','C_BANNER_READY.json','C_RESET_OWNER_DONE.json')):
                    if not (root/'ARM_PREPARE.json').exists():g.save(root/'ARM_PREPARE.json',{'monotonic':time.monotonic()})
                    if (root/'ARM_BACKEND_BASELINE.json').exists():
                        arm=serial_call('SERIAL_SINGLE_B5START',lambda:start_once(port,root,a));receipt['B5START_attempts']=1
                        print(json.dumps({'event':'G3_SINGLE_START_SENT','arm_hard_s':420}),flush=True)
            else:
                common=g.maybe(root/'CLOUD_COMMON.json')
                if t0 is None and common and gate.startup_ready():
                    g.require(abs(int(time.time()*1000)-common['server_time'])<=1500,'G3_HOST_SERVER_T0_CLOCK_SKEW')
                    t0=time.monotonic();limits=phase_limits(arm['monotonic'],t0)
                    g.save(root/'T0.json',{'monotonic':t0,'UTC_ms':common['server_time'],
                       'UTC_basis':'Fresh actual Backend WSS server_time; no equality of B/C uptimes assumed',
                       'gateway_session':common['gateway_session'],'B_session':common['B_session'],
                       'evaluation_UTC_ms':[common['server_time']+45000,common['server_time']+345000],**limits})
                limits=phase_limits(arm['monotonic'],t0)
                if t0 is None:g.require(now<=arm['monotonic']+60,'G3_COMMON_NOT_READY_IN_60S')
                if gate.stopped:
                    g.require(t0 is not None and now>=t0+345,'G3_C_STOPPED_BEFORE_EVALUATION_END')
                    g.require(now>=limits['hard']-1,'G3_C_STOPPED_EARLY')
                if gate.diags and gate.diags[-1]['stop']:
                    g.require(now>=limits['hard']-1,'G3_C_STOPPED_EARLY')
                if now>=limits['hard'] and not ended_B:
                    g.save(root/'END_B',{'at':now,'MCU_business_stop':'REQUIRES_C_STOP_EVIDENCE'});ended_B=True
                if now>=limits['hard']+2:g.require(C_stop_at is not None and C_stop_at<=limits['hard']+2,'G3_MCU_STOP_NOT_CONFIRMED_MANUAL_ISOLATE')
                if t0 is not None and t0+45<=now<t0+345:
                    g.require(shared.get('cloud_last_monotonic',0)>=now-2,'G3_WSS_GAP')
                if now>=limits['passive_end']:break
        g.require(t0 is not None and C_stop_at is not None and gate.stopped,'G3_INCOMPLETE_WINDOW')
        if bundle.get('_require_source_STOP_state'):
            proof=g.load(root/'C_STOP_SOURCE_STATE.json')['source']
            g.require(proof['business_elapsed_ms']==420000 and proof['reason']==1
                      and proof['phase']==7 and not proof['unsynced'] and not proof['pending'],
                      'G3_STOP_SOURCE_OR_UNSAFE_NETWORK_END')
        receipt.update(status='G3_FILES_CAPTURED_REVIEW_PENDING',exit_code=0,Tarm=arm['monotonic'],T0=t0,
                       source_STOP_required=bool(bundle.get('_require_source_STOP_state')),
                       C_STOP_banner_monotonic=C_stop_at,serial_startup_steps=sorted(gate.steps),
                       physiological_and_transport_PASS='NOT_GRANTED_UNTIL_OFFLINE_JOINT_REVIEW')
    except BaseException as e:
        receipt.update(g.error_record(e))
        reason=str(e)
        receipt['reason']=reason if reason.startswith('G3_') and reason.replace('_','').isalnum() else 'PRIVATE_ERROR_SUPPRESSED'
        if not (root/'STOP').exists():g.save(root/'STOP',{'reason':receipt['reason']})
        if (root/'ARM_ATTEMPT.json').exists():
            receipt['B5START_attempts']=1;receipt['physical_stop']='NOT_CONFIRMED_REQUIRE_MANUAL_ALL_BOARD_POWER_REMOVAL'
            receipt['manual_isolation_required']=['B_J5_OFF','C_J5_OFF','C_USB_UNPLUG','JLink_PC_USB_UNPLUG']
            print(json.dumps({'event':'MANUAL_BC_J5_C_USB_JLINK_USB_POWER_OFF_REQUIRED','reason':receipt['reason']}),flush=True)
            # 只读尾段不发AT/START；目标失败后仍保留随后到达的STOP和云端末批原件。
            end=min(time.monotonic()+5,arm['monotonic']+440) if arm else time.monotonic()
            receipt['failure_passive_tail_started']=time.monotonic()
            try:
                while port and port.is_open and time.monotonic()<end:
                    port.timeout=min(.05,max(0,end-time.monotonic()))
                    chunk=serial_call('SERIAL_READ_PASSIVE_TAIL',lambda:port.read(512))
                    if not chunk:continue
                    rawfile.write(chunk);rawfile.flush();pending+=chunk
                    pending,_,C_stop_at=record_lines(pending,lines,root,True,C_stop_at)
            except Exception as error:
                receipt['passive_tail_error']=g.error_record(error)
            receipt['failure_passive_tail_ended']=time.monotonic()
    finally:
        receipt['precommon_ntp_failures']=gate.precommon_ntp_failures
        stop.set()
        if b_child:
            try:b_child.wait(timeout=15 if a.get('host_cancel_cleanup_s',0) else 5)
            except subprocess.TimeoutExpired:b_child.kill();b_child.wait(timeout=5);receipt['B_target_state']='UNKNOWN_NO_RECONNECT'
            receipt['B_worker_exit_code']=b_child.returncode;b_log.close()
            if b_child.returncode:receipt['exit_code']=1
        if cloud_thread:
            cloud_thread.join(timeout=5)
            if cloud_thread.is_alive():receipt.update(exit_code=1,cloud_thread_state='UNKNOWN_SUPERVISOR_MUST_END_PROCESS')
        if port:port.close()
        if pending:receipt['serial_unterminated_tail_bytes']=len(pending)
        rawfile.close();lines.close();heartbeat.close();serial_events.close()
        cloud_receipt=g.maybe(root/'cloud-receipt-private.json')
        if not cloud_receipt or cloud_receipt.get('exit_code')!=0:receipt['exit_code']=1
        g.save(root/'joint-receipt-private.json',receipt)
    print(json.dumps({'status':receipt['status'],'exit_code':receipt['exit_code']}),flush=True)
    return receipt['exit_code']


def supervise(auth_path,c_check=False):
    a=g.load(auth_path);bundle,site=g.validate(a,g.HW if c_check else g.G3)
    output=Path(a['output']);g.require(not output.exists(),'G3_OUTPUT_EXISTS')
    marker={'scope':a['scope'],'started_monotonic':time.monotonic(),'authorization_sha256':g.sha(auth_path.read_bytes())}
    g.save(auth_path.with_suffix('.used'),marker)
    log=output.with_name(output.name+'-supervisor-worker-private.log');g.write_private(log,b'')
    flag='--c-worker' if c_check else '--joint-worker'
    command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),flag,'--authorization',str(auth_path)]
    with log.open('ab') as f:
        child=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT)
        reason=None;serial_notice=False;hard_notice=False
        while child.poll() is None:
            now=time.monotonic();arm=g.maybe(output/'ARM_ATTEMPT.json')
            prearm_limit=g.prearm_seconds(a)+(30 if a.get('host_cancel_cleanup_s',0) else 0)
            end=marker['started_monotonic']+90 if c_check else (arm['monotonic']+445 if arm else marker['started_monotonic']+prearm_limit)
            if now>end:reason='SUPERVISOR_DEADLINE'
            if (output/'STOP-SUPERVISOR').exists():reason='OWNER_STOP'
            if not c_check:
                if (output/'RESET_REQUESTED.json').exists() and not serial_notice:
                    print(json.dumps({'event':'SERIAL_READY_PRESS_C_RESET_ONCE_AS_PREAPPROVED','B5START':0}),flush=True);serial_notice=True
                for file,label in [('B/heartbeat-events.jsonl','B_NATIVE_DEADLINE'),('serial-API-events.jsonl','SERIAL_NATIVE_DEADLINE')]:
                    last=last_event(output/file)
                    if last.get('active') and now>last['deadline_monotonic']:reason=label
                if arm:
                    if now>=arm['monotonic']+420 and not hard_notice:
                        print(json.dumps({'event':'MCU_420S_BUSINESS_DEADLINE_VERIFY_STOP'}),flush=True);hard_notice=True
                    if now>arm['monotonic']+60 and not (output/'T0.json').exists():reason='COMMON_READY_DEADLINE'
                    stop_proof=g.maybe(output/'C_STOP_BANNER.json')
                    if now>arm['monotonic']+422 and (not stop_proof or stop_proof['monotonic']>arm['monotonic']+422):
                        reason='MCU_STOP_NOT_CONFIRMED_MANUAL_ISOLATE'
            if reason:
                # 只结束本次创建的进程树；这不是MCU停机，仍须人工切C供电和USB。
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=8)
                break
            time.sleep(.05)
        child.wait(timeout=5)
    result={'supervisor_reason':reason,'worker_exit_code':child.returncode,
      'supervisor_exit_code':0 if reason is None and child.returncode==0 else 1,'automatic_retry_or_recovery':False,
      'process_tree_killed_is_not_MCU_stop':True,'G3_B5START_attempted':(output/'ARM_ATTEMPT.json').exists()}
    output.mkdir(exist_ok=True);g.save(output/'supervisor-private.json',result)
    if result['supervisor_exit_code'] and result['G3_B5START_attempted']:
        print(json.dumps({'event':'MANUAL_BC_J5_C_USB_JLINK_USB_POWER_OFF_REQUIRED','reason':'G3_SUPERVISOR_FAILED'}),flush=True)
    print(json.dumps(result));return result['supervisor_exit_code']


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--c-check',action='store_true')
    p.add_argument('--joint-worker',action='store_true');p.add_argument('--c-worker',action='store_true')
    p.add_argument('--ack-c-reset',action='store_true')
    p.add_argument('--authorization',type=Path);args=p.parse_args()
    if not any((args.execute,args.c_check,args.joint_worker,args.c_worker,args.ack_c_reset)):
        print(json.dumps({'enabled':False,'owner_approved':False,'criteria':g.CRITERIA,'B5START':0,'tools_sha256':g.bindings()}));return 0
    try:
        g.require(args.authorization is not None,'G3_AUTH_REQUIRED')
        if args.ack_c_reset:
            a=g.load(args.authorization);g.validate(a,g.G3);root=Path(a['output'])
            g.require(args.authorization.with_suffix('.used').exists() and (root/'SERIAL_READY.json').exists()
                      and (root/'RESET_REQUESTED.json').exists() and not (root/'ARM_ATTEMPT.json').exists(),'G3_RESET_ACK_PHASE')
            g.save(root/'C_RESET_OWNER_DONE.json',{'monotonic':time.monotonic(),'count':1,'basis':'Owner reported exactly one preplanned C RESET; no target command sent'})
            return 0
        if args.joint_worker or args.c_worker:
            a=g.load(args.authorization);bundle,site=g.validate(a,g.HW if args.c_worker else g.G3)
            g.require(args.authorization.with_suffix('.used').exists(),'G3_PARENT_MARKER_REQUIRED')
            if args.c_worker:
                import b5_g3_devices as dev
                root=Path(a['output']);root.mkdir(exist_ok=False);g.private.protected(root,False)
                return dev.c_preflight(a,root,bundle)
            return joint_worker(args.authorization,a,bundle)
        return supervise(args.authorization,args.c_check)
    except BaseException as e:
        print(json.dumps({'status':'STOP','exit_code':1,'error_type':type(e).__name__}));return 1

if __name__=='__main__':raise SystemExit(main())
