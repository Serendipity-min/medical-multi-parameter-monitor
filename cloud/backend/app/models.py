"""内部语义模型：未来 MMP2Adapter 只需产出同一 Frame。"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Quality = Literal['VALID', 'INVALID', 'STALE']
CHANNELS = {'NODE-A': {'PPG', 'SpO2', 'PR', 'NIBP'},
            'NODE-B': {'ECG', 'HR', 'RESP', 'RR', 'TEMP'}}
WAVES = {'ECG', 'PPG', 'RESP'}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)


class Signal(StrictModel):
    quality: Quality
    value: float | list[float] | None = None
    samples: list[float] = Field(default_factory=list, max_length=500)
    sample_rate: int = Field(default=0, ge=0, le=1000)


class Node(StrictModel):
    online: bool
    signals: dict[str, Signal]


class Frame(StrictModel):
    gateway_id: str = Field(pattern=r'^[A-Z0-9-]{1,40}$')
    session_id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,64}$')
    seq: int = Field(ge=0, le=2**53-1)
    mode: Literal['LIVE', 'REPLAY']
    captured_at: float = Field(gt=0)
    simulation: Literal[True]
    nodes: dict[str, Node]

    @model_validator(mode='after')
    def check_channels(self):
        # 第一阶段只有两个固定节点；完整快照避免遗漏字段残留旧正常值。
        if set(self.nodes) != set(CHANNELS):
            raise ValueError('node set mismatch')
        for node_id, node in self.nodes.items():
            if set(node.signals) != CHANNELS[node_id]:
                raise ValueError('channel set mismatch')
            for name, signal in node.signals.items():
                if name in WAVES:
                    if signal.value is not None or not signal.sample_rate:
                        raise ValueError('wave schema mismatch')
                    if signal.quality == 'VALID' and node.online and not signal.samples:
                        raise ValueError('valid wave is empty')
                else:
                    if signal.samples or signal.sample_rate:
                        raise ValueError('scalar schema mismatch')
                    if signal.quality == 'VALID' and node.online:
                        if name == 'NIBP':
                            if not isinstance(signal.value, list) or len(signal.value) != 2:
                                raise ValueError('NIBP requires SYS and DIA')
                        elif not isinstance(signal.value, float):
                            raise ValueError('scalar requires numeric value')
        return self
