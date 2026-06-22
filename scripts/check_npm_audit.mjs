import { spawnSync } from 'node:child_process';
import fs from 'node:fs';

const exceptions = JSON.parse(
  fs.readFileSync(new URL('../security/npm-audit-exceptions.json', import.meta.url), 'utf8'),
);
const result = spawnSync('npm', ['audit', '--audit-level=high', '--json'], {
  encoding: 'utf8',
});
const report = JSON.parse(result.stdout || '{}');
const today = new Date().toISOString().slice(0, 10);
const failures = [];

for (const [packageName, vulnerability] of Object.entries(report.vulnerabilities || {})) {
  for (const advisory of vulnerability.via || []) {
    if (typeof advisory === 'string') continue;
    if (!['high', 'critical'].includes(advisory.severity)) continue;

    const advisoryId = advisory.url.split('/').at(-1);
    const exception = exceptions[advisoryId];
    if (!exception || exception.package !== packageName) {
      failures.push(
        `${packageName}: ${advisoryId} (${advisory.severity}) has no matching exception`,
      );
    } else if (exception.expires < today) {
      failures.push(`${packageName}: ${advisoryId} exception expired ${exception.expires}`);
    } else {
      console.warn(
        `Accepted temporary npm audit exception ${advisoryId} for ${packageName} ` +
        `through ${exception.expires}: ${exception.reason}`,
      );
    }
  }
}

if (failures.length > 0) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log('npm high/critical audit gate passed.');
