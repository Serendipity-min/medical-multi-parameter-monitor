"""C-SWD一次重刷的错误角色、原件和配置保护；全部合成内存，无J-Link进程。"""
from pathlib import Path
import pytest
from tools import h3_c_jlink as tool


class FakeBridge:
    def __init__(self,flash,uid,options):self.flash=flash;self.uid=uid;self.options=options;self.loads=0;self.reads=0;self.bad_second=False;self.corrupt_config=False;self.freeze=b'\0'*4
    def execute(self,commands,write=False):
        for line in commands:
            if line.startswith('w4 0xE0042008 '):self.freeze=int(line.split()[-1],16).to_bytes(4,'little')
            if line.startswith('loadbin '):
                assert write;self.loads+=1;image=Path(line[8:].split(',')[0]).read_bytes()
                self.flash=image.ljust(49152,b'\xff')+self.flash[49152:]
                if self.corrupt_config:self.flash=self.flash[:49152]+b'!'+self.flash[49153:]
            if not line.startswith('savebin '):continue
            path,address,length=line[8:].split(', ');address,length=int(address,16),int(length,16)
            values={0xE0042000:(0x413).to_bytes(4,'little'),0x1FFF7A22:(1024).to_bytes(2,'little'),
                0x1FFF7A10:self.uid,0x1FFFC000:self.options,0xE0042008:self.freeze,
                0x00000000:b'R'*8,0x1FFF0000:b'R'*8}
            if address==0x08000000:
                self.reads+=1;value=self.flash
                if self.bad_second and self.reads==2:value=b'!'+value[1:]
            else:value=values.get(address,b'\xff'*length)
            Path(path).write_bytes(value[:length])


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    image=tmp_path/'candidate.bin';image.write_bytes(b'C'*43172)
    memory=image.read_bytes().ljust(49152,b'\xff')+b'R'*336+b'\xff'*(65536-49152-336)
    options=b'\x00\xaa'+b'\xff'*14;uid=b'C'*12
    monkeypatch.setattr(tool.expected,'IMAGE',tool.sha(image.read_bytes()))
    monkeypatch.setattr(tool.expected,'RECORD',tool.sha(b'R'*336));monkeypatch.setattr(tool.expected,'FULL',tool.sha(memory))
    monkeypatch.setattr(tool.expected,'OPTIONS',tool.sha(options));monkeypatch.setattr(tool.expected,'validate',lambda b:2)
    monkeypatch.setattr(tool,'plan',lambda image:{'synthetic':True})
    private=tmp_path/'private';private.mkdir()
    identity={'EXPECTED_CHIP_ID':'0x413','EXPECTED_UID':tool.Stm32Bootloader.format_uid(uid)}
    return image,private,identity,FakeBridge(memory,uid,options)


def test_one_c_application_load_preserves_config_and_protected(fixture):
    image,private,identity,bridge=fixture
    result=tool.Window(private,bridge,identity).run(image,True,{'flash_write_started':False})
    assert result['exit_code']==0 and bridge.loads==1
    assert result['config_sector3_unchanged'] and result['sector7_11_options_unchanged']
    assert (private/'first-flash64k.bin').read_bytes()==(private/'second-flash64k.bin').read_bytes()


@pytest.mark.parametrize('reason',['wrong_device','backup','current_image'])
def test_c_mismatch_stops_before_load(fixture,reason):
    image,private,identity,bridge=fixture
    if reason=='wrong_device':bridge.uid=b'A'*12
    if reason=='backup':bridge.bad_second=True
    if reason=='current_image':bridge.flash=b'!'+bridge.flash[1:]
    with pytest.raises(RuntimeError):tool.Window(private,bridge,identity).run(image,True,{'flash_write_started':False})
    assert bridge.loads==0


def test_c_config_readback_corruption_stops_without_second_load(fixture):
    image,private,identity,bridge=fixture;bridge.corrupt_config=True
    with pytest.raises(RuntimeError,match='CONFIG_READBACK'):tool.Window(private,bridge,identity).run(image,True,{'flash_write_started':False})
    assert bridge.loads==1 and (private/'flash-write-attempt.json').exists()


def test_c_readonly_action_has_no_load(fixture):
    image,private,identity,bridge=fixture
    result=tool.Window(private,bridge,identity).run(image,False,{'flash_write_started':False})
    assert result['exit_code']==0 and bridge.loads==0


def test_uart_permission_does_not_authorize_jlink_window(tmp_path):
    with pytest.raises(ValueError,match='EXPLICIT_C_JLINK_WINDOW'):
        tool.authorize({'auth_id':'AUTH-AC-C-READONLY'},tmp_path/'unused',tmp_path/'unused-identity')
