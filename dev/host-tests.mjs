import { test } from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { once } from 'node:events';
import { createHash } from 'node:crypto';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { decode as nodeDecode, RedisFault, RedisClient, replyText, request, encode } from '../runtime/redis-host.mjs';
import { decode as restDecode, RestFault, envelope } from '../runtime/rest-decode.mjs';
import { command, createTwin } from '../runtime/rest-twin.mjs';

for (const [name, decode, Fault] of [['node', nodeDecode, RedisFault], ['rest', restDecode, RestFault]]) {
  test(`${name} fragmented RESP2 and exact payloads`, () => {
    const fixtures = [['+OK\r\n', 'OK'], ['$-1\r\n', null], ['*-1\r\n', null], [':-5\r\n', -5],
      ['$16\r\n9007199254740993\r\n', '9007199254740993'], ['$4\r\na\0\n\n\r\n', 'a\0\n\n'],
      ['$3\r\n\ufeff\r\n', '\ufeff'], ['$0\r\n\r\n', ''], ['*0\r\n', []],
      ['*3\r\n$-1\r\n*2\r\n:1\r\n+OK\r\n$1\r\nx\r\n', [null, [1, 'OK'], 'x']]];
    for (const [wire, value] of fixtures) {
      const bytes = Buffer.from(wire);
      for (let i = 0; i < bytes.length; i++) assert.equal(decode(bytes.subarray(0, i)), null, `${name} prefix ${i}`);
      assert.deepEqual(decode(bytes), { value, next: bytes.length });
    }
    assert.ok(decode(Buffer.from('-NOSCRIPT missing\r\n')).value instanceof Fault);
  });
  test(`${name} malformed and unsafe replies are refused`, () => {
    for (const wire of [':9007199254740993\r\n', ':1.5\r\n', ':01\r\n', '$-2\r\n', '*-2\r\n',
      '$9007199254740993\r\n', '?hello\r\n', '+a\nb\r\n', '-ERR x\ry\r\n',
      '$1\r\nx!!', '$+1\r\n', '*1.0\r\n', '*1\r\n'.repeat(66) + ':0\r\n'])
      assert.throws(() => decode(Buffer.from(wire)), undefined, wire);
    assert.throws(() => decode(Buffer.from([36, 49, 13, 10, 255, 13, 10])));
    assert.throws(() => decode(Buffer.alloc(8 * 1024 * 1024 + 1)));
  });
}
test('envelopes and stdout preserve variants', () => {
  assert.deepEqual(envelope(new RestFault('BUSY')), { error: 'BUSY' });
  assert.deepEqual(envelope('9007199254740993'), { result: '9007199254740993' });
  assert.throws(() => envelope([new RestFault('ERR nested')]));
  assert.equal(replyText(null), '\n');
  assert.equal(replyText('a\0\n'), 'a\0\n\n');
  assert.equal(replyText([null, ['9007199254740993', 'x']]), '[null,["9007199254740993","x"]]\n');
  for (const value of [false, {}, 1.5, 9007199254740992, [true], new RedisFault('ERR')])
    assert.throws(() => replyText(value));
  assert.equal(encode(['GET', 'é']).toString(), '*2\r\n$3\r\nGET\r\n$2\r\né\r\n');
});
const body = Buffer.from('return "ok"'), sha = createHash('sha1').update(body).digest('hex');
test('load once, exact NOSCRIPT fallback and original bytes', async () => {
  const calls = [], answers = [sha, 'first', new RedisFault('NOSCRIPT missing'), 'second', 'third'];
  const client = new RedisClient(1, async args => { calls.push(args); return answers.shift(); });
  for (const answer of ['first', 'second', 'third']) assert.equal(await client.invoke(body, sha, ['k']), answer);
  assert.deepEqual(calls.map(args => args[0]), ['SCRIPT', 'EVALSHA', 'EVALSHA', 'EVAL', 'EVALSHA']);
  assert.deepEqual(calls[0], ['SCRIPT', 'LOAD', body]);
  assert.deepEqual(calls[3], ['EVAL', body, '1', 'k']);
});
test('load failure, non-NOSCRIPT, network failure and second NOSCRIPT never retry', async () => {
  for (const [answers, count] of [
    [[new RedisFault('NOAUTH')], 1], [['wrong hash'], 1], [[new RedisFault('NOSCRIPT')], 1],
    [[sha, new RedisFault('NOSCRIPTED')], 2], [[sha, new RedisFault('BUSY')], 2],
    [[sha, new RedisFault('ERR embedded NOSCRIPT')], 2],
    [[sha, new Error('Network')], 2], [[sha, new RedisFault('NOSCRIPT'), new RedisFault('NOSCRIPT')], 3]]) {
    const calls = [];
    const client = new RedisClient(1, async args => {
      calls.push(args); const value = answers.shift();
      if (value instanceof Error && !(value instanceof RedisFault)) throw value;
      return value;
    });
    await assert.rejects(client.invoke(body, sha, []));
    assert.equal(calls.length, count);
  }
  const client = new RedisClient(1, async () => assert.fail('hash mismatch made a request'));
  await assert.rejects(client.invoke(Buffer.from('changed'), sha, []), /body hash/);
});
async function fixture(handler, use) {
  const sockets = new Set();
  const server = net.createServer(socket => {
    sockets.add(socket); socket.on('error', () => {}); socket.on('close', () => sockets.delete(socket));
    handler(socket);
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  try { await use(server.address().port); }
  finally { for (const socket of sockets) socket.destroy(); await new Promise(resolve => server.close(resolve)); }
}
for (const [name, send] of [['node', request], ['rest', command]]) {
  test(`${name} socket framing, truncation, limits and deadlines`, async () => {
    await fixture(socket => socket.once('data', bytes => {
      assert.equal(bytes.toString(), '*1\r\n$4\r\nPING\r\n');
      socket.write('$4\r\na'); setTimeout(() => socket.end('b\0c\r\n'), 5);
    }), async port => {
      const result = await send(port, ['PING']);
      assert.deepEqual(result, name === 'node' ? 'ab\0c' : { result: 'ab\0c' });
    });
    await fixture(s => s.once('data', () => s.end('$4\r\nab')), async p => assert.rejects(send(p, ['PING']), /truncated/));
    await fixture(s => s.once('data', () => s.end('+OK\r\n+extra\r\n')),
      async p => assert.rejects(send(p, ['PING']), /trailing/));
    await fixture(() => {}, async p => assert.rejects(send(p, ['PING'], 20), /timeout/));
  });
}
test('REST authentication and invalid request bodies cannot reach Redis', async () => {
  const calls = [];
  const twin = createTwin({ token: 'test-token', send: async args => { calls.push(args); return { result: 'ok' }; } });
  twin.listen(0, '127.0.0.1'); await once(twin, 'listening');
  try {
    const url = `http://127.0.0.1:${twin.address().port}/`;
    const post = (body, token = 'test-token') => fetch(url, { method: 'POST',
      headers: { Authorization: `Bearer ${token}` }, body });
    assert.equal((await post('["EVAL","x","0"]', 'wrong')).status, 401);
    for (const body of ['null', '[]', '[1]', '["x",null]', '["\\ud800"]', '{', '["FLUSHALL"]'])
      assert.equal((await post(body)).status, 400);
    assert.deepEqual(calls, []);
    const result = await post('["EVAL","return 1","0"]');
    assert.equal(result.status, 200); assert.deepEqual(await result.json(), { result: 'ok' });
    assert.deepEqual(calls, [['EVAL', 'return 1', '0']]);
  } finally { twin.closeAllConnections(); await new Promise(resolve => twin.close(resolve)); }
});
test('the REST request log keeps refused command text out of the record', async () => {
  const log = join(mkdtempSync(join(tmpdir(), 'tether-rest-')), 'requests.jsonl');
  const twin = createTwin({ token: 'test-token', log, send: async () => ({ result: 'ok' }) });
  twin.listen(0, '127.0.0.1'); await once(twin, 'listening');
  try {
    const url = `http://127.0.0.1:${twin.address().port}/`;
    const post = body => fetch(url, { method: 'POST',
      headers: { Authorization: 'Bearer test-token' }, body });
    const script = 'return redis.call("GET", KEYS[1]) -- {counter}:hits:visits';
    assert.equal((await post(JSON.stringify([script]))).status, 400);
    assert.equal((await post(JSON.stringify(['SCRIPT', 'FLUSH-{counter}:hits:visits']))).status, 400);
    assert.equal((await post('["EVAL","return 1","0"]')).status, 200);
    const text = readFileSync(log, 'utf8');
    assert.deepEqual(text.trimEnd().split('\n').map(row => JSON.parse(row).command),
      ['other', 'other', 'EVAL']);
    assert.ok(!text.includes('{counter}') && !text.includes('redis.call'), text);
  } finally { twin.closeAllConnections(); await new Promise(resolve => twin.close(resolve)); }
});
