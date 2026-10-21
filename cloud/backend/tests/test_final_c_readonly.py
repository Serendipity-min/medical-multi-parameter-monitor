"""C当前原件核验只用合成内存；FakeBoot没有任何Flash写入方法。"""
from pathlib import Path
import pytest
from tools import h3_c_readonly as reader


class FakeBoot:
    def __init__(self,flash,options):self.flash=flash;self.options=options;self.reads=0;self.mismatch=False
    def read_memory_data(self,address,length):
        if address==0x1FFFC000:return self.options
        if address==0x08000000:
            self.reads+=1
            return (b'!'+self.flash[1:]) if self.mismatch and self.reads==2 else self.flash
        return b'\xff'*length


@pytest.fixture
def synthetic(monkeypatch):
    flash=b'A'*43172+b'\xff'*(49152-43172)+b'R'*336+b'\xff'*(65536-49152-336)
    options=b'\x00\xaa'+b'\xff'*14
    monkeypatch.setattr(reader,'IMAGE',reader.sha(flash[:43172]));monkeypatch.setattr(reader,'RECORD',reader.sha(b'R'*336))
    monkeypatch.setattr(reader,'FULL',reader.sha(flash));monkeypatch.setattr(reader,'OPTIONS',reader.sha(options))
    monkeypatch.setattr(reader,'validate',lambda b:2)
    return FakeBoot(flash,options)


def test_current_c_pair_and_full_double_read_without_any_write_api(synthetic,tmp_path):
    result=reader.capture(synthetic,tmp_path)
    assert result['exit_code']==0 and not result['flash_write'] and not result['RAM_write']
    assert (tmp_path/'c-current-first.bin').read_bytes()==(tmp_path/'c-current-second.bin').read_bytes()


def test_c_double_read_disagreement_retained_and_stops(synthetic,tmp_path):
    synthetic.mismatch=True
    with pytest.raises(RuntimeError,match='DOUBLE_OR_DISK'):reader.capture(synthetic,tmp_path)
    assert (tmp_path/'c-current-first.bin').exists() and (tmp_path/'c-current-second.bin').exists()


def test_total_contract_does_not_authorize_c_read():
    with pytest.raises(ValueError,match='C_READ_WINDOW_REQUIRED'):reader.authorize({},Path('unused-synthetic-reference'))
