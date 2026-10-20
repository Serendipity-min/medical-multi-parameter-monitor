"""台架下载事务的离线故障回归；不创建串口、设备或真实凭据。"""
from datetime import datetime,timedelta,timezone
import builtins
import json
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from gateway.physical_can import r2_config_record as record
from gateway.physical_can import r2_flash_c as gate


def fixture_inputs():
    payload=struct.pack('<II',0x31435747,1800000000)
    values=('synthetic-ap','synthetic-wifi-password','mqtt.example.invalid','h3-synthetic','synthetic-secret','h3-c-synthetic')
    payload+=b''.join(v.encode().ljust(n,b'\0') for v,n in zip(values,(33,65,65,33,65,41)))+b'\0\0'
    config=record.pack(payload,1)
    image=bytearray(0xA000);struct.pack_into('<II',image,0,0x20020000,gate.START+0x101)
    struct.pack_into('<I',image,144,gate.START+0x201);image=bytes(image)
    manifest={'exit_code':0,'feature':'H3_NETWORK_IRQ','fresh_sntp':True,
      'commands':[['gcc','-DMP_MQTT_TLS_PORT=8884','-DMP_H3_TEST_SOURCE','-DMP_H3_PERSISTENT_CONFIG']],
      'persistent_config':{'address':gate.CONFIG,'sector':3,'record_bytes':336,'erase_bytes':0x4000,'runtime_flash_writes':False},
      'image':{'start':gate.START,'end_exclusive':gate.START+len(image),'bytes':len(image),'sha256':gate.sha(image),
       'erase_sectors':[0,1,2],'initial_sp':0x20020000,'reset_vector':gate.START+0x101,
       'CAN1_RX0_vector':{'strong_handler':True,'address':gate.START+0x201},
       'protected_sectors':[7,11],'mass_erase':False,'option_bytes_write':False,
       'load_segments':[{'start':gate.START,'end_exclusive':gate.START+len(image)}]}}
    return manifest,image,config


class Rom:
    extended_erase=True
    def __init__(self):
        self.memory=bytearray(b'\x11'*gate.SPAN);self.options=b'\0\xaa'+b'\0'*14
        self.protected={'fixed':'synthetic-hash'};self.erases=[];self.writes=[];self.fail=None
    def read_memory_data(self,address,length):
        if address==0x1FFFC000:return self.options
        assert gate.START<=address<address+length<=gate.START+gate.SPAN
        return bytes(self.memory[address-gate.START:address-gate.START+length])
    def extended_erase_memory(self,sectors):
        assert sectors in ([0,1,2],[3],[0,1,2,3])
        self.erases.append(sectors[:])
        for n in sectors:self.memory[n*0x4000:(n+1)*0x4000]=b'\xff'*0x4000
    def write_memory_data(self,address,data):
        assert address%4==0 and len(data)%4==0
        assert gate.START<=address<address+len(data)<=gate.START+gate.SPAN
        self.writes.append((address,bytes(data)))
        at=address-gate.START
        assert all(old&new==new for old,new in zip(self.memory[at:at+len(data)],data))
        self.memory[at:at+len(data)]=data
        if self.fail=='application' and address==gate.START:self.memory[0]^=1
        if self.fail=='pending' and address==gate.CONFIG+24:self.memory[gate.CONFIG-gate.START+24]^=1
        if self.fail=='commit' and address==gate.CONFIG+20:self.memory[gate.CONFIG-gate.START+20]^=1


@pytest.fixture
def rom(monkeypatch):
    value=Rom();monkeypatch.setattr(gate,'protected_hashes',lambda boot:boot.protected.copy())
    return value


def baseline(rom):
    backup=bytes(rom.memory)
    return {'exit_code':0,'double_read_match':True,'bytes':gate.SPAN,'sha256':gate.sha(backup),
            'protected':rom.protected.copy(),'options_sha256':gate.sha(rom.options)},backup


def test_python_record_is_accepted_by_actual_c_verifier(tmp_path):
    _,_,config=fixture_inputs();root=Path(__file__).resolve().parents[3]
    source=tmp_path/'verify.c';source.write_text('''#include "persistent_config.h"
#include <stdio.h>
/* 直接调用固件验证器，校验Python打包的CRC/布局，避免两份Python规则自证。 */
int main(void){H3ConfigRecord r;if(fread(&r,1,sizeof(r),stdin)!=sizeof(r))return 2;return h3_config_record_valid(&r)?0:1;}
''')
    built=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(root/'gateway/mqtt/src'),str(source),'-o',str(tmp_path/'verify.exe')],capture_output=True)
    assert built.returncode==0,built.stderr.decode(errors='replace')
    assert subprocess.run([str(tmp_path/'verify.exe')],input=config,capture_output=True).returncode==0
    for at in (0,4,8,12,16,20,24,335):
        bad=bytearray(config);bad[at]^=1
        assert subprocess.run([str(tmp_path/'verify.exe')],input=bad,capture_output=True).returncode==1
        with pytest.raises(record.RecordError):record.validate(bad)


def test_manual_rom_stabilizes_and_discards_old_host_input_before_sync(monkeypatch):
    events=[]
    class Uart:
        def reset_input_buffer(self):events.append('clear_host_input')
        def write(self,data):events.append(('write',data))
        def read(self,size):events.append(('read',size));return b'\x79'
    class Boot:
        def get(self):events.append('get')
    monkeypatch.setattr(gate.time,'sleep',lambda value:events.append(('sleep',value)))
    gate.synchronize_ready_rom(Uart(),Boot())
    assert events==[('sleep',.3),'clear_host_input',('write',b'\x7f'),('read',1),'get']


@pytest.mark.parametrize('fault',['sectors','app_hash','sp','irq','ram','normal_port','load','record_crc','record_uncommitted'])
def test_offline_plan_blocks_wrong_scope(fault):
    m,image,config=fixture_inputs()
    if fault=='sectors':m['image']['erase_sectors']=[0,1,2,3]
    elif fault=='app_hash':image=image[:-1]+b'x'
    elif fault=='sp':m['image']['initial_sp']=0x2001FE00
    elif fault=='irq':m['image']['CAN1_RX0_vector']['strong_handler']=False
    elif fault=='ram':m['volatile_config']={'address':0x2001FE00}
    elif fault=='normal_port':m['commands'][0].remove('-DMP_MQTT_TLS_PORT=8884')
    elif fault=='load':m['image']['load_segments'][0]['end_exclusive']=gate.CONFIG+4
    elif fault=='record_crc':config=config[:24]+bytes([config[24]^1])+config[25:]
    else:config=config[:20]+b'\xff'*4+config[24:]
    with pytest.raises((gate.GateError,record.RecordError)):gate.offline_plan(m,image,config)


def test_program_commit_is_last_and_only_approved_ranges_are_written(rom):
    m,image,config=fixture_inputs();b,backup=baseline(rom)
    result=gate.program(rom,m,image,config,b,backup,lambda *args:None)
    assert rom.erases==[[0,1,2],[3]]
    assert [p for p,_ in rom.writes]==[gate.START,gate.CONFIG,gate.CONFIG+24,gate.CONFIG+20]
    assert rom.writes[-1][1]==struct.pack('<I',record.COMMITTED)
    assert bytes(rom.memory)==image.ljust(0xC000,b'\xff')+config.ljust(0x4000,b'\xff')
    assert result['exit_code']==0 and not result['automatic_go'] and result['physical_cold_boot']=='NOT_TESTED'


@pytest.mark.parametrize('fault',['backup','current','protected','options','no_extended_erase'])
def test_invalid_baseline_never_erases(rom,fault):
    m,image,config=fixture_inputs();b,backup=baseline(rom)
    if fault=='backup':backup=b'x'+backup[1:]
    elif fault=='current':rom.memory[0]^=1
    elif fault=='protected':rom.protected={'fixed':'changed'}
    elif fault=='options':rom.options=b'x'+rom.options[1:]
    else:rom.extended_erase=False
    with pytest.raises(gate.GateError):gate.program(rom,m,image,config,b,backup,lambda *args:None)
    assert rom.erases==[] and rom.writes==[]


@pytest.mark.parametrize('fault',['application','pending','commit'])
def test_readback_failure_stops_without_go_or_retry(rom,fault):
    m,image,config=fixture_inputs();b,backup=baseline(rom);rom.fail=fault
    with pytest.raises(gate.GateError):gate.program(rom,m,image,config,b,backup,lambda *args:None)
    if fault=='application':assert rom.erases==[[0,1,2]]
    if fault=='pending':
        assert all(p!=gate.CONFIG+20 for p,_ in rom.writes)
        assert bytes(rom.memory[0xC014:0xC018])==b'\xff'*4
    assert len(rom.erases)<=2


def test_protection_change_after_app_stops_before_config_erase(rom):
    m,image,config=fixture_inputs();b,backup=baseline(rom)
    original=rom.write_memory_data
    def changed(address,data):original(address,data);rom.protected={'fixed':'changed'}
    rom.write_memory_data=changed
    with pytest.raises(gate.GateError,match='PROTECTED_BASELINE_CHANGED'):
        gate.program(rom,m,image,config,b,backup,lambda *args:None)
    assert rom.erases==[[0,1,2]]


def previous_receipt(rom):
    return {'role':'C','exit_code':0,'image_readback_match':True,'protected_unchanged':True,'options_unchanged':True,
      'protected_after':rom.protected.copy(),'options_sha256':gate.sha(rom.options),'image':{'bytes':42728,'sha256':gate.sha(bytes(rom.memory[:42728]))}}


def test_backup_twice_and_restore_exact_original_64k(rom,tmp_path):
    proof=gate.capture_backup(rom,previous_receipt(rom),tmp_path,'synthetic-identity-sha')
    first=(tmp_path/'c-sector0-3-first.bin').read_bytes()
    assert first==(tmp_path/'c-sector0-3-second.bin').read_bytes()
    assert proof['double_read_match'] and proof['bytes']==65536 and not rom.erases
    m,image,config=fixture_inputs();gate.program(rom,m,image,config,proof,first,lambda *args:None)
    current=gate.sha(bytes(rom.memory));rom.erases.clear();rom.writes.clear()
    with pytest.raises(gate.GateError):gate.restore(rom,proof,first,'wrong',lambda *args:None)
    assert not rom.erases
    restored=gate.restore(rom,proof,first,current,lambda *args:None)
    assert rom.erases==[[0,1,2,3]] and bytes(rom.memory)==first and not restored['automatic_go']


def test_backup_inconsistent_reads_creates_no_proof_or_files(rom,tmp_path):
    receipt=previous_receipt(rom);read=rom.read_memory_data;count=[0]
    def changing(address,length):
        value=read(address,length)
        if address==gate.START and length==gate.SPAN:
            count[0]+=1
            if count[0]==2:return b'x'+value[1:]
        return value
    rom.read_memory_data=changing
    with pytest.raises(gate.GateError,match='BACKUP_READS_DIFFER'):gate.capture_backup(rom,receipt,tmp_path,'synthetic')
    assert list(tmp_path.iterdir())==[] and not rom.erases


@pytest.mark.parametrize('fault',['expired','source','config','role','identity','port','action'])
def test_owner_window_is_bound_to_action_source_device_and_config(fault):
    m,image,config=fixture_inputs();p=gate.offline_plan(m,image,config)
    w={'expires_utc':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'role':'C','port':'COM15',
       'source_commit':'synthetic-commit','actions':['backup','program','restore'],'erase_sectors':[0,1,2,3],
       'image_sha256':p['image_sha256'],'record_sha256':p['record_sha256'],'identity_source_sha256':'synthetic-identity','mqtt_tls_port':8884}
    gate.check_window(w,'program',p,'synthetic-commit','synthetic-identity')
    if fault=='expired':w['expires_utc']='2000-01-01T00:00:00+00:00'
    elif fault=='source':w['source_commit']='other'
    elif fault=='config':w['record_sha256']='other'
    elif fault=='role':w['role']='A'
    elif fault=='identity':w['identity_source_sha256']='other'
    elif fault=='port':w['mqtt_tls_port']=8883
    else:w['actions']=['backup']
    with pytest.raises(gate.GateError):gate.check_window(w,'program',p,'synthetic-commit','synthetic-identity')


@pytest.mark.parametrize('action',['plan','program'])
def test_default_plan_and_missing_window_never_import_serial(tmp_path,monkeypatch,capsys,action):
    m,image,config=fixture_inputs()
    for name,data in [('manifest.json',json.dumps(m).encode()),('image.bin',image),('record.bin',config)]:
        (tmp_path/name).write_bytes(data)
    argv=['r2_flash_c','--action',action,'--manifest',str(tmp_path/'manifest.json'),'--image',str(tmp_path/'image.bin'),'--record',str(tmp_path/'record.bin')]
    monkeypatch.setattr(sys,'argv',argv);original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name in ('serial','stm32loader.uart','stm32loader.bootloader'):raise AssertionError('hardware import attempted')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    assert gate.main()==(0 if action=='plan' else 1)
    value=json.loads(capsys.readouterr().out)
    assert not value['hardware_accessed'] and not value['flash_write_started']
    assert 'synthetic-secret' not in str(value) and 'mqtt.example.invalid' not in str(value)
