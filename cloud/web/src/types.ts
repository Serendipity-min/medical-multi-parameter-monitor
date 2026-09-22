// 集中定义 WebSocket Snapshot v1、波形采样及视图模型数据结构。
// 前端所有模块统一引用此文件，严禁在多处分散重复定义。

export type Validity = 'VALID' | 'INVALID' | 'STALE' | 'OFFLINE';
export type SignalSource = 'LIVE' | 'MOCK' | 'REPLAY';

export interface Signal {
  node_id: string;
  stream: string;
  timestamp: number;
  seq: number;
  session_id: string;
  validity: Validity;
  source: SignalSource;
  synthetic: boolean;
  value: number | number[] | null;
  samples: number[];
  sample_rate: number;
  unit: string;
}

export interface Snapshot {
  type: 'snapshot';
  schema_version: 1;
  gateway_id: string;
  gateways?: string[];
  gateway_state: string;
  broker_connected?: boolean;
  nodes: Record<string, string>;
  server_time?: number;
  streams: Signal[];
  replay: Signal | null;
  event: { value: string } | null;
}

export interface Point {
  t: number;
  y: number;
  gap?: boolean;
}

export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'timeout'
  | 'error';

export type WaveChannel = 'ECG' | 'RESP' | 'PPG';
export type ScalarChannel = 'HR' | 'RR' | 'NIBP' | 'SpO2' | 'PR' | 'TEMP';

export interface ScalarReading {
  channel: ScalarChannel;
  rawValue: number | number[] | null;
  formatted: string;
  subFormatted?: string;
  unit: string;
  validity: Validity;
  source: SignalSource | 'OFFLINE';
  nodeId: string;
  updatedTime?: string;
}

export interface MonitorViewModel {
  waves: Record<WaveChannel, { validity: Validity; source: string }>;
  gatewayId: string;
  gatewayState: string;
  nodeAState: string;
  nodeBState: string;
  sources: string[];
  sourceBanner: string;
  sourceNote: string;
  modeText: string;
  lastUpdatedText: string;
  scalars: Record<ScalarChannel, ScalarReading>;
  replayStatus: string;
  eventStatus: string;
}
