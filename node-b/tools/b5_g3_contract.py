"""G3共享边界与证据解析；默认无设备、串口或网络连接。"""
import hashlib
import base64
import importlib.metadata
import json
import re
from pathlib import Path
import struct
import time
import sys
from collections import Counter
from decimal import Decimal

import b4_recovery as private
from b5_g0_readonly import write_private

ROOT=Path(__file__).resolve().parents[2]
G3='B5_G3_ONE_ECG60_MOCK_CLOUD_WINDOW'
HW='B5_G3_PREP_C_READONLY_AND_COLD_TRANSFER'
CRITERIA={'prearm_s':120,'readiness_s':60,'warmup_s':45,'evaluation_s':300,'tail_s':15,
          'arm_hard_s':420,'passive_after_hard_s':20,'cleanup_s':5,'HR_range':[58,62],
          'HR_valid_fraction':1.0,'RR':'INVALID','TEMP':'INVALID','A':'OFFLINE',
          'source':'MOCK','synthetic':True,'ECG_batch':100,'ECG_rate':250,'RESP_batch':50,'RESP_rate':50}
CRITERIA.update(ECG_min_points=74250,RESP_min_points=14850,B_min_saved=590,WSS_min_saved=2900,
                scalar_min_messages=295,nominal_grid_phase_max_ms=2,host_server_T0_max_skew_ms=1500)
CRITERIA['manual_reset_ack_max_s']=30
B_IMAGE='676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82'
C_IMAGE='d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683'
C_FULL='acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e'
B_ELF='94e1ed1d188acae350943382645ce49edc1ed91bb043245657de3df1f1f89249'
B_SYMBOLS='b6810d245bc7f76b8ed620de5e28d936e2aa36c2df34034a58c7bf7431c91ca2'
SLOTS=0x20002160; BLOCK_BYTES=5692
QUEUE=0x20002d60; CLOCK=0x20003760
SOURCE={'mode':'NORMAL_ECG','HR_bpm':60,'amplitude_menu_mV':1.0,
        'leads':{'R':'RA','L':'LA','F':'RL/N','LL':'EMPTY'},'battery_no_USB':True,'no_human':True}
require=private.require
sha=lambda b:hashlib.sha256(b).hexdigest()


def bindings():
    names=('b5_g3_contract.py','b5_g3_devices.py','b5_g3_cloud.py','b5_g3_joint.py','b5_g3_review.py',
           'b4_runtime.py','b4_ecg_rala_can_current.py','c_b4_readonly.py','c_b4_closeout_readonly.py',
           'readback_b.py','runtime_state_b.py','live_state_b.py','resp_exploratory.py',
           'b4_recovery.py','b5_g0_readonly.py','b5_g1_smoke.py','b5_g2_site.py','b5_gen5_plan.py','b5_gen5_writer.py',
           'b5_sector3_write.py','b5_sector3_write_protocol.py','b5_g2ro.py',
           'b4_swd_install.py','b5_sector3_write_supervisor.py','b5_sector3_plan.py','b5_g1_cloud.py')
    return {n:sha((ROOT/'node-b/tools'/n).read_bytes()) for n in names}


def environment():
    return {'python':sys.version.split()[0],
            'packages':{n:importlib.metadata.version(n) for n in ('pyserial','paho-mqtt','websockets','pydantic','numpy')},
            'Backend_sources':{n:sha((ROOT/'cloud/backend/app'/n).read_bytes()) for n in ('adapters.py','models.py','hub.py')}}


def save(path,data):write_private(Path(path),(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())

def load(path):return json.loads(private.read(Path(path),False))

def maybe(path):
    try:return json.loads(Path(path).read_text('utf8'))
    except (OSError,ValueError):return None


def append(stream,kind,data):
    stream.write(json.dumps({'monotonic':time.monotonic(),'UTC_ms':int(time.time()*1000),
                             'kind':kind,'data':data},ensure_ascii=False)+'\n');stream.flush()


def error_record(error):
    text=str(error)
    safe=(text.startswith(('G3_','B4_','C_RO_','SDK_')) and text.isascii()
          and text.replace('_','').isalnum() and text.isupper())
    return {'error_type':type(error).__name__,'reason':text if safe else 'PRIVATE_ERROR_SUPPRESSED',
            'error_text_sha256':sha(text.encode()),
            'errno':getattr(error,'errno',None),'TLS_verify_code':getattr(error,'verify_code',None)}


def expected_c_full(a,bundle):
    if 'gen5_package' not in a:
        require(a.get('configuration_generation',4)==4,'G3_GEN5_PACKAGE_REQUIRED')
        return C_FULL
    import b5_gen5_writer as gen5
    require(a.get('configuration_generation')==5,'G3_GEN5_GENERATION')
    _,files=gen5.load_package(a['gen5_package'],a['gen5_package_manifest_sha256'])
    expected=sha(files['gen5-full-private.bin'])
    raw=private.read(Path(a['gen5_install_receipt']),False);receipt=json.loads(raw)
    require(sha(raw)==a['gen5_install_receipt_sha256'] and receipt.get('exit_code')==0
        and receipt.get('status')=='SECTOR3_FULL_VERIFY_AND_DISARMED_BOOT_PASS'
        and receipt.get('scope')=='B5_GEN5_WIFI_WRITE' and receipt.get('configuration_generation')==5
        and receipt.get('Close_completed') is True
        and receipt.get('after_full_sha256')==expected
        and receipt.get('package_manifest_sha256')==a['gen5_package_manifest_sha256'],'G3_GEN5_INSTALL_NOT_PASS')
    require(bundle['C_full']['sha256']==expected,'G3_GEN5_FULL_REFERENCE')
    return expected


def validate(a,scope):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==scope,'G3_OWNER_SCOPE')
    require(a.get('tools_sha256')==bindings() and a.get('criteria')==CRITERIA,'G3_FROZEN_BINDINGS')
    require(a.get('precommon_ntp_retries_max',0) in (0,2),'G3_PRECOMMON_NTP_RETRY_SCOPE')
    require(a.get('environment')==environment(),'G3_ENVIRONMENT_DRIFT')
    require(time.time()<a.get('expires_unix',0) and a.get('retries')==0,'G3_EXPIRED_OR_RETRY')
    card='B5-GEN5-AND-G3-OBJECT-AUTHORIZATION-DRAFT.md' if 'gen5_package' in a else ('AUTH-B5-G3-CLOUD-WINDOW-001-R4.md' if scope==G3 else 'AUTH-B5-G3-HW-PREP-001-R1.md')
    require(a.get('card_sha256')==sha((ROOT/'node-b/docs'/card).read_bytes()),'G3_CARD_DRIFT')
    require(a.get('DLL_sha256')=='632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff','G3_DLL_IDENTITY')
    bundle_raw=private.read(Path(a['bundle']),False)
    require(sha(bundle_raw)==a.get('bundle_sha256'),'G3_BUNDLE_DRIFT')
    bundle=json.loads(bundle_raw)
    for key in ('B_identity','B_full','B_options','C_identity','C_full','C_options','B_ELF','B_symbols','cloud_package','cloud_credentials'):
        b=private.read(Path(bundle[key]['path']),False)
        require(sha(b)==bundle[key]['sha256'],'G3_PRIVATE_REFERENCE_DRIFT')
    expected_full=expected_c_full(a,bundle)
    require(bundle['B_ELF']['sha256']==B_ELF and bundle['B_symbols']['sha256']==B_SYMBOLS
            and bundle['C_full']['sha256']==expected_full
            and bundle['cloud_package']['sha256']=='dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0','G3_ELF_FULL_BINDING')
    P=load(bundle['cloud_package']['path'])
    require(all(sha(base64.b64decode(P['sources']['backend/app/'+n]))==v
                for n,v in environment()['Backend_sources'].items()),'G3_REAL_BACKEND_COMPATIBILITY_DRIFT')
    site_raw=private.read(Path(a['site_record']),False)
    require(sha(site_raw)==a.get('site_record_sha256'),'G3_SITE_DRIFT')
    site=json.loads(site_raw)
    if scope==G3:
        require(a.get('B5START_allowed') is True and a.get('start_max')==1,'G3_ARM_NOT_APPROVED')
        require(a.get('test_service_expiry_unix',0)>time.time()+625,'G3_TEST_SERVICE_RESIDENCY_TOO_SHORT')
        require(site.get('source')==SOURCE and site.get('COM_confirmed') is True
                and site.get('JLink_target')=='B' and site.get('C_USB_port')==a.get('COM')
                and site.get('C_USB_connector')=='USB_UART/USB232'
                and re.fullmatch(r'COM[1-9][0-9]{0,4}',a.get('COM','')) is not None,'G3_SOURCE_ROUTE')
        require(all(site.get(k) is True for k in ('C_J5','B_J5','CAN_GND_unchanged','A_disconnected',
                    'INMP441_TTS_disconnected','ESP_present_powered_exception','operator_ready_manual_cutoff',
                    'one_C_reset_preplanned_only','cold_transfer_completed','B_USB_disconnected',
                    'all_dark_10s_confirmed','JTAG_direction_verified','exclusive_test_namespace')),'G3_SITE_INCOMPLETE')
        require(a.get('observer_client_id','').startswith('b5-g3-observer-') and len(a['observer_client_id'])<=60,
                'G3_OBSERVER_IDENTITY')
        require(a.get('observer_username')=='b5-observer','G3_NO_PUBLISHER_OBSERVER')
        cproof_raw=private.read(Path(a['C_preflight_receipt']),False)
        require(sha(cproof_raw)==a.get('C_preflight_receipt_sha256'),'G3_C_PREFLIGHT_BINDING')
        cproof=json.loads(cproof_raw)
        require(cproof.get('status')=='C_CURRENT_B5_CONFIG_DISARMED_READONLY_PASS' and cproof.get('exit_code')==0
                and cproof.get('full_sha256')==expected_full,'G3_C_PREFLIGHT_NOT_PASS')
        require(time.time()-cproof['observed_unix']<=3600,'G3_C_PREFLIGHT_TOO_OLD')
    else:
        require(a.get('B5START_allowed') is False and site.get('JLink_target')=='C'
                and site.get('unchanged_power_wiring') is True,'G3_HW_SCOPE_ONLY')
    private.protected(Path(a['output']).parent,False)
    bundle['_expected_C_full_sha256']=expected_full
    return bundle,site


def parse_diag(line):
    if not line.startswith('B5 DIAG '):return None
    out={}
    for item in line[8:].split():
        k,v=item.split('=',1);out[k]=int(v)
    expected={'tick','session','rx','txack','txfail','overflow','esr','uart_err','live','cache','dropped','q0_transport','q1_puback','mqtt_fail','stop'}
    require(set(out)==expected,'G3_DIAG_SCHEMA')
    return out


def assert_snapshot(s):
    require(s.get('gateway_id')=='GW-B5-001' and s.get('nodes',{}).get('NODE-A')=='OFFLINE','G3_WSS_IDENTITY_A')
    for x in s.get('streams',[]):
        require(x.get('source')=='MOCK' and x.get('synthetic') is True,'G3_WSS_SOURCE')
        if x['validity']!='VALID':require(x.get('value') is None and not x.get('samples'),'G3_WSS_INVALID_MASK')
        if x['stream'] in ('RR','TEMP'):require(x['validity'] in ('INVALID','STALE','OFFLINE'),'G3_WSS_RR_TEMP')


def telemetry_key(t):return (t['node_id'],t['stream'],t['session_id'],t['seq'],t['timestamp'])

def fixed(value,scale):
    v=Decimal(str(value))*scale
    require(v.is_finite() and v==v.to_integral_value(),'G3_FIXED_POINT_QUANTIZATION')
    return int(v)


def signed(value,anchor):return ((value-anchor+0x80000000)&0xffffffff)-0x80000000


class Versions:
    """只保留各版本计数与首两处位置；全部原件仍在块文件，不保存百万条对象副本。"""
    def __init__(self):self.rows={};self.positions={};self.last_max=0
    def add(self,key,blob,position):
        self.rows.setdefault(key,Counter())[blob]+=1
        self.positions.setdefault((key,blob),[])
        if len(self.positions[key,blob])<2:self.positions[key,blob].append(position)
    def stable(self):
        good={};bad=[]
        for key,counter in self.rows.items():
            repeated=[b for b,n in counter.items() if n>=2]
            if len(repeated)==1:good[key]=repeated[0]
            else:bad.append(key)
        return good,bad


def decode_block(blob):
    require(len(blob)==BLOCK_BYTES,'G3_BLOCK_LENGTH')
    raw=[];can=[]
    for n in range(128):
        b=blob[n*24:n*24+24];status=int.from_bytes(b[:3],'big');seq=struct.unpack_from('<I',b,12)[0]
        if seq and status&0xf01fff==0xc00000:raw.append((seq,b,n*24))
        b=blob[3072+n*20:3072+(n+1)*20];ecg,resp,tick,seq,due,flags=struct.unpack('<iiIIBB2x',b)
        if seq and due in (0,1) and due==int(seq%5==0):can.append((seq,b,3072+n*20))
    return raw,can,struct.unpack_from('<III B 3x',blob,5632)


def can_utc_points(versions,clocks):
    index={}
    for seq,b in versions.items():
        ecg,resp,tick,actual_seq,due,flags=struct.unpack('<iiIIBB2x',b)
        require(seq==actual_seq,'G3_CAN_SEQUENCE')
        if flags:continue
        for epoch,anchor,received,valid in clocks:
            if valid==1 and epoch>=1577836800 and -100<=signed(tick,received)<=30000:
                utc=epoch*1000+signed(tick,anchor)
                for stream,value in [('ECG',ecg)]+([('RESP',resp)] if due else []):
                    index.setdefault((stream,utc,value),set()).add(seq)
    return index
