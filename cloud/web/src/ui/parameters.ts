// 产品支持范围的静态配置，不代表运行时硬件自检结果。
import type { ScalarChannel, WaveChannel } from '../types';
import { fiveAppliance } from '../gatewayProfile';

export type ParameterKey = 'ecg' | 'spo2' | 'resp' | 'nibp' | 'temp';

export interface Parameter {
  title: string;
  scalar: ScalarChannel;
  wave?: WaveChannel;
  node: 'Node-A' | 'Node-B' | 'Node-D' | 'Node-E';
  device: string;
  facts: [string, string][];
}

export const parameters: Record<ParameterKey, Parameter> = {
  ecg: { title: '心电', scalar: 'HR', wave: 'ECG', node: 'Node-B', device: 'ADS1292R', facts: [['采集模块', 'ADS1292R'], ['采集节点', 'Node-B'], ['导联', 'RA–LA 单导联'], ['采样率', '250 Hz']] },
  spo2: { title: '血氧', scalar: 'SpO2', wave: 'PPG', node: 'Node-A', device: 'AFE4490', facts: [['采集模块', 'AFE4490'], ['采集节点', 'Node-A'], ['光路', '红光 / 红外光'], ['采样率', '50 Hz']] },
  resp: { title: '呼吸', scalar: 'RR', wave: 'RESP', node: 'Node-B', device: 'ADS1292R', facts: [['采集模块', 'ADS1292R'], ['采集节点', 'Node-B'], ['方式', '阻抗呼吸'], ['采样率', '50 Hz']] },
  nibp: { title: '无创血压', scalar: 'NIBP', node: 'Node-A', device: 'HKB-08B+', facts: [['测量模块', 'HKB-08B+'], ['采集节点', 'Node-A'], ['方式', '示波法 · 间歇测量'], ['单位', 'mmHg']] },
  temp: { title: '体表温度', scalar: 'TEMP', node: 'Node-B', device: 'GY641', facts: [['传感器', 'GY641 红外'], ['采集节点', 'Node-B'], ['测量对象', '体表温度（非体温）'], ['标定', '绝对精度未标定']] },
};
if (fiveAppliance) {
  for (const [key, node] of [['temp', 'Node-D'], ['nibp', 'Node-E']] as const) {
    parameters[key].node = node;
    parameters[key].facts = parameters[key].facts.map(([name, value]) => [name, name === '采集节点' ? node : value]);
  }
}

// 趋势页按参数逐一查看；颜色与监护主界面同一通道一致。
export interface TrendChannel {
  channel: ScalarChannel;
  label: string;
  unit: string;
  color: string;
}

export const CHANNEL_COLORS: Record<ScalarChannel, string> = {
  HR: '#2ee66b', PR: '#24d3f2', SpO2: '#24d3f2', RR: '#ffd23f', NIBP: '#f2f2f2', TEMP: '#e8e8e8',
};

export const trendChannels: TrendChannel[] = [
  { channel: 'HR', label: '心率 HR', unit: 'bpm', color: CHANNEL_COLORS.HR },
  { channel: 'SpO2', label: '血氧 SpO₂', unit: '%', color: CHANNEL_COLORS.SpO2 },
  { channel: 'PR', label: '脉率 PR', unit: 'bpm', color: CHANNEL_COLORS.PR },
  { channel: 'RR', label: '呼吸率 RR', unit: 'rpm', color: CHANNEL_COLORS.RR },
  { channel: 'NIBP', label: '无创血压 NIBP', unit: 'mmHg', color: CHANNEL_COLORS.NIBP },
  { channel: 'TEMP', label: '体表温度 T', unit: '°C', color: CHANNEL_COLORS.TEMP },
];
