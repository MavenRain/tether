// Independent RESP2 parser for the REST twin. No Node host decoder imports.
const LIMIT = 8 * 1024 * 1024;
export class RestFault extends Error {}
export function decode(buffer) {
  if (buffer.length > LIMIT) throw new Error('REST reply limit');
  let cursor = 0;
  const text = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
  const parse = depth => {
    if (depth > 64) throw new Error('REST reply depth');
    const stop = buffer.indexOf('\r\n', cursor);
    if (stop < 0) return undefined;
    const kind = buffer[cursor++], field = text(buffer.subarray(cursor, stop));
    if (/[\r\n]/.test(field)) throw new Error('REST line terminator');
    cursor = stop + 2;
    switch (kind) {
      case 43: return field;
      case 45: return new RestFault(field);
      case 58: {
        if (!/^(0|-?[1-9][0-9]*)$/.test(field) || !Number.isSafeInteger(Number(field)))
          throw new Error('INTEGER-BOUNDARY expected bulk string');
        return Number(field);
      }
      case 36:
      case 42: {
        if (!/^(0|-?[1-9][0-9]*)$/.test(field)) throw new Error('REST length syntax');
        const count = Number(field);
        if (!Number.isSafeInteger(count) || count < -1 || count > LIMIT) throw new Error('REST length');
        if (count === -1) return null;
        if (kind === 36) {
          if (buffer.length - cursor < count + 2) return undefined;
          const value = text(buffer.subarray(cursor, cursor + count)); cursor += count;
          if (buffer[cursor++] !== 13 || buffer[cursor++] !== 10) throw new Error('REST bulk terminator');
          return value;
        }
        const values = [];
        for (let i = 0; i < count; i++) {
          const value = parse(depth + 1);
          if (value === undefined) return undefined;
          values.push(value);
        }
        return values;
      }
      default: throw new Error('REST unsupported RESP');
    }
  };
  const value = parse(0);
  return value === undefined ? null : { value, next: cursor };
}
export function envelope(value) {
  if (value instanceof RestFault) return { error: value.message };
  const check = value => {
    if (value instanceof RestFault) throw new Error('REST nested error reply');
    if (Array.isArray(value)) for (const item of value) check(item);
  };
  check(value);
  return { result: value };
}
