"""维护门禁负例：内存Flash替身证明越区/原件变化在写入前停止，不连接J-Link。"""
from pathlib import Path
import json
import pytest
from gateway.voice import cloud_window as w


def test_plan_requires_verified_8883_image_inside_sector3(tmp_path):
    image=tmp_path/'app.bin';image.write_bytes(b'v'*47272)
    manifest=tmp_path/'manifest.json'
    data={'exit_code':0,'cloud_voice':True,'compiled_MQTT_port':8883,
          'image':{'sha256':w.sha(image.read_bytes()),'erase_sectors':[0,1,2]}}
    manifest.write_text(json.dumps(data))
    result=w.plan(image,manifest)
    assert result['write_end_exclusive']==0x0800c000 and result['preserve_sectors'][0]==3
    for mutation in ('port','sector','hash','exit'):
        bad=json.loads(json.dumps(data))
        if mutation=='port':bad['compiled_MQTT_port']=8884
        if mutation=='sector':bad['image']['erase_sectors']=[0,1,2,3]
        if mutation=='hash':bad['image']['sha256']='0'*64
        if mutation=='exit':bad['exit_code']=1
        manifest.write_text(json.dumps(bad))
        with pytest.raises(ValueError):w.plan(image,manifest)


class FakeWindow(w.Window):
    def __init__(self,path,original,change=False):
        self.private=path;self.memory=original;self.write_calls=0;self.change=change
    def identity_read(self,label):return {k:b'\0'*4 for k in ('chip','size','uid','options','freeze')}
    def protection(self,label):return {'sector7':b'protected','sector11':b'protected','options':b'rdp'}
    def controller(self,label):return b'clean'
    def read(self,label,specs,extra=()):
        for command in extra:
            if command.startswith('loadbin '):
                self.write_calls+=1;file=command.split(' ',1)[1].split(',')[0]
                self.memory=Path(file).read_bytes()+self.memory[w.APP:]
                if self.change:self.memory=self.memory[:-1]+b'X'
        out={}
        for name,_,size in specs:
            out[name]=self.memory if name=='flash64k' else b'\0'*size
            (self.private/(label+'-'+name+'.bin')).write_bytes(out[name])
        return out


def test_application_write_preserves_every_config_byte(tmp_path):
    before=b'old'.ljust(w.APP,b'\xff')+b'C'*16384
    fake=FakeWindow(tmp_path,before)
    new=b'new'.ljust(w.APP,b'\xff')
    result=fake.transact(new,before,'trial')
    assert result['sector3_7_11_options_unchanged'] and fake.memory==new+before[w.APP:] and fake.write_calls==1


def test_changed_original_stops_before_write(tmp_path):
    fake=FakeWindow(tmp_path,b'A'*65536)
    with pytest.raises(ValueError,match='CURRENT_BACKUP'):fake.transact(b'N'*49152,b'B'*65536,'trial')
    assert fake.write_calls==0


def test_protected_config_change_stops_without_automatic_restore(tmp_path):
    before=b'A'*65536;fake=FakeWindow(tmp_path,before,True)
    with pytest.raises(ValueError,match='CONFIG_READBACK'):fake.transact(b'N'*49152,before,'trial')
    assert fake.write_calls==1


def test_oversized_block_never_reaches_flash(tmp_path):
    fake=FakeWindow(tmp_path,b'A'*65536)
    with pytest.raises(ValueError,match='BLOCK_SIZE'):fake.transact(b'N'*65536,b'A'*65536,'trial')
    assert fake.write_calls==0
