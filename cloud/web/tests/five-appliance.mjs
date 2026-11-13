// 两种构建模式均调用真实默认模型/Socket/DOM模板，不连接网络。
import { buildSync } from 'esbuild';
import assert from 'node:assert/strict';
for (const mode of ['production', 'five-appliance']) {
  const bundle = buildSync({ stdin: { contents: `
    export {defaultGateway} from './src/gatewayProfile';
    export {parameters} from './src/ui/parameters';
    export {setupMonitorDOM} from './src/ui/monitorView';
    export {getEmptyViewModel} from './src/model/viewModel';
    export {MonitorSocket} from './src/transport/monitorSocket';
    export {voiceLabels} from './src/ui/aiResponse';`, resolveDir: process.cwd(), loader: 'ts' },
    bundle: true, format: 'esm', platform: 'node', write: false,
    define: { 'import.meta.env.MODE': JSON.stringify(mode) } });
  const m = await import('data:text/javascript;base64,' + Buffer.from(bundle.outputFiles[0].text).toString('base64'));
  const gateway = mode === 'five-appliance' ? 'GW-B5-001' : 'GW-C-001';
  assert.equal(m.defaultGateway, gateway);
  assert.equal(new m.MonitorSocket({}).getGatewayId(), gateway);
  assert.equal(m.getEmptyViewModel().gatewayId, gateway);
  const container = { innerHTML: '' }; m.setupMonitorDOM(container);
  // 网关由构建配置或 URL 决定，界面不再提供模拟/真机网关切换。
  assert.ok(!container.innerHTML.includes('gateway-select'));
  assert.ok(!/模拟网关|真机网关/.test(container.innerHTML));
  assert.equal(m.parameters.temp.node, mode === 'five-appliance' ? 'Node-D' : 'Node-B');
  assert.equal(m.parameters.nibp.node, mode === 'five-appliance' ? 'Node-E' : 'Node-A');
  assert.equal(m.parameters.temp.facts.find(([name])=>name==='采集节点')[1], m.parameters.temp.node);
  assert.match(m.voiceLabels.BROKER_PUBACK_ONLY_NOT_TTS_DONE, /未验证/);
  assert.match(m.voiceLabels.NO_RECORDING_CONTEXT, /K1/);
  console.log(mode + ' PROFILE_PASS');
}
