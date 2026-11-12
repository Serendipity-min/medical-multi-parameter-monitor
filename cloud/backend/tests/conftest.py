import pytest


@pytest.fixture
def monitor_snapshot():
    def snapshot(client, hello):
        with client.websocket_connect('/ws/v1/monitor', headers={'origin': 'http://testserver'}) as ws:
            ws.send_json(hello)
            data = ws.receive_json()
            # 等服务端清理订阅并发送关闭帧，再退出 TestClient 的取消作用域。
            ws.close()
            while ws.receive()['type'] == 'websocket.send':
                pass
        return data
    return snapshot
