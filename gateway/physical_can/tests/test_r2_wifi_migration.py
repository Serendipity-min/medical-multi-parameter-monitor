"""换网事务使用ROM内存模型注入故障，验证应用不被擦写、失败闭锁和可恢复边界。"""
from datetime import datetime,timedelta,timezone
import json
import sys

import pytest

from gateway.physical_can import r2_config_record as record
from gateway.physical_can import r2_flash_c as gate
from gateway.physical_can.tests.test_r2_persistent_download import fixture_inputs,Rom,baseline


@pytest.fixture
def inputs(monkeypatch):
    manifest,image,old=fixture_inputs();new=record.replace_wifi(old,'new-synthetic-ap','new-synthetic-password')
    rom=Rom();rom.memory[:]=image.ljust(0xC000,b'\xff')+old.ljust(0x4000,b'\xff')
    monkeypatch.setattr(gate,'protected_hashes',lambda boot:boot.protected.copy())
    proof,backup=baseline(rom)
    return manifest,image,old,new,rom,proof,backup


def test_wifi_update_and_restore_never_write_application(inputs):
    m,image,old,new,rom,proof,backup=inputs
    result=gate.update_wifi(rom,m,image,old,new,proof,backup,lambda *args:None)
    assert result['application_unchanged'] and rom.erases==[[3]]
    assert [at for at,_ in rom.writes]==[gate.CONFIG,gate.CONFIG+24,gate.CONFIG+20]
    assert bytes(rom.memory[:0xC000])==backup[:0xC000]
    restored=gate.restore_wifi(rom,proof,backup,gate.sha(bytes(rom.memory)),lambda *args:None)
    assert rom.erases==[[3],[3]] and bytes(rom.memory)==backup and restored['restore_readback_match']
    assert all(at>=gate.CONFIG for at,_ in rom.writes)


@pytest.mark.parametrize('fault',['mqtt','floor','generation','same_wifi','backup','current','protection','options','erase_unavailable'])
def test_wrong_change_or_baseline_blocks_before_erase(inputs,fault):
    m,image,old,new,rom,proof,backup=inputs
    payload=bytearray(new[24:])
    if fault=='mqtt':payload[106]^=1;new=record.pack(bytes(payload),2)
    elif fault=='floor':payload[4]^=1;new=record.pack(bytes(payload),2)
    elif fault=='generation':new=record.pack(bytes(payload),3)
    elif fault=='same_wifi':new=record.pack(old[24:],2)
    elif fault=='backup':proof['sha256']='wrong'
    elif fault=='current':rom.memory[50]^=1
    elif fault=='protection':rom.protected={'fixed':'changed'}
    elif fault=='options':rom.options=b'changed'+rom.options[7:]
    else:rom.extended_erase=False
    with pytest.raises(gate.GateError):gate.update_wifi(rom,m,image,old,new,proof,backup,lambda *args:None)
    assert not rom.erases and not rom.writes


@pytest.mark.parametrize('fault',['pending','commit'])
def test_interrupted_config_stays_inside_sector3(inputs,fault):
    m,image,old,new,rom,proof,backup=inputs;rom.fail=fault
    with pytest.raises(gate.GateError):gate.update_wifi(rom,m,image,old,new,proof,backup,lambda *args:None)
    assert rom.erases==[[3]] and bytes(rom.memory[:0xC000])==backup[:0xC000]
    if fault=='pending':assert all(at!=gate.CONFIG+20 for at,_ in rom.writes)
    # 更新中断后，先记录实际当前摘要；恢复仍只写sector3，不执行GO或应用重刷。
    rom.fail=None
    gate.restore_wifi(rom,proof,backup,gate.sha(bytes(rom.memory)),lambda *args:None)
    assert bytes(rom.memory)==backup and rom.erases==[[3],[3]]


def test_restore_refuses_changed_application(inputs):
    _,_,_,_,rom,proof,backup=inputs;rom.memory[12]^=1
    with pytest.raises(gate.GateError,match='WIFI_APPLICATION_CHANGED'):
        gate.restore_wifi(rom,proof,backup,gate.sha(bytes(rom.memory)),lambda *args:None)
    assert not rom.erases


def test_wifi_backup_double_reads_current_persistent_image(inputs,tmp_path):
    m,image,old,new,rom,proof,backup=inputs;plan=gate.wifi_plan(m,image,old,new)
    actual=gate.capture_wifi_backup(rom,plan,proof,tmp_path,'synthetic-identity')
    assert actual['sha256']==gate.sha(backup) and actual['double_read_match']
    assert (tmp_path/'c-sector0-3-first.bin').read_bytes()==backup
    assert (tmp_path/'c-sector0-3-second.bin').read_bytes()==backup and not rom.erases


def test_backup_refuses_other_current_config(inputs,tmp_path):
    m,image,old,new,rom,proof,_=inputs;rom.memory[0xC030]^=1
    with pytest.raises(gate.GateError,match='CURRENT_WIFI_BASELINE_MISMATCH'):
        gate.capture_wifi_backup(rom,gate.wifi_plan(m,image,old,new),proof,tmp_path,'synthetic')
    assert not list(tmp_path.iterdir()) and not rom.erases


@pytest.mark.parametrize('fault',['full_app_scope','old_record'])
def test_wifi_window_cannot_inherit_full_app_authorization(inputs,fault):
    m,image,old,new,_,_,_=inputs;p=gate.wifi_plan(m,image,old,new)
    w={**p,'source_commit':'synthetic','actions':['wifi-update'],'identity_source_sha256':'identity',
       'mqtt_tls_port':8884,'expires_utc':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    gate.check_window(w,'wifi-update',p,'synthetic','identity')
    if fault=='full_app_scope':w['erase_sectors']=[0,1,2,3]
    else:w['previous_record_sha256']='other'
    with pytest.raises(gate.GateError):gate.check_window(w,'wifi-update',p,'synthetic','identity')


@pytest.mark.parametrize('ssid,password',[('x'*33,'pw'),('new','p'*65),('bad\0ssid','pw'),('bad"ssid','pw'),('','pw')])
def test_private_wifi_encoding_rejects_truncation_and_at_control(inputs,ssid,password):
    old=inputs[2]
    with pytest.raises(record.RecordError):record.replace_wifi(old,ssid,password)


def test_wifi_cli_plan_does_not_import_serial(inputs,tmp_path,monkeypatch,capsys):
    m,image,old,new,*_=inputs
    for name,data in [('manifest.json',json.dumps(m).encode()),('image.bin',image),('old.bin',old),('new.bin',new)]:
        (tmp_path/name).write_bytes(data)
    monkeypatch.setitem(sys.modules,'serial',None)
    monkeypatch.setattr(sys,'argv',['r2_flash_c','--action','wifi-plan','--manifest',str(tmp_path/'manifest.json'),
      '--image',str(tmp_path/'image.bin'),'--record',str(tmp_path/'new.bin'),'--previous-record',str(tmp_path/'old.bin')])
    assert gate.main()==0
    result=json.loads(capsys.readouterr().out)
    assert not result['hardware_accessed'] and result['plan']['erase_sectors']==[3]
