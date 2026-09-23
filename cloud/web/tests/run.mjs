// 使用项目已有 esbuild 编译测试入口；临时产物放系统临时目录并在退出时清理。
import { buildSync } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
const directory = mkdtempSync(join(tmpdir(), 'monitor-state-'));
try {
  const outfile = join(directory, 'state.test.cjs');
  buildSync({ entryPoints: ['tests/state.test.ts'], bundle: true, platform: 'node', outfile });
  const result = spawnSync(process.execPath, ['--test', outfile], { stdio: 'inherit' });
  process.exitCode = result.status ?? 1;
} finally {
  rmSync(directory, { recursive: true, force: true });
}
