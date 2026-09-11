import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { once } from 'node:events';
import { join } from 'node:path';
import { RedisClient, request } from '../runtime/redis-host.mjs';
import { createTwin, command } from '../runtime/rest-twin.mjs';
import { artifacts } from './run-node.mjs';
const [directory, portText] = process.argv.slice(2), port = Number(portText);
const { bodies } = await artifacts(directory), script = [...bodies.values()][0], calls = [];
const client = new RedisClient(port, args => { calls.push(args); return request(port, args); });
assert.equal(await client.invoke(script.body, script.sha1, script.keys), '9007199254740993');
assert.equal(await request(port, ['SCRIPT', 'FLUSH']), 'OK');
assert.equal(await client.invoke(script.body, script.sha1, script.keys), '9007199254740994');
assert.equal(await client.invoke(script.body, script.sha1, script.keys), '9007199254740995');
assert.deepEqual(calls.map(args => args[0]), ['SCRIPT', 'EVALSHA', 'EVALSHA', 'EVAL', 'EVALSHA']);
assert.deepEqual(calls[0][2], calls[3][1]);
console.log('PASS NODE-NOSCRIPT loads=1 evalsha=3 eval=1 steady_calls=1');
const restCalls = [];
const twin = createTwin({ token: 'fallback-fixture', send: async args => {
  restCalls.push(args);
  const result = await command(port, args);
  if (args[0] === 'SCRIPT') await command(port, ['SCRIPT', 'FLUSH']);
  return result;
} });
twin.listen(0, '127.0.0.1'); await once(twin, 'listening');
try {
  await request(port, ['SET', '{counter}:hits:visits', '9007199254740992']);
  const { stdout, stderr } = await promisify(execFile)('/bin/bash', [join(directory, 'prog.sh')], {
    timeout: 30000, env: { ...process.env, TETHER_TOKEN: 'fallback-fixture',
      TETHER_URL: `http://127.0.0.1:${twin.address().port}/` },
  });
  assert.equal(stdout, '9007199254740993\n'); assert.equal(stderr, '');
  assert.deepEqual(restCalls.map(args => args[0]), ['SCRIPT', 'EVALSHA', 'EVAL']);
  assert.equal(restCalls[0][2], restCalls[2][1]);
  assert.equal(restCalls[0][2], script.body.toString());
  assert.deepEqual(restCalls[2].slice(2), ['1', ...script.keys]);
  console.log('PASS BASH-NOSCRIPT loads=1 evalsha=1 eval=1 same_body=1');
} finally { twin.closeAllConnections(); await new Promise(resolve => twin.close(resolve)); }
