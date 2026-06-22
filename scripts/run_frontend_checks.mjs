import { spawnSync } from 'node:child_process';

const workspaces = ['frontend/crowdcraft', 'frontend/qf', 'frontend/mm', 'frontend/ir', 'frontend/tl'];
const commands = ['lint', 'typecheck', 'build'];
const failures = [];

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
