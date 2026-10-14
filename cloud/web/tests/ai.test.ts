// 回执语义和跨网关边界的普通回归；测试只使用合成对象，不访问云端。
import assert from 'node:assert/strict';
import test from 'node:test';
import { modelLabel, validResponse, voiceLabels, type AiResponse } from '../src/ui/aiResponse';
const response = (): AiResponse => ({ gateway_id: 'GW-DEV-001', session_id: 'test', turn_id: 'turn', fact_digest: 'digest',
  answer: '<img src=x onerror=alert(1)>', model_mode: 'REAL', real_model: 'NOT_CALLED', voice_status: 'PAUSED', facts: [{
    label: '心率', node_id: 'NODE-B', validity: 'VALID', source: 'MOCK', synthetic: true,
    timestamp: 1, session_id: 'sample', seq: 1, value: 77, unit: 'bpm',
  }] });
test('确定性回答不被 REAL 模式误标为豆包调用', () => {
  assert.equal(modelLabel(response()), '监护事实核对 · 本轮未调用模型');
  assert.equal(modelLabel({ ...response(), real_model: 'REAL_REQUEST_USED' }), '本轮使用豆包');
  assert.equal(modelLabel({ ...response(), model_mode: 'MOCK', real_model: 'REAL_REQUEST_USED' }), 'MOCK · 模拟回答');
});
test('记录回放优先标记历史，不能冒充本轮调用', () => {
  const data = response(); data.real_model = 'REAL_REQUEST_USED'; data.facts[0].source = 'REPLAY';
  assert.match(modelLabel(data), /历史回答回放.*未调用模型/);
});
test('回执严格匹配网关和会话，拒绝畸形事实', () => {
  const data = response(); assert.ok(validResponse(data, 'GW-DEV-001', 'test'));
  assert.equal(validResponse(data, 'GW-C-001', 'test'), false);
  assert.equal(validResponse(data, 'GW-DEV-001', 'other'), false);
  for (const malformed of [null, { ...data, facts: [null] }, { ...data, facts: [{}] }, { ...data, answer: 123 }, { ...data, voice_status: null }]) {
    assert.equal(validResponse(malformed, 'GW-DEV-001', 'test'), false);
  }
});
test('五种播报语义完整，Broker 回执明确设备播放未验证', () => {
  assert.equal(Object.keys(voiceLabels).length, 5);
  assert.match(voiceLabels.BROKER_PUBACK_ONLY, /设备播放未验证/);
  assert.ok(Object.values(voiceLabels).every((label) => !label.includes('已播放')));
});
