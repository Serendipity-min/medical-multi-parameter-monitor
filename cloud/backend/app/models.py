"""MQTT 与浏览器共用的内部数据语义；时间戳统一为毫秒。"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

CHANNELS = {'NODE-A': {'PPG', 'SPO2', 'PR', 'NIBP'}, 'NODE-B': {'ECG', 'HR', 'RESP', 'RR', 'TEMP'}}
WAVES = {'ECG', 'PPG', 'RESP'}
UNITS = {'ECG': 'mV', 'PPG': 'relative', 'RESP': 'relative', 'SPO2': '%', 'HR': 'bpm',
         'PR': 'bpm', 'RR': 'breaths/min', 'TEMP': 'degC', 'NIBP': 'mmHg',
         'NODE_STATUS': 'state', 'GATEWAY_STATUS': 'state', 'FAULT': 'code'}

class Telemetry(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)
    gateway_id: str = Field(pattern=r'^[A-Za-z0-9-]{1,40}$')
    node_id: str = Field(pattern=r'^(NODE-A|NODE-B|GATEWAY)$')
    stream: str
    timestamp: int = Field(gt=0, le=2**53-1)
    seq: int = Field(ge=0, le=2**53-1)
    session_id: str = Field(pattern=r'^[A-Za-z0-9-]{1,64}$')
    validity: Literal['VALID', 'INVALID', 'STALE', 'OFFLINE']
    source: Literal['LIVE', 'REPLAY', 'MOCK']
    synthetic: bool = False
    value: float | list[float] | str | None = None
    samples: list[float] = Field(default_factory=list, max_length=500)
    sample_rate: int = Field(default=0, ge=0, le=1000)
    unit: str

    @model_validator(mode='after')
    def validate_stream(self):
        if self.stream not in UNITS or self.unit != UNITS[self.stream]:
            raise ValueError('unknown stream or unit')
        if self.source == 'MOCK' and not self.synthetic:
            raise ValueError('mock must be synthetic')
        if self.synthetic and self.source == 'LIVE':
            raise ValueError('synthetic data cannot be LIVE')
        if self.stream in {'GATEWAY_STATUS', 'NODE_STATUS'}:
            expected = 'GATEWAY_STATUS' if self.node_id == 'GATEWAY' else 'NODE_STATUS'
            if self.stream != expected or self.source == 'REPLAY' or self.value not in ('ONLINE', 'OFFLINE'):
                raise ValueError('invalid status')
        elif self.stream == 'FAULT':
            if self.node_id == 'GATEWAY' or not isinstance(self.value, str) or len(self.value) > 160:
                raise ValueError('invalid event')
        elif self.stream not in CHANNELS.get(self.node_id, set()):
            raise ValueError('node stream mismatch')
        if self.stream in WAVES:
            if self.value is not None or not self.sample_rate or (self.validity == 'VALID' and not self.samples):
                raise ValueError('invalid waveform')
        else:
            if self.samples or self.sample_rate:
                raise ValueError('scalar cannot have samples')
            if self.validity == 'VALID' and self.stream in set().union(*CHANNELS.values()):
                if self.stream == 'NIBP':
                    if not isinstance(self.value, list) or len(self.value) != 2:
                        raise ValueError('NIBP requires SYS and DIA')
                elif not isinstance(self.value, float):
                    raise ValueError('scalar requires numeric value')
        return self
