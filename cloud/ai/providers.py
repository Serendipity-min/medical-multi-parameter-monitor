"""真实豆包的一般解释：数值留在事实层，模型文字需独立核验且不能控制设备。"""
import json
import os
from pathlib import Path
import re
import time
import httpx
from .usage import UsageLedger

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
            self.ledger = UsageLedger(self.budget_dir)

    def reserve_call(self):
        # SQLite事务跨进程保留审计与限流，不再用五个独占槽限制总调用数。
        return self.ledger.reserve(self.model)

    @property
    def budget_used(self):
        return self.ledger.summary()['requests'] if self.budget_dir else 0

    async def explain(self, question: str, facts: list[dict], history: list[dict]) -> str:
        if self.mode == 'MOCK':
            return EXPLANATIONS['project' if '项目' in question else 'quality']
        number = self.reserve_call()
        self.calls += 1
        started = time.monotonic()
        evidence = {'call': number, 'requested_model': self.model, 'status': 'API_ERROR',
                    'billing_state': 'UNKNOWN_TOKEN_USAGE_RECORDED'}
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
                                                            {'role': 'user', 'content': json.dumps({'question': question, 'facts': [{k: f[k] for k in ('stream','node_id','validity','source','synthetic') if k in f} for f in facts]}, ensure_ascii=False)}]}) as response:
                    evidence['http_status'] = response.status_code
                    if response.status_code in (401,403): evidence['status'] = 'AUTH_ERROR'
                    elif response.status_code == 429: evidence['status'] = 'QUOTA_ERROR'
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 16384:
                            raise ValueError('MODEL_RESPONSE_SIZE')
                    if response.is_error:
                        try:
                            code = json.loads(raw).get('error', {}).get('code')
                            if isinstance(code,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',code):
                                evidence['error_code'] = code
                        except (ValueError, AttributeError):
                            pass
                        response.raise_for_status()
            payload = json.loads(raw)
            # 先记上游Token，即使后续事实/输出审核拒绝，也不能漏记已发生的调用。
            evidence['usage'] = {k:v for k,v in payload.get('usage',{}).items()
                if k in ('prompt_tokens','completion_tokens','total_tokens') and type(v) is int and v>=0}
            evidence['status'] = 'OUTPUT_REJECTED'
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
        except httpx.TimeoutException:
            evidence['status'] = 'TIMEOUT'; evidence['error_code'] = 'MODEL_TIMEOUT'
            raise
        except httpx.HTTPStatusError as exc:
            evidence.setdefault('error_code', 'UPSTREAM_HTTP_' + str(exc.response.status_code))
            raise
        finally:
            evidence['latency_ms'] = round((time.monotonic() - started) * 1000)
            self.last_call = dict(evidence)
            self.ledger.finish(number, evidence)
