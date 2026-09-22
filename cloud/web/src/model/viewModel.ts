// 纯函数转换层：将后端快照数据转化为 UI 展现所需的 ViewModel。
// 无测量值或非 VALID 时显示 '--'；波形与算法标量分别判定，不推断探头状态。

import type { MonitorViewModel, ScalarChannel, ScalarReading, Signal, Snapshot } from '../types';

const defaultUnits: Record<ScalarChannel, string> = {
  HR: 'bpm',
  RR: '次/分',
  NIBP: 'mmHg',
  SpO2: '%',
  PR: 'bpm',
  TEMP: '°C',
};

export function toMonitorViewModel(data: Snapshot): MonitorViewModel {
  const sources = [...new Set(data.streams.map((signal) => signal.source))];
  const latestTimestamp = Math.max(0, ...data.streams.map((signal) => signal.timestamp));

  const signals = new Map<string, Signal>(
    data.streams.map((signal) => [signal.stream === 'SPO2' ? 'SpO2' : signal.stream, signal]),
  );

  const formatScalar = (channel: ScalarChannel): ScalarReading => {
    const signal = signals.get(channel) ?? null;
    const valid = signal?.validity === 'VALID' && signal.source !== 'REPLAY';
    const value = signal?.value ?? null;
    const unit = defaultUnits[channel];
    const source = signal ? signal.source : 'OFFLINE';
    const nodeId = signal ? signal.node_id : '';

    if (channel === 'NIBP') {
      const isArray = Array.isArray(value) && value.length >= 2 && value.slice(0, 2).every(Number.isFinite);
      return {
        channel,
        rawValue: value,
        formatted: valid && isArray ? String(Math.round(value[0])) : '--',
        subFormatted: valid && isArray ? String(Math.round(value[1])) : '--',
        unit,
        validity: signal?.validity ?? 'OFFLINE',
        source,
        nodeId: nodeId || 'Node-A',
        updatedTime: valid && signal ? new Date(signal.timestamp).toLocaleTimeString('zh-CN', { hour12: false }) : '—',
      };
    }

    let formatted = '--';
    if (valid && typeof value === 'number' && Number.isFinite(value)) {
      formatted = channel === 'TEMP' ? value.toFixed(1) : String(Math.round(value));
    }

    return {
      channel,
      rawValue: value,
      formatted,
      unit,
      validity: signal?.validity ?? 'OFFLINE',
      source,
      nodeId: nodeId || (channel === 'SpO2' || channel === 'PR' ? 'Node-A' : 'Node-B'),
      updatedTime: signal ? new Date(signal.timestamp).toLocaleTimeString('zh-CN', { hour12: false }) : '--',
    };
  };

  const scalars: Record<ScalarChannel, ScalarReading> = {
    HR: formatScalar('HR'),
    RR: formatScalar('RR'),
    NIBP: formatScalar('NIBP'),
    SpO2: formatScalar('SpO2'),
    PR: formatScalar('PR'),
    TEMP: formatScalar('TEMP'),
  };

  const sourceBanner = sources.includes('MOCK')
    ? 'MOCK 模拟数据'
    : sources.join(' / ') || '等待数据源';

  const sourceNote = sources.includes('MOCK')
    ? '含合成数据，用于系统联调'
    : '来源和有效性见各参数标签';

  const lastUpdatedText = latestTimestamp
    ? `最后采集时间：${new Date(latestTimestamp).toLocaleString('zh-CN', { hour12: false })}`
    : '最后采集时间：—';

  const replayStatus = data.replay
    ? `${data.replay.stream} #${data.replay.seq} · ${new Date(data.replay.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}${data.replay.synthetic ? ' · 模拟补传' : ''}`
    : '尚未收到补传';

  const eventStatus = data.event ? `事件：${data.event.value}` : '无事件';

  return {
    waves: Object.fromEntries(['ECG', 'RESP', 'PPG'].map((name) => {
      const signal = signals.get(name);
      return [name, { validity: signal?.source === 'REPLAY' ? 'STALE' : signal?.validity ?? 'OFFLINE', source: signal?.source ?? 'OFFLINE' }];
    })) as MonitorViewModel['waves'],
    gatewayId: data.gateway_id,
    gatewayState: data.gateway_state || 'OFFLINE',
    nodeAState: data.nodes['NODE-A'] || 'OFFLINE',
    nodeBState: data.nodes['NODE-B'] || 'OFFLINE',
    sources,
    sourceBanner,
    sourceNote,
    modeText: `${data.gateway_state} · ${sources.join(' / ') || '等待数据'}`,
    lastUpdatedText,
    scalars,
    replayStatus,
    eventStatus,
  };
}

export function getEmptyViewModel(reason = '等待数据'): MonitorViewModel {
  const createEmptyScalar = (channel: ScalarChannel): ScalarReading => ({
    channel,
    rawValue: null,
    formatted: '--',
    subFormatted: channel === 'NIBP' ? '--' : undefined,
    unit: defaultUnits[channel],
    validity: 'STALE',
    source: 'OFFLINE',
    nodeId: channel === 'NIBP' || channel === 'SpO2' || channel === 'PR' ? 'Node-A' : 'Node-B',
    updatedTime: '—',
  });

  return {
    waves: { ECG: { validity: 'STALE', source: 'OFFLINE' }, RESP: { validity: 'STALE', source: 'OFFLINE' }, PPG: { validity: 'STALE', source: 'OFFLINE' } },
    gatewayId: 'GW-DEV-001',
    gatewayState: 'OFFLINE',
    nodeAState: 'OFFLINE',
    nodeBState: 'OFFLINE',
    sources: [],
    sourceBanner: '等待数据源',
    sourceNote: '暂无有效数据',
    modeText: reason,
    lastUpdatedText: '最后采集时间：—',
    scalars: {
      HR: createEmptyScalar('HR'),
      RR: createEmptyScalar('RR'),
      NIBP: createEmptyScalar('NIBP'),
      SpO2: createEmptyScalar('SpO2'),
      PR: createEmptyScalar('PR'),
      TEMP: createEmptyScalar('TEMP'),
    },
    replayStatus: '尚未收到补传',
    eventStatus: '无事件',
  };
}
