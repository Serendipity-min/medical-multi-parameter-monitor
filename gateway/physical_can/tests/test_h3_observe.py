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
    root=tmp_path/'repo';private=tmp_path/'private';private.mkdir(parents=True)
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


def test_transient_windows_reader_does_not_stop_uart(tmp_path,monkeypatch):
    # 模拟目标文件被读者短占用；重试成功必须保持设备/Host计数原值。
    original=Path.replace;calls=[]
    def replace(path,target):
        calls.append(1)
        if len(calls)<3:raise PermissionError('synthetic sharing conflict')
        return original(path,target)
    monkeypatch.setattr(Path,'replace',replace)
    monkeypatch.setattr(observer.time,'sleep',lambda _:None)
    target=tmp_path/'status.json'
    observer.save_state(target,{'fovr':7,'host_missing':2})
    import json
    assert json.loads(target.read_text())=={'fovr':7,'host_missing':2}
    assert len(calls)==3


def test_persistent_status_failure_is_not_hidden(tmp_path,monkeypatch):
    calls=[]
    def replace(path,target):
        calls.append(1);raise PermissionError('synthetic persistent conflict')
    monkeypatch.setattr(Path,'replace',replace)
    monkeypatch.setattr(observer.time,'sleep',lambda _:None)
    with pytest.raises(PermissionError):observer.save_state(tmp_path/'status.json',{'fovr':7})
    assert len(calls)==10 and (tmp_path/'status.tmp').is_file()


def test_passive_reattach_requires_new_puback_not_old_total(tmp_path,monkeypatch):
    # 错过CONNECT标记时，首个累计计数不能证明链路仍活跃。
    state,_=run(tmp_path,monkeypatch,report(1)+report(2))
    assert not state.get('delivery_progress_seen')
    state,_=run(tmp_path/'later',monkeypatch,report(3)+report(4).replace(b'qos1_puback=7',b'qos1_puback=8'))
    assert state['delivery_progress_seen']


def test_peer_absence_keeps_capture_but_latched_fault_is_recorded(tmp_path,monkeypatch):
    # 对端无ACK是独立计数，不能伪称Bus-off；真正停机保留首次寄存器证据。
    data=(report(1)+b'GW PEER wait=1 losses=1 returns=0 no_ack=1 discarded=4 esr=48 tsr=9 at_ms=500\n')
    state,_=run(tmp_path,monkeypatch,data)
    assert state['peer']['wait']==1 and state['state']=='CAPTURE_COMPLETE'
    state,_=run(tmp_path/'fatal',monkeypatch,data+b'GW CAN_FAULT reason=8 esr=4 tsr=8 at_ms=600 reset=0\nGW CAN_FAULT_NETWORK_CLOSED_STOP\n')
    assert state['state']=='DEVICE_STOP' and state['fatal_can']['esr']==4
