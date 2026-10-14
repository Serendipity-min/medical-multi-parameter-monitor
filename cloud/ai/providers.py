"""真实豆包的一般解释：数值留在事实层，模型文字需独立核验且不能控制设备。"""
import json
import os
from pathlib import Path
import re
import time
import httpx

EXPLANATIONS = {
    'quality': '只有有效且未过期的采集结果才能作为当前读数；模拟与补传来源应分别核对。',
    'general': '可以先休息并复测，结合实际感受观察变化；出现明显不适时请寻求医生评估。',
    'project': '本项目通过采集节点、网关和云端展示监护数据，目前属于工程样机。',
}


class ValidatedExplanation(str):
    # 每轮携带自己的请求证据，不能在并发时从 provider 的全局 last_call 串用另一轮信息。
    def __new__(cls, text: str, evidence: dict):
        instance = super().__new__(cls, text)
        instance.evidence = dict(evidence)
        return instance


def validate_explanation(parsed: dict) -> str:
    if not isinstance(parsed, dict) or set(parsed) != {'kind', 'explanation'} or parsed['kind'] not in EXPLANATIONS:
        raise ValueError('MODEL_OUTPUT_REJECTED')
    text = parsed['explanation']
    if not isinstance(text, str) or not 1 <= len(text) <= 600:
        raise ValueError('MODEL_OUTPUT_REJECTED')
    # 模型不复述数值/单位，避免把测量值或参考阈值混入当前事实；禁止药量/治疗指令和标签。
    if any(ord(c) < 32 or 0x7f <= ord(c) <= 0x9f or c in '[]<>'
           or 0x200b <= ord(c) <= 0x200f or 0x2028 <= ord(c) <= 0x202e
           or 0x2060 <= ord(c) <= 0x206f or ord(c) >= 0xfffe for c in text):
        raise ValueError('MODEL_OUTPUT_REJECTED')
    if re.search(r'[0-9０-９%℃°]|\b(?:bpm|mmhg|mg|ml)\b|https?://|Bearer\s|ark-[a-f0-9-]+', text, re.I):
        raise ValueError('MODEL_OUTPUT_REJECTED')
    if re.search(r'确诊|诊断为|患有|建议服|应该服|需要服|口服|注射|用药|药量|剂量|处方|治疗方案|停药|加药|减药|百分之|毫克|毫升|(?:您的|你的|当前|此次).{0,12}(?:正常|异常|偏高|偏低)|[零〇一二两三四五六七八九十百千万亿]+(?:次|天|小时|分钟|秒|片|粒|杯|度|岁|步)|(?:心率|脉率|血氧|呼吸率|体温|血压|读数|数值).{0,3}[零〇一二两三四五六七八九十百千万亿]{2,}', text):
        raise ValueError('MODEL_OUTPUT_REJECTED')
    return text


class Provider:
    def __init__(self, mode: str):
        if mode not in ('MOCK', 'DOUBAO'):
            raise ValueError('MODEL_MODE')
        self.mode, self.calls = mode, 0
        self.key, self.model = '', ''
        self.last_call = None
        self.budget_dir = None
        if mode == 'DOUBAO':
            # 真实调用必须在服务器进程中显式配置账户/预算门禁，默认不读取或输出密钥。
            self.key = os.environ.get('ARK_API_KEY', '')
            self.model = os.environ.get('ARK_MODEL_ID', '')
            if not self.key or not self.model or os.environ.get('P6_REAL_ACCOUNT_APPROVED') != '1' or os.environ.get('P6_REAL_BUDGET_APPROVED') != '1':
                raise ValueError('REAL_MODEL_BLOCKED')
            budget = os.environ.get('P6_REAL_BUDGET_DIR', '')
            if not budget or not Path(budget).is_dir():
                raise ValueError('REAL_MODEL_BUDGET_CONFIG')
            self.budget_dir = Path(budget)

    def reserve_call(self):
        # 跨进程/重启共享五个独占槽。失败也消耗一次预算，绝不自动重试或重启补满次数。
        for number in range(1, 6):
            path = self.budget_dir / f'call-{number:02d}.json'
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump({'call': number, 'model': self.model, 'status': 'RESERVED'}, stream)
            return number, path
        raise ValueError('REAL_MODEL_CALL_LIMIT')

    @property
    def budget_used(self):
        return sum((self.budget_dir / f'call-{n:02d}.json').exists() for n in range(1, 6)) if self.budget_dir else 0

    async def explain(self, question: str, facts: list[dict], history: list[dict]) -> str:
        if self.mode == 'MOCK':
            return EXPLANATIONS['project' if '项目' in question else 'quality']
        if self.calls >= 5:
            raise ValueError('REAL_MODEL_CALL_LIMIT')
        number, slot = self.reserve_call()
        self.calls += 1
        started = time.monotonic()
        evidence = {'call': number, 'requested_model': self.model, 'status': 'API_ERROR'}
        prompt = ('你是工程监护样机的文字解释助手。仅提供一般健康提示、数据来源解释或项目知识，不做临床诊断、处方、药量或治疗指令。'
                  '只返回 JSON 对象，字段 kind 为 quality/general/project 之一，explanation 为自然中文短回答。'
                  '不要复述任何数字、单位、阈值、服药或治疗；监护读数由服务端独立显示。不要把 MOCK、synthetic、REPLAY 当真人当前数据，'
                  '也不要判断当前读数正常、异常、偏高或偏低。可建议休息、复测、在明显不适时寻求医生评估。'
                  '回答需针对问题，最多三句，不含换行、链接、标签或控制字符。')
        # 模型只接收已归属/有效性核验的标量事实，不发送波形、身份或服务器凭据。
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                async with client.stream('POST', 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                                         headers={'Authorization': f'Bearer {self.key}'},
                                         json={'model': self.model, 'stream': False, 'max_tokens': 256,
                                               'thinking': {'type': 'disabled'}, 'response_format': {'type': 'json_object'},
                                               'messages': [{'role': 'system', 'content': prompt},
                                                            {'role': 'user', 'content': json.dumps({'question': question, 'facts': facts, 'history': history}, ensure_ascii=False)}]}) as response:
                    response.raise_for_status()
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 16384:
                            raise ValueError('MODEL_RESPONSE_SIZE')
            payload = json.loads(raw)
            choice = payload['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('MODEL_RESPONSE_INCOMPLETE')
            text = validate_explanation(json.loads(choice['message']['content']))
            usage = payload.get('usage', {})
            evidence.update(status='VALIDATED', http_status=200, reported_model=payload.get('model'),
                            request_id=payload.get('id'), finish_reason=choice['finish_reason'],
                            latency_ms=round((time.monotonic() - started) * 1000),
                            usage={k: v for k, v in usage.items() if k in ('prompt_tokens', 'completion_tokens', 'total_tokens') and type(v) is int and v >= 0})
            return ValidatedExplanation(text, evidence)
        finally:
            evidence['latency_ms'] = round((time.monotonic() - started) * 1000)
            self.last_call = dict(evidence)
            slot.write_text(json.dumps(evidence), encoding='utf-8')
