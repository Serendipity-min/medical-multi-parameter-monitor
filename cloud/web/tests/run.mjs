// 使用项目已有 esbuild 编译测试入口；临时产物放系统临时目录并在退出时清理。
import { buildSync } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
const directory = mkdtempSync(join(tmpdir(), 'monitor-state-'));
try {
  // 状态与回执分别编译，复用现有工具链，不增加测试依赖。
  const files = ['state', 'ai'].map((name) => {
    const outfile = join(directory, `${name}.test.cjs`);
    buildSync({ entryPoints: [`tests/${name}.test.ts`], bundle: true, platform: 'node', outfile });
    return outfile;
  });
  const result = spawnSync(process.execPath, ['--test', ...files], { stdio: 'inherit' });
  process.exitCode = result.status ?? 1;
} finally {
  rmSync(directory, { recursive: true, force: true });
}
