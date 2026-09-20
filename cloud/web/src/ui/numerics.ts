// 体征数值与状态面板组件：集中管理 HR / SpO2 / PR / RR / NIBP / TEMP 数值渲染及异常状态提示。

import type { MonitorViewModel, ScalarChannel } from '../types';

export class NumericsView {
  private getEl(id: string): HTMLElement | null {
    return document.getElementById(id);
  }

  private setText(id: string, text: string): void {
    const el = this.getEl(id);
    if (el) el.textContent = text;
  }

  public update(vm: MonitorViewModel): void {
    // 1. HR 心率
    const hr = vm.scalars.HR;
    this.setText('value-HR', hr.formatted);
    this.setText('state-HR', `${hr.validity} · ${hr.source}`);

    // 2. SpO2 血氧 & PR 脉率
    const spo2 = vm.scalars.SpO2;
    this.setText('value-SpO2', spo2.formatted);
    this.setText('state-SpO2', `${spo2.validity} · ${spo2.source}`);

    const pr = vm.scalars.PR;
    this.setText('value-PR', pr.formatted);
    this.setText('state-PR', `${pr.validity} · ${pr.source}`);

    // 3. RR 呼吸率 & 趋势状态
    const rr = vm.scalars.RR;
    this.setText('value-RR', rr.formatted);
    this.setText('state-RR', `${rr.validity} · ${rr.source}`);
    if (rr.validity === 'VALID' && rr.formatted !== '—') {
      this.setText('rr-trend-status', `最近 120 秒 · ${rr.source}`);
    } else {
      this.setText('rr-trend-status', '无有效 RR 数据');
    }

    // 4. NIBP 无创血压 (SYS / DIA)
    const nibp = vm.scalars.NIBP;
    this.setText('pressure-sys', nibp.formatted);
    this.setText('pressure-dia', nibp.subFormatted ?? '—');
    this.setText('state-NIBP', `${nibp.validity} · ${nibp.source}`);
    this.setText('bp-updated', nibp.updatedTime ?? '—');

    // 5. TEMP 体温
    const temp = vm.scalars.TEMP;
    this.setText('value-TEMP', temp.formatted);
    this.setText('state-TEMP', `${temp.validity} · ${temp.source}`);

    // 6. 波形通道质量标牌与空状态指示
    const ecgValid = hr.validity === 'VALID';
    this.setText('quality-ECG', `${hr.validity} · ${hr.source}`);
    const emptyEcg = this.getEl('empty-ECG');
    if (emptyEcg) emptyEcg.hidden = ecgValid;

    const respValid = rr.validity === 'VALID';
    this.setText('quality-RESP', `${rr.validity} · ${rr.source}`);
    const emptyResp = this.getEl('empty-RESP');
    if (emptyResp) emptyResp.hidden = respValid;

    const ppgValid = spo2.validity === 'VALID';
    this.setText('quality-PPG', `${spo2.validity} · ${spo2.source}`);
    const emptyPpg = this.getEl('empty-PPG');
    if (emptyPpg) emptyPpg.hidden = ppgValid;

    // 7. 补传、事件与底部时间
    this.setText('replay-status', vm.replayStatus);
    this.setText('event-status', vm.eventStatus);
    this.setText('updated', vm.lastUpdatedText);
    this.setText('source-note', vm.sourceNote);

    // 8. 离线状态模块降暗处理
    this.updateModuleDimming('ECG', hr.validity);
    this.updateModuleDimming('NIBP', nibp.validity);
    this.updateModuleDimming('RESP', rr.validity);
    this.updateModuleDimming('SpO2', spo2.validity);
  }

  private updateModuleDimming(moduleName: string, validity: string): void {
    const el = document.querySelector<HTMLElement>(`[data-module="${moduleName}"]`);
    if (el) {
      el.classList.toggle('channel-offline', validity === 'OFFLINE');
    }
  }
}
