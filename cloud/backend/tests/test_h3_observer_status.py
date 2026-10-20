"""并发只读观测不得争用状态临时文件，也不能混淆各自结果。"""
from concurrent.futures import ThreadPoolExecutor
import json
import copy
import pytest
from cloud.deploy.h3 import e2e_observer as observer


def test_concurrent_observers_have_independent_atomic_status(tmp_path,monkeypatch):
    monkeypatch.setattr(observer,'STATE',tmp_path)
    directories=[tmp_path/'first',tmp_path/'second']
    for directory in directories:directory.mkdir()
    def write(index):
        # 两个观测会话各自递增合成计数，不允许写同一个全局状态文件。
        for count in range(30):observer.save_status({'run':index,'count':count},directories[index])
    with ThreadPoolExecutor(max_workers=2) as executor:list(executor.map(write,range(2)))
    for index,directory in enumerate(directories):
        assert json.loads((directory/'status.json').read_text())=={'run':index,'count':29}
    assert not (tmp_path/'e2e-status.json').exists()
    assert not list(tmp_path.rglob('*.tmp'))


def active_snapshot():
    # 纯合成波形仅用于门禁逻辑；故意使标量INVALID，验证不会把源质量当作断链。
    return {'gateway_state':'ONLINE','nodes':{'NODE-A':'ONLINE','NODE-B':'OFFLINE'},'server_time':10000,
            'streams':[{'stream':'PPG','timestamp':9800,'validity':'VALID','source':'MOCK',
                        'synthetic':True,'samples':[1,2]},
                       {'stream':'SPO2','validity':'INVALID','value':None}]}


def test_active_ppg_does_not_falsify_invalid_scalar():
    snapshot=active_snapshot();before=copy.deepcopy(snapshot)
    assert observer.active_ppg(snapshot)
    assert snapshot==before


@pytest.mark.parametrize('change', ['stale','future','empty','offline_a','absent_b','online_b','replay','invalid'])
def test_active_ppg_rejects_idle_old_or_wrong_source(change):
    snapshot=active_snapshot();ppg=snapshot['streams'][0]
    if change=='stale':ppg['timestamp']=4999
    elif change=='future':ppg['timestamp']=10001
    elif change=='empty':ppg['samples']=[]
    elif change=='offline_a':snapshot['nodes']['NODE-A']='OFFLINE'
    elif change=='absent_b':del snapshot['nodes']['NODE-B']
    elif change=='online_b':snapshot['nodes']['NODE-B']='ONLINE'
    elif change=='replay':ppg['source']='REPLAY'
    elif change=='invalid':ppg['validity']='INVALID'
    assert not observer.active_ppg(snapshot)
