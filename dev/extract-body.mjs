import { readFile } from 'node:fs/promises';
const [path, name = 'requestBody'] = process.argv.slice(2);
const { instance } = await WebAssembly.instantiate(await readFile(path));
const api = instance.exports;
let cursor = api[name]();
const bytes = [];
while (api.bytesEmpty(cursor) === 0) {
  const byte = api.bytesHead(cursor);
  if (!Number.isInteger(byte) || byte < 0 || byte > 255) throw new Error('WASM-BYTE');
  bytes.push(byte);
  cursor = api.bytesTail(cursor);
  if (bytes.length > 1048576) throw new Error('WASM-BODY-SIZE');
}
process.stdout.write(Buffer.from(bytes));
