import http from 'node:http';
import net from 'node:net';
import { appendFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { decode, envelope } from './rest-decode.mjs';

const LIMIT = 8 * 1024 * 1024;
// This transport deliberately owns its framing as well as its reply decoder.
export function command(port, args, timeout = 5000) {
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Redis port');
  const parts = [Buffer.from(`*${args.length}\r\n`)];
  for (const arg of args) {
    const bytes = Buffer.from(arg);
    parts.push(Buffer.from(`$${bytes.length}\r\n`), bytes, Buffer.from('\r\n'));
  }
  const payload = Buffer.concat(parts);
  if (payload.length > LIMIT) throw new Error('REST command limit');
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: '127.0.0.1', port });
    let received = Buffer.alloc(0), done = false;
    const finish = (error, result) => {
      if (done) return;
      done = true; clearTimeout(timer); socket.destroy();
      if (error) reject(error); else resolve(result);
    };
    const timer = setTimeout(() => finish(new Error('Redis timeout')), timeout);
    socket.on('connect', () => socket.write(payload));
    socket.on('error', e => finish(e));
    socket.on('end', () => finish(new Error('Redis truncated reply')));
    socket.on('data', bytes => {
      try {
        received = Buffer.concat([received, bytes]);
        const frame = decode(received);
        if (frame) {
          if (frame.next !== received.length) throw new Error('REST trailing reply');
          finish(null, envelope(frame.value));
        }
      } catch (error) { finish(error); }
    });
  });
}
export function createTwin({ redisPort, token, log, send = args => command(redisPort, args) }) {
  if (typeof token !== 'string' || !token || /[\r\n]/.test(token)) throw new Error('REST token required');
  const server = http.createServer(async (request, response) => {
    let action = {};
    const reply = (status, body) => {
      try { if (log) appendFileSync(log, JSON.stringify({ method: request.method, status, ...action }) + '\n'); }
      catch { status = 500; body = { error: 'HTTP request log failure' }; }
      response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
      response.end(JSON.stringify(body));
    };
    if (request.method !== 'POST' || request.url !== '/') {
      request.resume(); reply(404, { error: 'HTTP route' }); return;
    }
    if (request.headers.authorization !== `Bearer ${token}`) {
      request.resume(); reply(401, { error: 'NOAUTH Authentication required.' }); return;
    }
    try {
      const parts = []; let size = 0;
      for await (const part of request) {
        size += part.length;
        if (size > LIMIT) { reply(413, { error: 'HTTP body limit' }); return; }
        parts.push(part);
      }
      let args;
      try {
        args = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(parts)));
        if (!Array.isArray(args) || !args.length || args.length > 65536 ||
            args.some(arg => typeof arg !== 'string' || !arg.isWellFormed())) throw new Error('arguments');
      } catch { reply(400, { error: 'HTTP expected a JSON array of strings' }); return; }
      // The log holds allowlisted names only: a refused request never puts
      // attacker text, a script body or a key name in the record.
      const name = args[0].toUpperCase(), sub = name === 'SCRIPT' ? args[1]?.toUpperCase() : undefined;
      const allowed = ['EVAL', 'EVALSHA', 'SCRIPT'];
      if (!allowed.includes(name) || (name === 'SCRIPT' && sub !== 'LOAD')) {
        action = { command: 'other' };
        reply(400, { error: 'HTTP unsupported command' }); return;
      }
      action = { command: name, subcommand: sub };
      reply(200, await send(args));
    } catch { if (!response.headersSent) reply(502, { error: 'Network or invalid Redis reply' }); }
  });
  server.requestTimeout = 10000;
  server.headersTimeout = 10000;
  server.timeout = 10000;
  return server;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const redisPort = Number(process.env.TETHER_REDIS_PORT), port = Number(process.env.TETHER_REST_PORT ?? 0);
    if (!Number.isInteger(port) || port < 0 || port > 65535 || !Number.isInteger(redisPort) ||
        redisPort < 1 || redisPort > 65535) throw new Error('REST ports');
    const server = createTwin({ redisPort, token: process.env.TETHER_TOKEN, log: process.env.TETHER_REST_LOG });
    server.on('error', error => { console.error(`REST ${error.message}`); process.exitCode = 4; });
    server.listen(port, '127.0.0.1', () => console.log(`REST-UP port=${server.address().port}`));
    const stop = () => { server.close(); server.closeAllConnections(); };
    process.once('SIGTERM', stop); process.once('SIGINT', stop);
  } catch (error) { console.error(`REST ${error.message}`); process.exitCode = 4; }
}
