import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const sourcePath = new URL('../frontend/crowdcraft/src/api/origin.ts', import.meta.url);
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const origin = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('API URLs default to the browser origin', () => {
  assert.equal(
    origin.resolveGameApiUrl('qf', undefined, 'https://quipflip.crowdcraftlabs.com'),
    'https://quipflip.crowdcraftlabs.com/qf',
  );
});

test('configured game prefixes are not duplicated', () => {
  assert.equal(
    origin.resolveGameApiUrl('ir', 'https://api.example.test/ir/', 'https://ignored.test'),
    'https://api.example.test/ir',
  );
});

test('WebSocket URLs preserve same-origin protocol and path', () => {
  assert.equal(
    origin.resolveWebSocketUrl(
      '/qf/party/session/ws',
      undefined,
      'https://quipflip.crowdcraftlabs.com',
    ).toString(),
    'wss://quipflip.crowdcraftlabs.com/qf/party/session/ws',
  );
});
