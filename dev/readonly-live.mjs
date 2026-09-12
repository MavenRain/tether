import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { readFile } from 'node:fs/promises';
import { RedisClient, RedisFault, request } from '../runtime/redis-host.mjs';
import { createTwin, command } from '../runtime/rest-twin.mjs';
import { trace } from './lua-same.mjs';

const [directory, portText] = process.argv.slice(2), port = Number(portText);
const scripts = JSON.parse(await readFile(join(directory, 'scripts.json')));
const observed = await trace(join(directory, 'prog.wasm'));
assert.equal(scripts.length, 1); assert.equal(observed.calls.length, 2);
const script = { ...scripts[0], body: observed.calls[0].body }, expected = '9007199254740993', calls = [];
assert.deepEqual(observed.calls[0].args, [script.sha1, ...script.keys].map(x => Buffer.from(x)));
assert.deepEqual(script.keys, ['{counter}:hits:visits']);
assert.equal(await request(port, ['SET', script.keys[0], expected]), 'OK');
const client = new RedisClient(port, args => { calls.push(args); return request(port, args); });
assert.equal(await client.invoke(script.body, script.sha1, script.keys), expected);
assert.equal(await request(port, ['SCRIPT', 'FLUSH']), 'OK');
assert.equal(await client.invoke(script.body, script.sha1, script.keys), expected);
assert.equal(await client.invoke(script.body, script.sha1, script.keys), expected);
assert.deepEqual(calls.map(args => args[0]), ['SCRIPT', 'EVALSHA_RO', 'EVALSHA_RO', 'EVAL_RO', 'EVALSHA_RO']);
assert.deepEqual(calls[0][2], calls[3][1]);
assert.deepEqual(calls[3].slice(2), ['1', ...script.keys]);

const restCalls = [], twin = createTwin({ token: 'readonly-fallback', send: async args => {
  restCalls.push(args);
  const reply = await command(port, args);
  if (args[0] === 'SCRIPT') await command(port, ['SCRIPT', 'FLUSH']);
  return reply;
} });
twin.listen(0, '127.0.0.1'); await once(twin, 'listening');
try {
  const { stdout, stderr } = await promisify(execFile)('/bin/bash', [join(directory, 'prog.sh')], {
    timeout: 30000, env: { ...process.env, TETHER_TOKEN: 'readonly-fallback',
      TETHER_URL: `http://127.0.0.1:${twin.address().port}/` },
  });
  assert.equal(stdout, expected + '\n'); assert.equal(stderr, '');
  assert.deepEqual(restCalls.map(args => args[0]), ['SCRIPT', 'EVALSHA_RO', 'EVAL_RO', 'EVALSHA_RO']);
  assert.equal(restCalls[0][2], script.body.toString());
  assert.equal(restCalls[2][1], script.body.toString());
  assert.deepEqual(restCalls[2].slice(2), ['1', ...script.keys]);
} finally { twin.closeAllConnections(); await new Promise(resolve => twin.close(resolve)); }

// Redis itself enforces no-writes, including on a flushed-cache fallback.
const badBody = Buffer.from('#!lua flags=no-writes\nreturn redis.call("SET", KEYS[1], "changed")');
const badSha = createHash('sha1').update(badBody).digest('hex'), refused = [];
const writer = new RedisClient(port, async args => {
  refused.push(args[0]); const reply = await request(port, args);
  if (args[0] === 'SCRIPT') await request(port, ['SCRIPT', 'FLUSH']);
  return reply;
});
await assert.rejects(writer.invoke(badBody, badSha, script.keys), error =>
  error instanceof RedisFault && /Write commands are not allowed/.test(error.message));
assert.deepEqual(refused, ['SCRIPT', 'EVALSHA_RO', 'EVAL_RO']);
assert.equal(await request(port, ['GET', script.keys[0]]), expected);
console.log('PASS RO-LIVE node_flush=1 bash_flush=1 write_refused=1 exact_bytes=1');
