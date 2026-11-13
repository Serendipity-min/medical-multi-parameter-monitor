// 只编译纯状态测试并读取Host快照文件，不创建浏览器、WebSocket或服务。
import { buildSync } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const [input, output] = process.argv.slice(2);
buildSync({ entryPoints: [fileURLToPath(new URL('./tri-host.test.ts', import.meta.url))],
  bundle: true, platform: 'node', outfile: output });
const result = spawnSync(process.execPath, ['--test', output], {
  env: { ...process.env, T0_SNAPSHOT_INPUT: input }, stdio: 'inherit',
});
process.exitCode = result.status ?? 1;
