-- Independent test twin. Arithmetic uses decimal digits, never Lua integers.
local config = dofile(arg[1])
local values, output = config.values, nil
local set_kind = {}
local list_kind = {}
for key, members in pairs(config.sets or {}) do values[key] = {[set_kind]=members} end
for key, items in pairs(config.lists or {}) do values[key] = {[list_kind]=items} end
local function canonical(s)
  local negative = s:sub(1,1) == '-'
  local digits = negative and s:sub(2) or s
  local limit = negative and '9223372036854775808' or '9223372036854775807'
  return digits:match('^%d+$') and (#digits == 1 or digits:sub(1,1) ~= '0')
    and not (negative and digits == '0') and
    (#digits < #limit or (#digits == #limit and digits <= limit))
end
local function add(left, right)
  if not canonical(left) or not canonical(right) then
    return nil, 'ERR value is not an integer or out of range'
  end
  local ln, rn = left:sub(1,1) == '-', right:sub(1,1) == '-'
  local a, b = ln and left:sub(2) or left, rn and right:sub(2) or right
  local negative, subtract = ln, ln ~= rn
  if #a < #b or (#a == #b and a < b) then a, b, negative = b, a, rn end
  b = string.rep('0', #a - #b) .. b
  local carry = 0
  local out = {}
  for i = #a, 1, -1 do
    local x, y = a:byte(i) - 48, b:byte(i) - 48
    local n = subtract and (x - y - carry) or (x + y + carry)
    if n >= 10 then n, carry = n - 10, 1
    elseif n < 0 then n, carry = n + 10, 1 else carry = 0 end
    out[i] = string.char(48 + n)
  end
  local result = ((carry == 1 and '1' or '') .. table.concat(out)):gsub('^0+', '')
  result = result == '' and '0' or (negative and '-' or '') .. result
  if not canonical(result) then return nil, 'ERR increment or decrement would overflow' end
  return result
end
local function hash_call(command, key, field, value, ...)
  if command == 'HINCRBY' and not canonical(value) then
    return {err='ERR value is not an integer or out of range'}
  end
  if values[key] ~= nil and (type(values[key]) ~= 'table'
    or values[key][set_kind] ~= nil or values[key][list_kind] ~= nil) then
    return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
  end
  local fields = values[key] or {}
  if command == 'HMGET' then
    local requested, out = {field, value, ...}, {}
    for i, name in ipairs(requested) do out[i] = fields[name] or false end
    return out
  end
  if command == 'HGETALL' or command == 'HKEYS' or command == 'HVALS' then
    local keys, out = {}, {}
    for field in pairs(fields) do keys[#keys+1] = field end
    table.sort(keys)
    for i = #keys, 1, -1 do
      if command == 'HGETALL' then out[#out+1], out[#out+2] = keys[i], fields[keys[i]]
      else out[#out+1] = command == 'HKEYS' and keys[i] or fields[keys[i]] end
    end
    return out
  end
  if command == 'HGET' then return fields[field] or false end
  if command == 'HEXISTS' then return fields[field] ~= nil and 1 or 0 end
  if command == 'HSTRLEN' then return fields[field] and #fields[field] or 0 end
  if command == 'HLEN' then
    local count = 0
    for _ in pairs(fields) do count = count + 1 end
    return count
  end
  if command == 'HDEL' then
    local count = 0
    for _, name in ipairs({field, value, ...}) do
      if fields[name] ~= nil then fields[name], count = nil, count + 1 end
    end
    if next(fields) == nil then values[key] = nil end
    return count
  end
  if command == 'HSETNX' then
    if fields[field] ~= nil then return 0 end
    fields[field], values[key] = value, fields
    return 1
  end
  if command == 'HSET' then
    local items, count = {field, value, ...}, 0
    if #items % 2 ~= 0 then error('TWIN odd HSET argument count') end
    for i = 1, #items, 2 do
      if fields[items[i]] == nil then count = count + 1 end
      fields[items[i]] = items[i+1]
    end
    values[key] = fields
    return count
  end
  if command ~= 'HINCRBY' then error('TWIN unsupported hash command') end
  local old = fields[field] or '0'
  if not canonical(old) then return {err='ERR hash value is not an integer'} end
  local updated, reason = add(old, value)
  if not updated then return {err=reason} end
  fields[field], values[key] = updated, fields
  -- Redis answers the exact new value; the printed body reads it back with HGET.
  return updated
end
local function set_call(command, key, member, ...)
  local stored = values[key]
  if stored ~= nil and (type(stored) ~= 'table' or stored[set_kind] == nil) then
    return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
  end
  local members = stored and stored[set_kind] or {}
  if command == 'SUNION' or command == 'SINTER' or command == 'SDIFF' then
    local other = values[member]
    if other ~= nil and (type(other) ~= 'table' or other[set_kind] == nil) then
      return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
    end
    local right, out = other and other[set_kind] or {}, {}
    for value in pairs(members) do
      if command == 'SUNION' or (command == 'SINTER' and right[value])
        or (command == 'SDIFF' and not right[value]) then out[#out+1] = value end
    end
    if command == 'SUNION' then
      for value in pairs(right) do
        if not members[value] then out[#out+1] = value end
      end
    end
    table.sort(out, function(a,b) return a > b end)
    return out
  end
  if command == 'SMEMBERS' then
    local out = {}
    for member in pairs(members) do out[#out+1] = member end
    return out
  end
  if command == 'SISMEMBER' then return members[member] and 1 or 0 end
  if command == 'SCARD' then
    local count = 0
    for _ in pairs(members) do count = count + 1 end
    return count
  end
  if command == 'SADD' then
    local added = 0
    for _, item in ipairs({member, ...}) do
      if not members[item] then added = added + 1 end
      members[item] = true
    end
    values[key] = {[set_kind]=members}
    return added
  end
  if command ~= 'SREM' then error('TWIN unsupported set command') end
  local removed = 0
  for _, item in ipairs({member, ...}) do
    if members[item] then removed = removed + 1 end
    members[item] = nil
  end
  if next(members) == nil then values[key] = nil end
  return removed
end
local function list_offset(index, length)
  if not canonical(index) then return nil end
  local negative = index:sub(1,1) == '-'
  local digits = negative and index:sub(2) or index
  local limit = tostring(length)
  if #digits > #limit or (#digits == #limit and digits > limit) then
    return negative and -1 or length
  end
  -- Conversion is exact after bounding the magnitude by the list length.
  local n = tonumber(index)
  return n < 0 and length + n or n
end
local function list_call(command, key, value, extra, ...)
  if (command == 'LTRIM' or command == 'LRANGE') and (not canonical(value) or not canonical(extra)) then
    return {err='ERR value is not an integer or out of range'}
  end
  local stored = values[key]
  if stored ~= nil and (type(stored) ~= 'table' or stored[list_kind] == nil) then
    return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
  end
  local items = stored and stored[list_kind] or {}
  if command == 'LINDEX' or command == 'LSET' then
    if #items == 0 then
      if command == 'LINDEX' then return false end
      return {err='ERR no such key'}
    end
    local index = list_offset(value, #items)
    if not index then return {err='ERR value is not an integer or out of range'} end
    if command == 'LINDEX' then return items[index+1] or false end
    if index < 0 or index >= #items then return {err='ERR index out of range'} end
    items[index+1] = extra
    return {ok='OK'}
  end
  if command == 'LTRIM' or command == 'LRANGE' then
    local first, last = list_offset(value, #items), list_offset(extra, #items)
    local kept = {}
    for i = math.max(0, first), math.min(#items-1, last) do kept[#kept+1] = items[i+1] end
    if command == 'LRANGE' then return kept end
    values[key] = #kept > 0 and {[list_kind]=kept} or nil
    return {ok='OK'}
  end
  if command == 'LLEN' then return #items end
  if command == 'LPUSH' or command == 'RPUSH' or command == 'LPUSHX' or command == 'RPUSHX' then
    if (command == 'LPUSHX' or command == 'RPUSHX') and #items == 0 then return 0 end
    for _, item in ipairs({value, extra, ...}) do
      table.insert(items, (command == 'LPUSH' or command == 'LPUSHX') and 1 or #items + 1, item)
    end
    values[key] = {[list_kind]=items}
    return #items
  end
  if command ~= 'LPOP' and command ~= 'RPOP' then error('TWIN unsupported list command') end
  if #items == 0 then return false end
  local popped = table.remove(items, command == 'LPOP' and 1 or #items)
  if #items == 0 then values[key] = nil end
  return popped
end
local function data_call(command, key, amount, value, ...)
  if command == 'SMOVE' then
    local source, target = values[key], values[amount]
    if source == nil then return 0 end
    if type(source) ~= 'table' or source[set_kind] == nil
      or (target ~= nil and (type(target) ~= 'table' or target[set_kind] == nil)) then
      return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
    end
    local members = source[set_kind]
    if not members[value] then return 0 end
    if key == amount then return 1 end
    local destination = target and target[set_kind] or {}
    members[value], destination[value] = nil, true
    if next(members) == nil then values[key] = nil end
    values[amount] = {[set_kind]=destination}
    return 1
  end
  if command == 'SUNIONSTORE' or command == 'SINTERSTORE' or command == 'SDIFFSTORE' then
    local result = set_call(command:sub(1, -6), amount, value)
    if result.err then return result end
    local members = {}
    for _, member in ipairs(result) do members[member] = true end
    values[key] = #result > 0 and {[set_kind]=members} or nil
    return #result
  end
  if command:sub(1,1) == 'H' then return hash_call(command, key, amount, value, ...) end
  if command == 'SADD' or command == 'SREM' or command == 'SISMEMBER' or command == 'SCARD' or command == 'SMEMBERS'
    or command == 'SUNION' or command == 'SINTER' or command == 'SDIFF' then
    return set_call(command, key, amount, value, ...)
  end
  if command == 'LPUSH' or command == 'RPUSH' or command == 'LPUSHX' or command == 'RPUSHX' or command == 'LPOP' or command == 'RPOP' or command == 'LLEN'
    or command == 'LINDEX' or command == 'LSET' or command == 'LTRIM' or command == 'LRANGE' then
    return list_call(command, key, amount, value, ...)
  end
  if command == 'EXISTS' then return values[key] ~= nil and 1 or 0 end
  if command == 'DEL' then
    local count = values[key] ~= nil and 1 or 0
    values[key] = nil
    return count
  end
  if command == 'SET' then values[key] = amount; return {ok='OK'} end
  if values[key] ~= nil and type(values[key]) ~= 'string' then
    return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
  end
  if command == 'GET' then return values[key] or false end
  if command == 'INCR' then amount = '1'
  elseif command == 'DECR' then amount = '-1'
  elseif command ~= 'INCRBY' then error('TWIN unsupported command') end
  local next, reason = add(values[key] or '0', amount)
  if not next then return {err=reason} end
  values[key] = next
  -- The printed body discards this potentially rounded integer and does GET.
  return 0
end
local deadlines, now = config.deadlines or {}, config.now or '0'
local function before(a, b) return #a < #b or (#a == #b and a < b) end
local function advance(delta)
  if not canonical(delta) or delta:sub(1,1) == '-' then error('TWIN invalid clock step') end
  local next_time = add(now, delta)
  if not next_time then error('TWIN clock overflow') end
  now = next_time
  for key, deadline in pairs(deadlines) do
    if not canonical(deadline) or deadline:sub(1,1) == '-' then error('TWIN invalid deadline') end
    if before(deadline, now) then values[key], deadlines[key] = nil, nil end
  end
end
if not canonical(now) or now:sub(1,1) == '-' then error('TWIN invalid clock') end
local function call(command, key, amount, value, ...)
  if command == 'EXPIRE' or command == 'PEXPIRE' or command == 'EXPIREAT' or command == 'PEXPIREAT' then
    if not canonical(amount) then return {err='ERR value is not an integer or out of range'} end
    local duration = (command == 'EXPIRE' or command == 'EXPIREAT') and amount ~= '0' and amount .. '000' or amount
    local absolute = command == 'EXPIREAT' or command == 'PEXPIREAT'
    local deadline = canonical(duration) and add(absolute and '0' or now, duration)
    if not deadline then return {err="ERR invalid expire time in '" .. command:lower() .. "' command"} end
    if values[key] == nil then return 0 end
    local old = deadlines[key]
    local earlier = old ~= nil and (deadline:sub(1,1) == '-' or before(deadline, old))
    local later = old ~= nil and deadline:sub(1,1) ~= '-' and before(old, deadline)
    if (value == 'NX' and old ~= nil) or (value == 'XX' and old == nil)
      or (value == 'GT' and not later) or (value == 'LT' and old ~= nil and not earlier) then return 0 end
    if deadline:sub(1,1) == '-' or not before(now, deadline) then values[key], deadlines[key] = nil, nil
    else deadlines[key] = deadline end
    return 1
  end
  if command == 'TTL' or command == 'PTTL' or command == 'EXPIRETIME' or command == 'PEXPIRETIME' then
    if values[key] == nil then return -2 end
    if deadlines[key] == nil then return -1 end
    local absolute = command == 'EXPIRETIME' or command == 'PEXPIRETIME'
    local remaining = absolute and deadlines[key] or add(deadlines[key], now == '0' and '0' or '-' .. now)
    if command == 'TTL' or command == 'EXPIRETIME' then
      local whole = #remaining > 3 and remaining:sub(1,-4) or '0'
      remaining = add(whole, tonumber(remaining:sub(-3)) >= 500 and '1' or '0')
    end
    if not before(remaining, '9007199254740992') then return 9007199254740992 end
    return tonumber(remaining)
  end
  if command == 'PERSIST' then
    local changed = deadlines[key] ~= nil and 1 or 0
    deadlines[key] = nil
    return changed
  end
  local result = data_call(command, key, amount, value, ...)
  if not (type(result) == 'table' and result.err) and
    (command == 'SET' or command == 'SUNIONSTORE' or command == 'SINTERSTORE' or command == 'SDIFFSTORE') then
    deadlines[key] = nil
  end
  for expired in pairs(deadlines) do if values[expired] == nil then deadlines[expired] = nil end end
  return result
end
local function frozen(members)
  return setmetatable({}, {__index=function(_, key)
    local value = members[key]
    if value == nil then error('NO-GLOBALS read ' .. key) end
    return value
  end, __newindex=function(_, key) error('NO-GLOBALS write ' .. key) end})
end
local answers = {}
for i, invocation in ipairs(config.invokes) do
  advance(invocation.advance or '0')
  local chunk, reason = loadfile(invocation.path)
  if not chunk then error(reason) end
  setfenv(chunk, frozen({KEYS=invocation.keys, ARGV={}, string=string, table=table,
    math=math, unpack=unpack, type=type, error=error,
    redis=frozen({pcall=call, call=function(...)
      local value = call(...)
      if type(value) == 'table' and value.err then error(value.err) end
      return value
    end})}))
  local result = chunk()
  if type(result) == 'table' and result.err then error(result.err) end
  answers[i] = result
end
for key, expected in pairs(config.expiries or {}) do
  if (deadlines[key] or false) ~= expected then error('TWIN expiry mismatch: ' .. key) end
end
for _, check in ipairs(config.checks or {}) do
  local actual = values[check.key]
  if actual == nil then actual = false end
  if check.kind == 'hash' then
    if type(actual) ~= 'table' or actual[set_kind] ~= nil or actual[list_kind] ~= nil then
      error('TWIN expected hash: ' .. check.key)
    end
    if check.fields then
      for field, value in pairs(check.fields) do
        if actual[field] ~= value then error('TWIN hash field mismatch') end
      end
      for field in pairs(actual) do
        if check.fields[field] == nil then error('TWIN unexpected hash field') end
      end
    end
  elseif check.kind == 'set' then
    if type(actual) ~= 'table' or actual[set_kind] == nil then error('TWIN expected set') end
    local members = actual[set_kind]
    for member in pairs(check.members) do
      if not members[member] then error('TWIN missing member') end
    end
    for member in pairs(members) do
      if not check.members[member] then error('TWIN unexpected member') end
    end
  elseif check.kind == 'list' then
    if type(actual) ~= 'table' or actual[list_kind] == nil then error('TWIN expected list') end
    local items = actual[list_kind]
    if #items ~= #check.items then error('TWIN list length mismatch') end
    for i, item in ipairs(check.items) do
      if items[i] ~= item then error('TWIN list order mismatch') end
    end
  elseif actual ~= check.value then error('TWIN stored value mismatch: ' .. check.key) end
end
if config.answer < 0 then error('Client fault') end
output = answers[config.answer + 1]
-- An int reply reaches this twin as a string, so 'string' covers int and bulk.
local function kind_of(value)
  if value == false or value == nil then return 'nil' end
  if type(value) == 'string' then return 'string' end
  if type(value) ~= 'table' then return 'other' end
  if value.ok then return 'status' end
  if value.err then return 'err' end
  return 'array'
end
if config.kind and kind_of(output) ~= config.kind then
  error('TWIN reply kind ' .. kind_of(output) .. ' wanted ' .. config.kind)
end
local function encode(value)
  local function hex(s) return (s:gsub('.', function(c) return string.format('%02x', string.byte(c)) end)) end
  if value == false then return 'null' end
  if type(value) == 'string' then return 'bulk:' .. hex(value) end
  if type(value) ~= 'table' then error('TWIN unsupported reply') end
  if value.ok then return 'status:' .. hex(value.ok) end
  if value.err then return 'error:' .. hex(value.err) end
  local encoded = {}
  for _, item in ipairs(value) do encoded[#encoded+1] = encode(item) end
  return 'array:[' .. table.concat(encoded, ',') .. ']'
end
if config.reply then io.write(encode(output), '\n')
elseif output == false then io.write('\n')
elseif type(output) == 'string' then io.write(output, '\n')
elseif type(output) == 'table' and output.ok then io.write(output.ok, '\n')
elseif type(output) == 'table' then
  io.write(encode(output), '\n')
else error('TWIN reply outside spine') end
