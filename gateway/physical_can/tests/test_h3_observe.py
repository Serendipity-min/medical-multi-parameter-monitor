"""报告缺失/串口未知内容不得被归并成设备队列零丢失；不连接真实串口。"""
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from gateway.physical_can import h3_observe as observer


class Uart:
    def __init__(self,data):self.data=data;self.in_waiting=len(data)
    def read(self,n):data=self.data[:n];self.data=self.data[n:];self.in_waiting=len(self.data);return data
    def write(self,data):raise AssertionError('passive observation must not write')


def report(seq,omit='',boff=0):
    rows={'METRICS':'can=54 drop=0 lost=0 nodes=10','RXQ':'fovr=0 sw=0 fault=0 uart=0 stale=0',
          'CANPROOF':f'hb=4 BOFF={boff}','DELIVERY':'qos1_puback=7 qos0_send=2 failed=0'}
    return ('GW DIAG_BEGIN seq='+str(seq)+' lines=4\n'+''.join('GW '+k+' '+v+'\n' for k,v in rows.items() if k!=omit)+
            'GW DIAG_END seq='+str(seq)+' lines=4\n').encode()


def run(tmp_path,monkeypatch,data):
    root=tmp_path/'repo';private=tmp_path/'private';private.mkdir()
    (root/'gateway/physical_can/evidence/h3').mkdir(parents=True)
    (root/'gateway/physical_can/build/h3-isolated').mkdir(parents=True)
    monkeypatch.setattr(observer,'ROOT',root)
    clock=iter(n*.01 for n in range(10000));monkeypatch.setattr(observer.time,'monotonic',lambda:next(clock))
    observer.observe(Uart(data),.3,private)
    import json
    state=json.loads((root/'gateway/physical_can/build/h3-isolated/uart-status.json').read_text())
    public=next((root/'gateway/physical_can/evidence/h3').glob('*.log')).read_text()
    return state,public


def test_host_gaps_independent_from_zero_device_overflow(tmp_path,monkeypatch):
    state,_=run(tmp_path,monkeypatch,report(1)+report(3,omit='DELIVERY'))
    assert state['latest']['queue']['fovr']==0
    assert state['host_log']['missing_reports']==1 and state['host_log']['missing_lines']==1
    assert state['host_log']['complete']==1


def test_busoff_stops_passive_capture(tmp_path,monkeypatch):
    state,_=run(tmp_path,monkeypatch,report(1,boff=1))
    assert state['state']=='CAN_FAULT_STOP' and state['exit_code']==1


def test_unknown_content_never_enters_public_log(tmp_path,monkeypatch):
    state,public=run(tmp_path,monkeypatch,b'GW UNKNOWN synthetic-private-payload\n'+report(1))
    assert 'synthetic-private-payload' not in public and state['host_log']['complete']==1
