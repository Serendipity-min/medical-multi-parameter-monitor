// 产品支持范围的静态配置，不代表运行时硬件自检结果。
import type { ScalarChannel, WaveChannel } from '../types';
import type { Route } from '../router/hashRouter';

export interface Parameter {
  route: Exclude<Route, 'overview'>;
  title: string;
  english: string;
  scalar: ScalarChannel;
  wave?: WaveChannel;
  node: 'Node-A' | 'Node-B';
  device: string;
  subtitle: string;
  facts: [string, string][];
}

export const parameters: Record<Exclude<Route, 'overview'>, Parameter> = {
  ecg: { route: 'ecg', title: '心电监测', english: 'ELECTROCARDIOGRAM', scalar: 'HR', wave: 'ECG', node: 'Node-B', device: 'ADS1292R', subtitle: '单导联 RA–LA · 250 Hz', facts: [['采集模块', 'ADS1292R'], ['采集节点', 'Node-B'], ['导联配置', 'RA / LA / RL（静态配置）'], ['采样率', '250 Hz'], ['滤波配置', '由 Node-B 固件定义'], ['电极状态', '当前协议未提供']] },
  spo2: { route: 'spo2', title: '血氧与脉率', english: 'PULSE OXIMETRY', scalar: 'SpO2', wave: 'PPG', node: 'Node-A', device: 'AFE4490', subtitle: '红光 / 红外光采集 · 50 Hz', facts: [['采集模块', 'AFE4490'], ['采集节点', 'Node-A'], ['光路配置', '红光 / 红外光'], ['PPG 采样率', '50 Hz'], ['波形单位', '相对幅值'], ['探头状态', '当前协议未提供']] },
  resp: { route: 'resp', title: '呼吸监测', english: 'IMPEDANCE RESPIRATION', scalar: 'RR', wave: 'RESP', node: 'Node-B', device: 'ADS1292R', subtitle: '阻抗呼吸 · 50 Hz · RR 算法输出', facts: [['采集模块', 'ADS1292R'], ['采集节点', 'Node-B'], ['测量方式', '阻抗呼吸'], ['采样率', '50 Hz'], ['波形单位', '相对幅值'], ['呼吸率来源', 'RR 标量 / 算法输出']] },
  nibp: { route: 'nibp', title: '无创血压', english: 'NON-INVASIVE BLOOD PRESSURE', scalar: 'NIBP', node: 'Node-A', device: 'HKB-08', subtitle: '间歇测量 · SYS / DIA', facts: [['测量模块', 'HKB-08'], ['采集节点', 'Node-A'], ['输出参数', 'SYS / DIA'], ['单位', 'mmHg'], ['测量类型', '间歇式'], ['最近测量时间', '见当前读数时间戳']] },
  temp: { route: 'temp', title: '红外体温', english: 'NON-CONTACT TEMPERATURE', scalar: 'TEMP', node: 'Node-B', device: 'MLX90614', subtitle: '非接触式额温 · GY-641 V3', facts: [['传感器', 'MLX90614 / GY-641 V3'], ['采集节点', 'Node-B'], ['接口配置', 'I²C'], ['测量方式', '非接触式额温'], ['建议距离', '1–3 cm（静态操作说明）'], ['温度来源', 'TEMP 标量']] },
};
