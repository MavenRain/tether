import net from 'node:net';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

const MAX = 8 * 1024 * 1024;
const utf8 = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
export class RedisFault extends Error {}
// RESP2 decoder owned by the Node host. null means an incomplete frame.
export function decode(buffer, start = 0, depth = 0) {
  if (depth > 64 || buffer.length > MAX) throw new Error('RESP limit');
  if (start >= buffer.length) return null;
  const end = buffer.indexOf('\r\n', start);
  if (end < 0) return null;
  const tag = buffer[start], text = utf8(buffer.subarray(start + 1, end));
  if (/[\r\n]/.test(text)) throw new Error('RESP line terminator');
  let next = end + 2;
  if (tag === 43) return { value: text, next };
  if (tag === 45) return { value: new RedisFault(text), next };
  if (![58, 36, 42].includes(tag) || !/^(0|-?[1-9][0-9]*)$/.test(text)) throw new Error('RESP header');
  if (tag === 58) {
    const number = Number(text);
    if (!Number.isSafeInteger(number)) throw new Error('INTEGER-BOUNDARY expected bulk string');
    return { value: number, next };
  }
  const length = Number(text);
  if (!Number.isSafeInteger(length) || length < -1 || length > MAX) throw new Error('RESP length');
  if (length === -1) return { value: null, next };
  if (tag === 36) {
    if (next + length + 2 > buffer.length) return null;
    if (buffer[next + length] !== 13 || buffer[next + length + 1] !== 10) throw new Error('RESP bulk terminator');
    return { value: utf8(buffer.subarray(next, next + length)), next: next + length + 2 };
  }
  const values = [];
  for (let i = 0; i < length; i++) {
    const part = decode(buffer, next, depth + 1);
    if (!part) return null;
    values.push(part.value); next = part.next;
  }
  return { value: values, next };
}
export function encode(args) {
  if (!Array.isArray(args) || !args.length || args.some(x => typeof x !== 'string' && !Buffer.isBuffer(x)))
    throw new Error('RESP arguments');
  const chunks = [Buffer.from(`*${args.length}\r\n`)];
  for (const arg of args) {
    const bytes = Buffer.from(arg);
    chunks.push(Buffer.from(`$${bytes.length}\r\n`), bytes, Buffer.from('\r\n'));
  }
  const buffer = Buffer.concat(chunks);
  if (buffer.length > MAX) throw new Error('RESP request limit');
  return buffer;
}
export function request(port, args, timeout = 5000) {
  const wire = encode(args);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Redis port');
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: '127.0.0.1', port });
    let buffer = Buffer.alloc(0), finished = false;
    const finish = (error, value) => {
      if (finished) return;
      finished = true; clearTimeout(timer); socket.destroy();
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => finish(new Error('Redis timeout')), timeout);
    socket.on('error', error => finish(error));
    socket.on('end', () => finish(new Error('Redis truncated reply')));
    socket.on('connect', () => socket.write(wire));
    socket.on('data', chunk => {
      try {
        buffer = Buffer.concat([buffer, chunk]);
        const frame = decode(buffer);
        if (frame) {
          if (frame.next !== buffer.length) throw new Error('Redis trailing reply');
          finish(null, frame.value);
        }
      } catch (error) { finish(error); }
    });
  });
}
// One canonical array text for every host. jq escapes the DEL byte and
// JSON.stringify does not, so the Node text escapes it too.
export const arrayText = value => JSON.stringify(value).split('\u007f').join('\\u007f');
export function replyText(reply) {
  const safe = (value, depth = 0) => {
    if (depth > 64) throw new Error('Reply depth');
    if (value instanceof RedisFault) throw value;
    if (value === null || typeof value === 'string') return;
    if (typeof value === 'number' && Number.isSafeInteger(value)) return;
    if (Array.isArray(value)) { for (const item of value) safe(item, depth + 1); return; }
    throw new Error('Invalid Reply');
  };
  safe(reply);
  return (reply === null ? '' : Array.isArray(reply) ? arrayText(reply) : String(reply)) + '\n';
}
// The read-only mode reads the emitted shebang flag list instead of a fixed
// byte prefix, so a later flag beside no-writes keeps the read-only dispatch
// that the Bash artifact selects from the same compiler flag.
export const shebangFlags = body => {
  const end = body.indexOf(10);
  const line = end < 0 ? '' : body.subarray(0, end).toString('utf8');
  return line.startsWith('#!lua flags=') ? line.slice('#!lua flags='.length).split(',') : [];
};
export const readOnlyBody = body => shebangFlags(body).includes('no-writes');
export class RedisClient {
  constructor(port, send = args => request(port, args)) { this.send = send; this.loaded = new Set(); }
  async invoke(body, sha, keys) {
    if (!Buffer.isBuffer(body) || createHash('sha1').update(body).digest('hex') !== sha)
      throw new Error('LUA-SAME body hash');
    if (!Array.isArray(keys) || keys.some(key => typeof key !== 'string' && !Buffer.isBuffer(key)))
      throw new Error('Redis keys');
    if (!this.loaded.has(sha)) {
      const loaded = await this.send(['SCRIPT', 'LOAD', body]);
      if (loaded instanceof RedisFault) throw loaded;
      if (loaded !== sha) throw new Error('SCRIPT LOAD hash mismatch');
      this.loaded.add(sha);
    }
    const suffix = readOnlyBody(body) ? '_RO' : '';
    let reply = await this.send(['EVALSHA' + suffix, sha, String(keys.length), ...keys]);
    if (reply instanceof RedisFault && /^NOSCRIPT(?: |$)/.test(reply.message))
      reply = await this.send(['EVAL' + suffix, body, String(keys.length), ...keys]);
    replyText(reply);
    return reply;
  }
}
// The Stage F Client can use code 10 with args [sha1, ...keys] and a Lua body.
// Resume receives status 0 and a result envelope, or status 1 and an error envelope.
export async function runReactor(path, port, output = process.stdout) {
  const { instance } = await WebAssembly.instantiate(await readFile(path));
  const a = instance.exports, client = new RedisClient(port);
  for (const name of ['emptyBytes', 'consBytes', 'bytesEmpty', 'bytesHead', 'bytesTail',
    'emptyWords', 'wordsEmpty', 'wordsHead', 'wordsTail', 'init', 'resume',
    'requestCode', 'requestArgs', 'requestBody', 'exitCode'])
    if (typeof a[name] !== 'function') throw new Error(`Missing reactor export ${name}`);
  const read = list => {
    const bytes = [];
    while (!a.bytesEmpty(list)) {
      const n = a.bytesHead(list);
      if (!Number.isInteger(n) || n < 0 || n > 255 || bytes.length >= MAX) throw new Error('ABI bytes');
      bytes.push(n); list = a.bytesTail(list);
    }
    return Buffer.from(bytes);
  };
  const write = buffer => {
    let list = a.emptyBytes();
    for (let i = buffer.length - 1; i >= 0; i--) list = a.consBytes(buffer[i], list);
    return list;
  };
  output.on('error', ignoreOutputError);
  try {
    let state = a.init(a.emptyWords());
    for (let step = 0; step < 100000; step++) {
      const code = a.requestCode(state);
      if (code === 0) {
        const exit = a.exitCode(state);
        if (!Number.isInteger(exit) || exit < 0 || exit > 255) throw new Error('ABI exit');
        return exit;
      }
      const body = read(a.requestBody(state));
      let status = 0, answer = Buffer.alloc(0);
      if (code === 6 || code === 11) {
        let text = body;
        if (code === 11) {
          const envelope = JSON.parse(utf8(body));
          if (!envelope || Array.isArray(envelope) || Object.keys(envelope).length !== 1 ||
              !Object.hasOwn(envelope, 'result')) throw new Error('Invalid result envelope');
          text = Buffer.from(replyText(envelope.result));
        }
        await new Promise((ok, fail) => output.write(text, e => e ? fail(e) : ok()));
      }
      else if (code === 10) {
        const args = []; let words = a.requestArgs(state);
        while (!a.wordsEmpty(words)) {
          if (args.length >= 65536) throw new Error('ABI words');
          args.push(read(a.wordsHead(words))); words = a.wordsTail(words);
        }
        try {
          if (!args.length) throw new Error('ABI missing SHA-1');
          answer = Buffer.from(JSON.stringify({ result: await client.invoke(body, utf8(args[0]), args.slice(1)) }));
        } catch (error) { status = 1; answer = Buffer.from(JSON.stringify({ error: error.message })); }
      } else throw new Error(`Unknown Redis request ${code}`);
      state = a.resume(state, status, write(answer));
    }
    throw new Error('Reactor step limit');
  } finally { output.removeListener('error', ignoreOutputError); }
}
function ignoreOutputError() {}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const [path, text] = process.argv.slice(2), port = Number(text);
    if (!path || !Number.isInteger(port) || port < 1 || port > 65535 || process.argv.length !== 4)
      throw new Error('Usage: redis-host.mjs prog.wasm PORT');
    process.exitCode = await runReactor(path, port);
  } catch (error) { console.error(`TETHER ${error.message}`); process.exitCode = 4; }
}
