"""并发只读观测不得争用状态临时文件，也不能混淆各自结果。"""
from concurrent.futures import ThreadPoolExecutor
import json
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
