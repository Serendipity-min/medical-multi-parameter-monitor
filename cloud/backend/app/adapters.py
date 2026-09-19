"""线协议适配层；MOCK/1 不是正式 MMP/2 字节协议。"""

import json
from .models import Frame


class MockJsonAdapter:
    def decode(self, text: str) -> Frame:
        # 包络单独校验，业务层不会依赖模拟线协议的版本字段。
        data = json.loads(text)
        if not isinstance(data, dict) or data.pop('protocol', None) != 'MOCK/1':
            raise ValueError('unsupported transport')
        return Frame.model_validate(data)
