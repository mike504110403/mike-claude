// [Mike 2026-09-08] post-edit 背景重建改帶 --lsp，避免上游 sync-run.js 的裸 `graft build .` 把 gopls 呼叫邊丟掉。
// 由 graft-hooks-global.cjs 經 GRAFT_TEST_SYNC_RUN 指到本檔；上游 API 以 @nanonets/graft@0.15.0 為準，升級後重驗。
import { execFileSync } from 'node:child_process';
import { runSync } from '/Users/mike/.nvm/versions/node/v20.20.0/lib/node_modules/@nanonets/graft/dist/claude/sync-run.js';
const CLI = '/Users/mike/.nvm/versions/node/v20.20.0/lib/node_modules/@nanonets/graft/dist/cli.js';
function lspBuild(dir) {
  execFileSync(process.execPath, [CLI, 'build', '--lsp', '--no-gitignore', '--no-ignore', '.'], { cwd: dir, stdio: 'ignore', timeout: 180000 });
}
const dir = process.argv[2];
if (dir) runSync(dir, lspBuild);
