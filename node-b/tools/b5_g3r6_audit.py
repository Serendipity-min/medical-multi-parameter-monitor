"""仅离线复核既有R5原件；返回不含设备身份/网络端点的统计。"""
import hashlib
import json
import importlib.util
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def window(folder):
    rows=[json.loads(line) for line in (folder/'io-private.jsonl').read_text('utf8').splitlines()]
    native=[row for row in rows if 'operation' in row]
    uart=[];select=tar=None
    for row in native:
        if row['operation']!='JLINKARM_CORESIGHT_WriteAPDPReg':continue
        reg,ap,value=row['reg'],row['AP'],row['value']
        if ap==0 and reg==2:select=value
        elif ap==1 and select==0 and reg==1:tar=value
        elif ap==1 and select==0 and reg==3 and tar==0x40004804:uart.append(value)
    wire=bytes(uart);parts=wire.split(b'\r\n')
    receipt=json.loads((folder/'receipt-private.json').read_text('utf8'))
    events=[json.loads(line) for line in (folder/'heartbeat-events.jsonl').read_text('utf8').splitlines()]
    return {'recorded_native_calls':len(native),'negative_native_returns':sum(
        isinstance(r.get('native_return_int'),int) and r['native_return_int']<0 for r in native),
        'short_ReadMemEx':sum(r['operation']=='JLINKARM_ReadMemEx' and r.get('native_return_int')!=r['requested'] for r in native),
        'UART_bytes':len(wire),'CRLF_complete_commands':len(parts)-1,'unterminated_tail_bytes':len(parts[-1]),
        'wire_sha256':hashlib.sha256(wire).hexdigest(),
        'host_ExecCommand_sequence':[r['policy'] for r in rows if 'policy' in r],
        'explicit_control_API_calls':sum(r['operation'] in ('JLINKARM_Go','JLINKARM_Reset','JLINKARM_Halt') for r in native),
        'Close_active_events':sum(r.get('operation')=='JLINKARM_Close' and r.get('active') is True for r in events),
        'Close_inactive_events':sum(r.get('operation')=='JLINKARM_Close' and r.get('active') is False for r in events),
        'receipt':{k:receipt.get(k) for k in ('exit_code','reason','SDK_calls','close_resume',
            'SNTP_enable_attempts','SNTP_disable_attempts','SNTP_stop_verified')},
        'sources_sha256':{name:digest(folder/name) for name in ('io-private.jsonl','heartbeat-events.jsonl','receipt-private.json')}}


def audit(first,later):
    a,b=window(first),window(later)
    entry=json.loads((later/'entry-private.json').read_text('utf8'))
    return {'first':a,'later':b,'later_state':{k:entry[k] for k in ('DHCSR','VTOR','CFSR','HFSR','DWT_PCSR')},
        'real_PC_MSP_available':False,'unique_HALT_cause':'UNRESOLVED',
        'new_target_sessions':0,'new_target_writes':0}


def budget_replay(source):
    spec=importlib.util.spec_from_file_location('budget_replay_only',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    link=object.__new__(module.QueryLink)
    link.sdk_calls=6000;link.sdk_limit=6000;link.verified_running_flash=True
    try:link.read(module.UART,4)
    except ValueError as error:
        return {'exception_class':type(error).__name__,'reason':str(error),
            'read_failed':getattr(link,'read_failed',False),'verified_running_flash':link.verified_running_flash,
            'new_native_calls':link.sdk_calls-6000}
    raise AssertionError('EXPECTED_BUDGET_REFUSAL')
