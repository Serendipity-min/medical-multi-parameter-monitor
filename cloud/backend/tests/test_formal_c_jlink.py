"""正式C事务的合成Flash回归：commit最后写，任何门禁失败均不继续编程。"""
from pathlib import Path
import struct
import pytest
from tools import h3_c_formal as tool
from gateway.physical_can.tests.test_r2_persistent_download import fixture_inputs
from gateway.physical_can.r2_config_record import pack


class FakeBridge:
    def __init__(self,flash,uid,options):
        self.flash=flash;self.uid=uid;self.options=options;self.freeze=b'\0'*4
        self.cr=0x80000000;self.sr=0;self.loads=0;self.commits=0;self.fail=None;self.reads=0
    def exact(self,commands):self.execute(commands,True)
    def execute(self,commands,write=False):
        for line in commands:
            if line.startswith('w4 '):
                assert write;_,address,value=line.split();address=int(address,16);value=int(value,16)
                if address==0xE0042008:self.freeze=struct.pack('<I',value)
                elif address==tool.KEYR:
                    if value==0xcdef89ab:self.cr&=~(1<<31)
                elif address==tool.CR:
                    # 实板回执显示：单次同时LOCK与清PG保留了旧低位，模型覆盖该实际失败路径。
                    if not self.cr&(1<<31):self.cr=(self.cr|(1<<31)) if value&(1<<31) else value
                elif address==tool.COMMIT:
                    assert self.cr&1 and (self.cr&0x300)==0x200 and not self.cr&(1<<31)
                    assert self.flash[0xC014:0xC018]==b'\xff'*4
                    self.commits+=1;data=struct.pack('<I',value)
                    self.flash=self.flash[:0xC014]+data+self.flash[0xC018:]
                    if self.fail=='commit':self.sr=0x80
                else:raise AssertionError('OUT_OF_SCOPE_MMIO')
            if line.startswith('loadbin '):
                assert write;self.loads+=1;self.flash=Path(line[8:].split(',')[0]).read_bytes()
                assert len(self.flash)==65536 and self.flash[0xC014:0xC018]==b'\xff'*4
                if self.fail=='pending':self.flash=b'!'+self.flash[1:]
                if self.fail=='status':self.sr=0x80
            if not line.startswith('savebin '):continue
            path,address,length=line[8:].split(', ');address=int(address,16);length=int(length,16)
            values={0xE0042000:struct.pack('<I',0x413),0x1FFF7A22:struct.pack('<H',1024),
                    0x1FFF7A10:self.uid,0x1FFFC000:self.options,0xE0042008:self.freeze,
                    0:b'R'*8,0x1FFF0000:b'R'*8,tool.SR:struct.pack('<II',self.sr,self.cr),tool.CR:struct.pack('<I',self.cr)}
            if address==0x08000000:
                self.reads+=1;value=self.flash
                if self.fail=='backup' and self.reads==2:value=b'!'+value[1:]
            else:value=values.get(address,b'\xff'*length)
            Path(path).write_bytes(value[:length])


@pytest.fixture
def state(tmp_path,monkeypatch):
    m,_,config=fixture_inputs();image=b'C'*43172;old=pack(config[24:],2);record=pack(config[24:],3)
    flash=image.ljust(49152,b'\xff')+old.ljust(16384,b'\xff');options=b'\0\xaa'+b'\xff'*14;uid=b'C'*12
    monkeypatch.setattr(tool.previous.expected,'FULL',tool.previous.sha(flash));monkeypatch.setattr(tool.previous.expected,'RECORD',tool.previous.sha(old));monkeypatch.setattr(tool.previous.expected,'OPTIONS',tool.previous.sha(options))
    monkeypatch.setattr(tool,'scope',lambda *args:{'synthetic_fixture':True})
    folder=tmp_path/'private';folder.mkdir();bridge=FakeBridge(flash,uid,options)
    identity={'EXPECTED_CHIP_ID':'0x413','EXPECTED_UID':tool.previous.Stm32Bootloader.format_uid(uid)}
    return m,image,record,folder,bridge,identity


def test_formal_commit_follows_full_pending_readback_and_protects_other_sectors(state):
    m,image,record,p,b,identity=state
    r=tool.Window(p,b,identity).run_formal(m,image,record,{})
    assert r['exit_code']==0 and b.loads==1 and b.commits==1
    assert b.flash==image.ljust(49152,b'\xff')+record.ljust(16384,b'\xff')
    assert r['commit_programmed_last'] and r['sector7_11_options_unchanged'] and b.cr==0x80000000


@pytest.mark.parametrize('fault,loads,commits',[('backup',0,0),('pending',1,0),('status',1,0),('commit',1,1)])
def test_formal_failure_stops_without_retry_or_clearing_error_status(state,fault,loads,commits):
    m,image,record,p,b,identity=state;b.fail=fault
    with pytest.raises((ValueError,RuntimeError)):tool.Window(p,b,identity).run_formal(m,image,record,{})
    assert b.loads==loads and b.commits==commits
    if fault in ('status','commit'):assert b.sr==0x80


def test_formal_commit_mmio_does_not_expand_old_isolated_bridge_whitelist(tmp_path):
    b=tool.previous.Bridge(tmp_path)
    with pytest.raises(ValueError):b.validate_commands(['connect','h','w4 0x40023c10 0x201','q'],True)
    leaf=tool.Bridge(tmp_path);leaf.exact_transaction=['connect','q']
    with pytest.raises(ValueError):leaf.validate_commands(['connect','w4 0x40023c10 0x201','q'],True)


@pytest.mark.parametrize('sr,cr',[(0x80,0),(1<<16,0),(0,1),(0,2),(0,4),(0,1<<16)])
def test_busy_error_or_erase_mode_cannot_enter_commit(sr,cr):
    with pytest.raises(ValueError):tool.checked_idle(sr,cr)


def test_postfailure_control_correction_never_reprograms_flash(state):
    m,image,record,p,b,identity=state
    b.flash=image.ljust(49152,b'\xff')+record.ljust(16384,b'\xff');before=b.flash
    b.cr=0x80000201;b.freeze=struct.pack('<I',0x1000)
    result=tool.Window(p,b,identity).restore_control_only(before,0x80000000,0)
    assert result['exit_code']==0 and b.cr==0x80000000 and b.freeze==b'\0'*4
    assert b.flash==before and b.loads==0 and b.commits==0


@pytest.mark.parametrize('fault',['flash','status','control','debug'])
def test_control_recovery_checks_current_state_before_unlocking(state,fault):
    m,image,record,p,b,identity=state
    expected=image.ljust(49152,b'\xff')+record.ljust(16384,b'\xff');b.flash=expected
    b.cr=0x80000201;b.freeze=struct.pack('<I',0x1000)
    if fault=='flash':b.flash=b'!'+b.flash[1:]
    if fault=='status':b.sr=0x80
    if fault=='control':b.cr=0x80000203
    if fault=='debug':b.freeze=b'\0'*4
    original_cr=b.cr
    with pytest.raises(ValueError):tool.Window(p,b,identity).restore_control_only(expected,0x80000000,0)
    assert b.cr==original_cr and not b.loads and not b.commits
