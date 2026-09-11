import assert from 'node:assert/strict';
import { join } from 'node:path';
import { trace } from './lua-same.mjs';
const [directory] = process.argv.slice(2);
for (const name of ['main', 'twice', 'earlierOutput', 'capturedReply', 'exactMain', 'readMain', 'incrementMain']) {
  const path = join(directory, name, 'prog.wasm');
  const control = await trace(path);
  assert.equal(control.exit, 0);
  for (let i = 0; i < control.calls.length; i++) {
    const failed = await trace(path, i);
    assert.equal(failed.exit, 4);
    assert.equal(failed.calls.length, i + 1);
    assert.deepEqual(failed.writes, []);
  }
}
const stopped = await trace(join(directory, 'stopped', 'prog.wasm'));
assert.equal(stopped.exit, 4);
assert.deepEqual(stopped.calls, []);
assert.deepEqual(stopped.writes, []);
const afterFault = await trace(join(directory, 'afterFault', 'prog.wasm'));
assert.equal(afterFault.exit, 4);
assert.equal(afterFault.calls.length, 1);
assert.deepEqual(afterFault.writes, []);
console.log('PASS CLIENT-REACTOR captured=1 first-fault=1 stopped=1');
