"""受限下载门禁回归：越界/原件变化在擦除前失败，成功只写应用及预留RAM。"""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import time
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from gateway.physical_can import h3_flash_c as gate


def inputs():
    image=struct.pack('<II',0x2001FE00,0x08000101)+b'\x00'*0x9000
    config=struct.pack('<II',0x31435747,int(time.time())-86400)
    config+=b''.join(b'x'.ljust(n,b'\0') for n in (33,65,65,33,65,41))
    config=config.ljust(312,b'\0')
    manifest={'exit_code':0,'feature':'H3_NETWORK_IRQ',
              'volatile_config':{'address':0x2001FE00,'bytes':312,'reserved_bytes':512,'flash_configuration_written':False},
              'image':{'start':gate.START,'end_exclusive':gate.START+len(image),'sha256':gate.sha(image),'erase_sectors':[0,1,2],
                       'CAN1_RX0_vector':{'strong_handler':True}}}
    return manifest,image,config


@pytest.mark.parametrize('case',['sector','hash','reservation','config_size','config_magic','time_floor','stack'])
def test_offline_download_rejects_bad_inputs(case):
    m,image,config=inputs()
    if case=='sector':m['image']['erase_sectors']=[0,1,2,7]
    elif case=='hash':image=image[:-1]+b'x'
    elif case=='reservation':m['volatile_config']['reserved_bytes']=0
    elif case=='config_size':config=config[:-1]
    elif case=='config_magic':config=b'xxxx'+config[4:]
    elif case=='time_floor':config=config[:4]+b'\0'*4+config[8:]
    elif case=='stack':
        image=b'\0'*4+image[4:];m['image']['sha256']=gate.sha(image)
    with pytest.raises(gate.GateError):gate.verify_plan(m,image,config)


class Rom:
    extended_erase=True
    def __init__(self):
        self.backup=b'\xff'*0xC000;self.image=self.backup;self.ram=b'';self.erases=[];self.writes=[]
        self.options=b'\x00\xaa'+b'\0'*14
    def read_memory_data(self,address,length):
        if address==0x1FFFC000:return self.options
        if address==gate.START:return self.image[:length]
        if address==0x2001FE00:return self.ram[:length]
        raise AssertionError('unexpected read')
    def extended_erase_memory(self,sectors):self.erases.append(sectors)
    def write_memory_data(self,address,data):
        self.writes.append((address,len(data)))
        if address==gate.START:self.image=data
        elif address==0x2001FE00:self.ram=data
        else:raise AssertionError('protected write')


@pytest.mark.parametrize('changed',['protected','options','application'])
def test_changed_baseline_never_erases(monkeypatch,changed):
    rom=Rom();m,image,config=inputs()
    baseline={'options_sha256':gate.sha(rom.options),'protected':{'same':True}}
    monkeypatch.setattr(gate,'protected_hashes',lambda boot:{'same':changed!='protected'})
    if changed=='options':baseline['options_sha256']='changed'
    if changed=='application':rom.image=b'x'+rom.image[1:]
    with pytest.raises(gate.GateError):gate.program(rom,image,m['image'],config,baseline,rom.backup,lambda *args:None)
    assert not rom.erases and not rom.writes


def test_program_writes_exact_app_sectors_and_ram(monkeypatch):
    rom=Rom();m,image,config=inputs();baseline={'options_sha256':gate.sha(rom.options),'protected':{'same':True}}
    monkeypatch.setattr(gate,'protected_hashes',lambda boot:{'same':True})
    result=gate.program(rom,image,m['image'],config,baseline,rom.backup,lambda *args:None)
    assert rom.erases==[[0,1,2]]
    assert [addr for addr,size in rom.writes]==[gate.START,0x2001FE00]
    assert result['protected_before']==result['protected_after'] and not result['configuration_flash_written']


def test_update_candidate_requires_matching_current_bytes(monkeypatch):
    rom=Rom();m,image,config=inputs();baseline={'options_sha256':gate.sha(rom.options),'protected':{'same':True}}
    monkeypatch.setattr(gate,'protected_hashes',lambda boot:{'same':True})
    prior=b'previous-verified-application';rom.image=prior
    with pytest.raises(gate.GateError):gate.program(rom,image,m['image'],config,baseline,rom.backup,lambda *a:None)
    assert not rom.erases
    gate.program(rom,image,m['image'],config,baseline,rom.backup,lambda *a:None,current_application=prior)
    assert rom.erases==[[0,1,2]] and rom.backup==b'\xff'*0xC000


def test_application_rollback_has_exact_scope_and_no_run(monkeypatch):
    rom=Rom();baseline={'options_sha256':gate.sha(rom.options),'protected':{'same':True}}
    monkeypatch.setattr(gate,'protected_hashes',lambda boot:{'same':True})
    current=b'prior-candidate';rom.image=current
    result=gate.restore_application(rom,baseline,rom.backup,current,lambda *a:None)
    assert rom.image==rom.backup and rom.erases==[[0,1,2]]
    assert rom.writes==[(gate.START,len(rom.backup))] and not result['rollback_application_executed']
