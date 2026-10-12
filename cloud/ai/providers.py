"""模型只选经核验的解释模板；数字和单位全部来自事实层，不执行任何控制。"""
import json
import os
import httpx

EXPLANATIONS = {
    'quality': '只有有效且未过期的采集结果才能作为当前读数；模拟与补传来源应分别核对。',
    'general': '可以先休息并复测，结合实际感受观察变化；出现明显不适时请寻求医生评估。',
    'project': '本项目通过采集节点、网关和云端展示监护数据，目前属于工程样机。',
}


class Provider:
    def __init__(self, mode: str):
        if mode not in ('MOCK', 'DOUBAO'):
            raise ValueError('MODEL_MODE')
        self.mode, self.calls = mode, 0
        self.key, self.model = '', ''
        if mode == 'DOUBAO':
            # 真实调用必须在服务器进程中显式配置账户/预算门禁，默认不读取或输出密钥。
            self.key = os.environ.get('ARK_API_KEY', '')
            self.model = os.environ.get('ARK_MODEL_ID', '')
            if not self.key or not self.model or os.environ.get('P6_REAL_ACCOUNT_APPROVED') != '1' or os.environ.get('P6_REAL_BUDGET_APPROVED') != '1':
                raise ValueError('REAL_MODEL_BLOCKED')

    async def explain(self, question: str, facts: list[dict], history: list[dict]) -> str:
        if self.mode == 'MOCK':
            return EXPLANATIONS['project' if '项目' in question else 'quality']
        if self.calls >= 5:
            raise ValueError('REAL_MODEL_CALL_LIMIT')
        self.calls += 1
        # 模型只接收已归属/有效性核验的标量事实，不发送波形、身份或服务器凭据。
        async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
            async with client.stream('POST', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                                     headers={'Authorization': f'Bearer {self.key}'},
                                     json={'model': self.model, 'stream': False, 'max_tokens': 64,
                                           'messages': [{'role': 'system', 'content': '仅选择解释类别，返回 JSON {"kind":"quality|general|project"}。禁止诊断、处方、药量、治疗或设备控制。'},
                                                        {'role': 'user', 'content': json.dumps({'question': question, 'facts': facts, 'history': history}, ensure_ascii=False)}]}) as response:
                response.raise_for_status()
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 16384:
                        raise ValueError('MODEL_RESPONSE_SIZE')
        parsed = json.loads(json.loads(raw)['choices'][0]['message']['content'])
        # 独立白名单将模型文字限制为已审查模板；未知结构/数值/诊疗内容均拒绝。
        if set(parsed) != {'kind'} or parsed['kind'] not in EXPLANATIONS:
            raise ValueError('MODEL_OUTPUT_REJECTED')
        return EXPLANATIONS[parsed['kind']]
