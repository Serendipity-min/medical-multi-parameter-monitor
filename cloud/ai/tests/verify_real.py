"""显式授权的真实小额验证，令牌只从外部环境读取；不由 Pytest/CI 自动执行。"""
import argparse
import json
import os
from pathlib import Path
import re
import uuid
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:18766')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--authorize-real-calls', action='store_true')
    args = parser.parse_args()
    if not args.authorize_real_calls or len(os.environ.get('P6_AI_TOKEN', '')) < 32:
        raise SystemExit('REAL_VALIDATION_AUTHORIZATION_REQUIRED')
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'mode': 'REAL_DOUBAO_WITH_READONLY_MONITOR', 'model_id': 'doubao-seed-2-0-mini-260428', 'cases': []}
    with httpx.Client(base_url=args.base_url, timeout=20, trust_env=False,
                      headers={'Authorization': 'Bearer ' + os.environ['P6_AI_TOKEN']}) as client:
        health = client.get('/health'); assert health.status_code == 200
        report['health_before'] = health.json()
        assert health.json()['model_mode'] == 'DOUBAO' and health.json()['snapshot_mode'] == 'MONITOR'
        scenarios = [('current_reading', 'GW-DEV-001', '现在心率多少', False),
                     ('offline_reading', 'GW-C-001', '现在心率多少', False),
                     ('general_health', 'GW-DEV-001', '工作间隙感觉疲劳，有哪些一般的健康调整建议？', True),
                     ('source_explanation', 'GW-DEV-001', '解释模拟数据、历史补传与当前读数的区别。', True)]
        for name, gateway, question, real in scenarios:
            response = client.post('/api/v1/text', json={'session_id': uuid.uuid4().hex, 'gateway_id': gateway,
                                                       'question': question, 'voice': False})
            entry = {'case': name, 'http_status': response.status_code, 'response': response.json()}
            report['cases'].append(entry)
            # 每轮先保存真实结果；失败不得改成 PASS，也不得自动重试消耗预算。
            (args.output / 'real-api.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            assert response.status_code == 200, name
            answer = entry['response']
            if real:
                assert answer['real_model'] == 'REAL_REQUEST_USED' and answer['model_evidence']['status'] == 'VALIDATED'
                assert answer['model_evidence']['reported_model'] == report['model_id']
                explanation = answer['answer'].split('\n')[-1]
                assert not re.search(r'[0-9０-９%℃°]', explanation)
            else:
                assert answer['real_model'] == 'NOT_CALLED'
                hr = next(f for f in answer['facts'] if f['stream'] == 'HR')
                if name == 'current_reading':
                    assert hr['validity'] == 'VALID' and hr['source'] == 'MOCK' and hr['synthetic']
                    assert f"{hr['value']:g} bpm" in answer['answer'] and '非真人' in answer['answer']
                else:
                    assert hr['value'] is None and hr['validity'] == 'OFFLINE' and '没有可用' in answer['answer']
            entry['result'] = 'PASS'
            print(name, 'PASS', 'REAL_REQUEST_USED' if real else 'DETERMINISTIC_NO_MODEL')
        report['health_after'] = client.get('/health').json()
    report['result'] = 'PASS'; report['exit_code'] = 0
    (args.output / 'real-api.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__': raise SystemExit(main())
