import { test } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { RedisClient, RedisFault, readOnlyBody, shebangFlags } from '../runtime/redis-host.mjs';
import { createTwin } from '../runtime/rest-twin.mjs';

const body = Buffer.from('#!lua flags=no-writes\nreturn redis.call("GET", KEYS[1])');
const sha = createHash('sha1').update(body).digest('hex');
test('RO-NODE load once and retain read-only mode on exact NOSCRIPT', async () => {
  for (const fault of ['NOSCRIPT', 'NOSCRIPT No matching script.']) {
    const calls = [], answers = [sha, null, new RedisFault(fault), '9007199254740993', 'last'];
    const client = new RedisClient(1, async args => { calls.push(args); return answers.shift(); });
    for (const expected of [null, '9007199254740993', 'last'])
      assert.equal(await client.invoke(body, sha, ['k']), expected);
    assert.deepEqual(calls, [
      ['SCRIPT', 'LOAD', body], ['EVALSHA_RO', sha, '1', 'k'],
      ['EVALSHA_RO', sha, '1', 'k'], ['EVAL_RO', body, '1', 'k'],
      ['EVALSHA_RO', sha, '1', 'k'],
    ]);
  }
});
test('RO-NODE non-NOSCRIPT failures and failed fallback never downgrade or retry', async () => {
  for (const [answers, expected] of [
    [[new RedisFault('NOAUTH')], ['SCRIPT']],
    [['bad hash'], ['SCRIPT']],
    [[sha, new RedisFault('NOPERM read-only command')], ['SCRIPT', 'EVALSHA_RO']],
    [[sha, new RedisFault('NOSCRIPTED')], ['SCRIPT', 'EVALSHA_RO']],
    [[sha, new RedisFault('ERR embedded NOSCRIPT')], ['SCRIPT', 'EVALSHA_RO']],
    [[sha, new Error('Network')], ['SCRIPT', 'EVALSHA_RO']],
    [[sha, new RedisFault('NOSCRIPT'), new RedisFault('NOSCRIPT')], ['SCRIPT', 'EVALSHA_RO', 'EVAL_RO']],
  ]) {
    const calls = [], client = new RedisClient(1, async args => {
      calls.push(args[0]); const answer = answers.shift();
      if (answer instanceof Error && !(answer instanceof RedisFault)) throw answer;
      return answer;
    });
    await assert.rejects(client.invoke(body, sha, []));
    assert.deepEqual(calls, expected);
  }
  await assert.rejects(new RedisClient(1, async () => assert.fail('unverified body sent'))
    .invoke(Buffer.concat([body, Buffer.from(' ')]), sha, []), /body hash/);
});
test('RO-NODE canonical header only and mode is selected independently per body', async () => {
  const calls = [], client = new RedisClient(1, async args => {
    calls.push(args);
    return args[0] === 'SCRIPT' ? createHash('sha1').update(args[2]).digest('hex') : 'ok';
  });
  const sources = [body, Buffer.from('#!lua\nreturn 1'), body,
    Buffer.from('-- #!lua flags=no-writes\nreturn 1'),
    Buffer.from('#!lua flags=no-writes-extra\nreturn 1'),
    Buffer.from('#!lua flags=no-writes'), Buffer.from('return "no-writes"'),
    Buffer.from('#!lua flags=no-writes,allow-stale\nreturn 1'),
    Buffer.from('#!lua flags=allow-stale\nreturn 1')];
  for (const source of sources)
    await client.invoke(source, createHash('sha1').update(source).digest('hex'), []);
  assert.deepEqual(calls.filter(args => args[0] !== 'SCRIPT').map(args => args[0]),
    ['EVALSHA_RO', 'EVALSHA', 'EVALSHA_RO', 'EVALSHA', 'EVALSHA', 'EVALSHA', 'EVALSHA',
      'EVALSHA_RO', 'EVALSHA']);
});
// The compiler owns the header text. This case derives both branches of
// print/lua.ml from that source and requires the Node classifier to agree,
// so the two literals cannot drift apart without a failing test.
test('RO-NODE header classification follows the compiler source', async () => {
  const ocaml = await readFile(new URL('../print/lua.ml', import.meta.url), 'utf8');
  const match = /let header = if no_writes then "([^"]*)" else "([^"]*)" in/.exec(ocaml);
  assert.ok(match, 'header literal not found in print/lua.ml');
  const literal = text => Buffer.from(text.split('\\n').join('\n'));
  assert.equal(readOnlyBody(literal(match[1])), true);
  assert.equal(readOnlyBody(literal(match[2])), false);
  assert.deepEqual(shebangFlags(literal(match[1])), ['no-writes']);
});
test('RO-REST admits both read-only commands and retains authentication and allowlist', async () => {
  const calls = [], twin = createTwin({ token: 'readonly-test', send: async args => {
    calls.push(args); return { result: '9007199254740993' };
  } });
  twin.listen(0, '127.0.0.1'); await once(twin, 'listening');
  try {
    const post = (args, token = 'readonly-test') => fetch(`http://127.0.0.1:${twin.address().port}/`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(args),
    });
    for (const command of ['EVALSHA_RO', 'EVAL_RO']) {
      const args = [command, command === 'EVAL_RO' ? body.toString() : sha, '1', 'k'];
      assert.equal((await post(args, 'invalid')).status, 401);
      const response = await post(args);
      assert.equal(response.status, 200);
      assert.deepEqual(await response.json(), { result: '9007199254740993' });
      assert.deepEqual(calls.at(-1), args);
    }
    for (const args of [['EVALSHA_RO_EXTRA', sha, '0'], ['FLUSHALL'], ['SCRIPT', 'FLUSH']])
      assert.equal((await post(args)).status, 400);
    assert.equal(calls.length, 2);
  } finally { twin.closeAllConnections(); await new Promise(resolve => twin.close(resolve)); }
});
