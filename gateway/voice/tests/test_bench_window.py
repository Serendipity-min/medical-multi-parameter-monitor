"""应用扇区范围/错误角色/回退原件的合成测试；绝不启动J-Link。"""
from pathlib import Path
import pytest
from gateway.voice import bench_window as tool


class FakeBridge:
    def __init__(self, flash, uid, options):
        self.flash=flash; self.uid=uid; self.options=options; self.freeze=bytes(4)
        self.loads=0; self.reads=0; self.bad_second=False; self.corrupt_other=False
        self.cr=0x80000000

    def execute(self, commands, write=False):
        for line in commands:
            if line.startswith('w4 0xE0042008 '):
                assert write; self.freeze=int(line.split()[-1],16).to_bytes(4,'little')
            if line.startswith('loadbin '):
                assert write; self.loads+=1
                block=Path(line[8:].split(',')[0]).read_bytes()
                assert len(block)==16384
                self.flash=block+self.flash[16384:]
                if self.corrupt_other: self.flash=self.flash[:20000]+b'!'+self.flash[20001:]
            if not line.startswith('savebin '): continue
            name, address, length=line[8:].split(', '); address=int(address,16); length=int(length,16)
            values={0xE0042000:(0x413).to_bytes(4,'little'),0x1FFF7A22:(1024).to_bytes(2,'little'),
                    0x1FFF7A10:self.uid,0x1FFFC000:self.options,0xE0042008:self.freeze,
                    0:bytes(8),0x1FFF0000:bytes(8),0x40023c0c:bytes(4)+self.cr.to_bytes(4,'little')}
            if address==0x08000000:
                self.reads+=1; data=self.flash
                if self.bad_second and self.reads==2: data=b'!'+data[1:]
            else: data=values.get(address,b'\xff'*length)
            Path(name).write_bytes(data[:length])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    current=b'C'*43172; record=b'R'*336
    flash=current.ljust(49152,b'\xff')+record.ljust(16384,b'\xff')
    options=b'\0\xaa'+b'\xff'*14; uid=b'C'*12
    monkeypatch.setattr(tool,'CURRENT_IMAGE',tool.sha(current))
    monkeypatch.setattr(tool,'CURRENT_FULL',tool.sha(flash))
    monkeypatch.setattr(tool,'CURRENT_RECORD',tool.sha(record))
    monkeypatch.setattr(tool.base.expected,'OPTIONS',tool.sha(options))
    monkeypatch.setattr(tool,'validate',lambda x:3)
    image=tmp_path/'bench.bin'; image.write_bytes(b'B'*100)
    monkeypatch.setattr(tool,'plan',lambda p:{'write_block_sha256':tool.sha(p.read_bytes().ljust(16384,b'\xff'))})
    private=tmp_path/'program'; private.mkdir()
    identity={'EXPECTED_CHIP_ID':'0x413','EXPECTED_UID':tool.base.Stm32Bootloader.format_uid(uid)}
    bridge=FakeBridge(flash,uid,options)
    return tmp_path,private,image,identity,bridge,flash


def test_exact_sector0_program_and_restore(setup):
    root,private,image,identity,bridge,original=setup
    result=tool.Window(private,bridge,identity).program(image)
    assert result['exit_code']==0 and bridge.loads==1 and bridge.flash[16384:]==original[16384:]
    restore=root/'restore'; restore.mkdir()
    result=tool.Window(restore,bridge,identity).restore(private)
    assert result['exit_code']==0 and bridge.loads==2 and bridge.flash==original


@pytest.mark.parametrize('fault',['wrong-role','double-read','old-image','controller'])
def test_prewrite_failure_never_loads(setup,fault):
    _,private,image,identity,bridge,_=setup
    if fault=='wrong-role': bridge.uid=b'A'*12
    if fault=='double-read': bridge.bad_second=True
    if fault=='old-image': bridge.flash=b'!'+bridge.flash[1:]
    if fault=='controller': bridge.cr=0x80000001
    with pytest.raises(RuntimeError): tool.Window(private,bridge,identity).program(image)
    assert bridge.loads==0


def test_unrequested_sector_change_stops_without_auto_restore(setup):
    _,private,image,identity,bridge,_=setup; bridge.corrupt_other=True
    with pytest.raises(RuntimeError,match='PRESERVED_SECTOR'): tool.Window(private,bridge,identity).program(image)
    assert bridge.loads==1


def test_changed_restore_original_is_rejected(setup):
    root,private,image,identity,bridge,_=setup
    tool.Window(private,bridge,identity).program(image)
    (private/'original-sector0.bin').write_bytes(b'!'*16384)
    restore=root/'restore'; restore.mkdir()
    with pytest.raises(RuntimeError,match='ORIGINAL_CHANGED'): tool.Window(restore,bridge,identity).restore(private)
    assert bridge.loads==1
