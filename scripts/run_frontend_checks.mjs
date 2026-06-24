import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { loadConfigFromFile } from 'vite';

const workspaces = ['frontend/crowdcraft', 'frontend/qf', 'frontend/mm', 'frontend/ir', 'frontend/tl'];
const appWorkspaces = workspaces.filter((workspace) => workspace !== 'frontend/crowdcraft');
const commands = ['lint', 'typecheck', 'build'];
const failures = [];
const requiredDedupe = ['react', 'react-dom', 'react-router', 'react-router-dom'];

for (const workspace of appWorkspaces) {
  const tsConfigPath = resolve(workspace, 'vite.config.ts');
  const jsConfigPath = resolve(workspace, 'vite.config.js');
  const configPath = existsSync(tsConfigPath) ? tsConfigPath : jsConfigPath;
  const loaded = await loadConfigFromFile(
    { command: 'build', mode: 'production' },
    configPath,
  );
  const configuredDedupe = loaded?.config.resolve?.dedupe ?? [];
  const missing = requiredDedupe.filter((dependency) => !configuredDedupe.includes(dependency));

  if (missing.length > 0) {
    console.error(`${workspace}: Vite must deduplicate ${missing.join(', ')}`);
    failures.push(`${workspace}:vite-react-dedupe`);
  }
}

console.log('\n==> frontend initial render verification');
const initialRenderResult = spawnSync('node', ['scripts/verify_frontend_initial_renders.mjs'], {
  stdio: 'inherit',
  shell: false,
});
if (initialRenderResult.status !== 0) {
  failures.push('frontend:initial-render');
}

for (const workspace of workspaces) {
  for (const command of commands) {
    console.log(`\n==> ${workspace}: npm run ${command}`);
    const result = spawnSync('npm', ['run', '--workspace', workspace, command], {
      stdio: 'inherit',
      shell: false,
    });
    if (result.status !== 0) {
      failures.push(`${workspace}:${command}`);
    }
  }
}

if (failures.length > 0) {
  console.error(`\nFrontend checks failed: ${failures.join(', ')}`);
  process.exitCode = 1;
} else {
  console.log('\nAll frontend lint, typecheck, and build checks passed.');
}
