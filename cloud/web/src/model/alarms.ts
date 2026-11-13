// 本地显示报警：按一般成人默认限值判定，仅作界面提示，不替代设备报警或临床判断。
// 优先级与颜色沿用 IEC 60601-1-8 习惯：高=红、中=黄、低=青。

import type { MonitorViewModel, ScalarChannel } from '../types';

export type AlarmPriority = 'high' | 'medium' | 'low';

export interface Alarm {
  id: string;
  priority: AlarmPriority;
  text: string;
  channel?: ScalarChannel;
  technical: boolean;
}

export interface AlarmLimit {
  low: number;
  high: number;
}

// 体表温度不是体温，不设生理报警；RR 在当前工装下无有效值，仅显示不报警。
export const ADULT_LIMITS: Partial<Record<ScalarChannel, AlarmLimit>> = {
  HR: { low: 50, high: 120 },
  SpO2: { low: 90, high: 101 },
  PR: { low: 50, high: 120 },
  RR: { low: 8, high: 30 },
};
export const NIBP_LIMITS = { sys: { low: 90, high: 160 }, dia: { low: 50, high: 90 } };

// 连续参数越限需持续 10 s 才报警，吸收单帧离群值（R44 §2：SpO₂ 存在零散越界）。
export const ALARM_DELAY_MS = 10_000;

const ORDER: Record<AlarmPriority, number> = { high: 0, medium: 1, low: 2 };
const LABEL: Partial<Record<ScalarChannel, string>> = { HR: '心率', SpO2: 'SpO₂', PR: '脉率', RR: '呼吸率' };

interface Condition {
  id: string;
  priority: AlarmPriority;
  text: string;
  channel?: ScalarChannel;
  technical: boolean;
  delayed: boolean;
}

export class AlarmMonitor {
  private onset = new Map<string, number>();

  public evaluate(vm: MonitorViewModel, connected: boolean, linkExpected: boolean, now: number): Alarm[] {
    const conditions: Condition[] = [];
    const numeric = (channel: ScalarChannel): number | null => {
      const reading = vm.scalars[channel];
      return reading.validity === 'VALID' && typeof reading.rawValue === 'number' && Number.isFinite(reading.rawValue)
        ? reading.rawValue : null;
    };

    for (const channel of ['HR', 'SpO2', 'PR', 'RR'] as ScalarChannel[]) {
      const value = numeric(channel);
      const limit = ADULT_LIMITS[channel]!;
      if (value === null) continue;
      if (value < limit.low) {
        const severe = channel === 'SpO2' ? value < 85 : channel === 'HR' || channel === 'PR' ? value < 40 : value < 6;
        conditions.push({ id: `${channel}-low`, priority: severe ? 'high' : 'medium', text: `${LABEL[channel]}过低`, channel, technical: false, delayed: true });
      } else if (value > limit.high) {
        const severe = channel === 'HR' || channel === 'PR' ? value > 150 : channel === 'RR' && value > 40;
        conditions.push({ id: `${channel}-high`, priority: severe ? 'high' : 'medium', text: `${LABEL[channel]}过高`, channel, technical: false, delayed: true });
      }
    }

    // NIBP 是离散测量，结果有效即按本次测量判定，不加延时。
    const nibp = vm.scalars.NIBP;
    if (nibp.validity === 'VALID' && Array.isArray(nibp.rawValue) && nibp.rawValue.length >= 2) {
      const [sys, dia] = nibp.rawValue;
      if (sys > NIBP_LIMITS.sys.high || dia > NIBP_LIMITS.dia.high) {
        conditions.push({ id: 'NIBP-high', priority: 'medium', text: '血压偏高', channel: 'NIBP', technical: false, delayed: false });
      } else if (sys < NIBP_LIMITS.sys.low || dia < NIBP_LIMITS.dia.low) {
        conditions.push({ id: 'NIBP-low', priority: 'medium', text: '血压偏低', channel: 'NIBP', technical: false, delayed: false });
      }
    }

    if (linkExpected && !connected) {
      conditions.push({ id: 'link', priority: 'medium', text: '监护通道断开', technical: true, delayed: false });
    } else if (connected) {
      if (vm.gatewayState !== 'ONLINE') {
        conditions.push({ id: 'gateway', priority: 'low', text: '采集网关离线', technical: true, delayed: false });
      } else {
        if (vm.waves.ECG.validity !== 'VALID') conditions.push({ id: 'ecg-signal', priority: 'low', text: 'ECG 信号无效', technical: true, delayed: false });
        if (vm.waves.PPG.validity !== 'VALID') conditions.push({ id: 'spo2-signal', priority: 'low', text: 'SpO₂ 信号无效', technical: true, delayed: false });
      }
    }

    const active = new Set(conditions.map((item) => item.id));
    for (const id of [...this.onset.keys()]) if (!active.has(id)) this.onset.delete(id);
    const alarms: Alarm[] = [];
    for (const item of conditions) {
      if (!this.onset.has(item.id)) this.onset.set(item.id, now);
      if (item.delayed && now - this.onset.get(item.id)! < ALARM_DELAY_MS) continue;
      alarms.push({ id: item.id, priority: item.priority, text: item.text, channel: item.channel, technical: item.technical });
    }
    return alarms.sort((a, b) => ORDER[a.priority] - ORDER[b.priority]);
  }

  public reset(): void {
    this.onset.clear();
  }
}

export function highestPriority(alarms: readonly Alarm[]): AlarmPriority | 'none' {
  return alarms[0]?.priority ?? 'none';
}
