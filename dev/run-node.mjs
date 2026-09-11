// Development schedule over the Stage C byte carriers. The Client reactor is Stage F.
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { RedisClient, replyText } from '../runtime/redis-host.mjs';

export async function artifacts(directory) {
  const scripts = JSON.parse(await readFile(join(directory, 'scripts.json'), 'utf8'));
  const plan = JSON.parse(await readFile(join(directory, 'client.json'), 'utf8'));
  if (!Array.isArray(scripts) || !Array.isArray(plan.invokes) || plan.version !== 1 ||
      !Number.isInteger(plan.answer) || plan.answer < -1 || plan.answer >= plan.invokes.length)
    throw new Error('CLIENT plan');
  const bodies = new Map();
  for (const script of scripts) {
    if (typeof script.entry !== 'string' || bodies.has(script.entry) ||
        !/^body-[0-9]+$/.test(script.stem) || !/^[0-9a-f]{40}$/.test(script.sha1) ||
        !Array.isArray(script.keys) || script.keys.some(k => typeof k !== 'string')) throw new Error('CLIENT script');
    const { instance } = await WebAssembly.instantiate(await readFile(join(directory, script.stem + '.wasm')));
    const a = instance.exports;
    const extract = value => {
      const bytes = [];
      while (!a.bytesEmpty(value)) {
        const n = a.bytesHead(value);
        if (!Number.isInteger(n) || n < 0 || n > 255 || bytes.length >= 8 * 1024 * 1024)
          throw new Error('CLIENT carrier bytes');
        bytes.push(n); value = a.bytesTail(value);
      }
      return Buffer.from(bytes);
    };
    const body = extract(a.requestBody()), sha = extract(a.scriptSha1()).toString('ascii');
    if (sha !== script.sha1 || createHash('sha1').update(body).digest('hex') !== sha ||
        !body.equals(await readFile(join(directory, script.stem + '.lua')))) throw new Error('LUA-SAME carrier');
    bodies.set(script.entry, { ...script, body });
  }
  if (plan.invokes.some(name => !bodies.has(name))) throw new Error('CLIENT missing script');
  return { plan, bodies };
}
export async function run(directory, client) {
  const { plan, bodies } = await artifacts(directory), replies = [];
  for (const name of plan.invokes) {
    const script = bodies.get(name);
    replies.push(await client.invoke(script.body, script.sha1, script.keys));
  }
  if (plan.answer === -1) throw new Error('Client fault');
  return replyText(replies[plan.answer]);
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { process.stdout.write(await run(process.argv[2], new RedisClient(Number(process.env.TETHER_REDIS_PORT)))); }
  catch (error) { console.error(`TETHER ${error.message}`); process.exitCode = 4; }
}
