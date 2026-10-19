// 回执展示只依据本轮字段；MOCK、历史回放和未调用模型不能标为真实生成。
export interface AiFact {
  label: string; node_id: string; validity: string; source: string; synthetic: boolean;
  timestamp: number; session_id: string; seq: number; value: number | number[] | null; unit: string;
}
export interface AiResponse {
  gateway_id: string; session_id: string; turn_id: string; fact_digest: string;
  answer: string; facts: AiFact[]; model_mode: string; real_model: string; voice_status: string;
  model_evidence?: { requested_model?: string; reported_model?: string; status?: string } | null;
}
export const voiceLabels: Record<string, string> = {
  PAUSED: '设备播报已暂停', DISABLED: '设备播报服务未启用',
  BROKER_PUBACK_ONLY: 'Broker 已接收下发 · 设备播放未验证',
  RATE_LIMITED: '播报频率受限', DOWNLINK_FAILED: '播报下发失败',
};
export function modelLabel(data: AiResponse): string {
  if (data.facts.some((fact) => fact.source === 'REPLAY')) return '历史回答回放 · 本轮未调用模型';
  if (data.model_mode === 'MOCK') return 'MOCK · 模拟回答';
  return data.real_model === 'REAL_REQUEST_USED' ? '本轮使用豆包' : '监护事实核对 · 本轮未调用模型';
}
export function validResponse(data: unknown, gateway: string, session: string): data is AiResponse {
  // 错网关/错会话及畸形事实一律拒绝，不进入聊天或覆盖状态标签。
  if (!data || typeof data !== 'object') return false;
  const d = data as AiResponse;
  return d.gateway_id === gateway && d.session_id === session && typeof d.answer === 'string'
    && ['turn_id', 'fact_digest', 'model_mode', 'real_model', 'voice_status'].every((key) => typeof (d as unknown as Record<string, unknown>)[key] === 'string')
    && Array.isArray(d.facts) && d.facts.every((f) => f && ['label', 'node_id', 'validity', 'source', 'session_id', 'unit'].every((key) => typeof (f as unknown as Record<string, unknown>)[key] === 'string')
      && Number.isFinite(f.timestamp) && Number.isFinite(f.seq) && typeof f.synthetic === 'boolean');
}
