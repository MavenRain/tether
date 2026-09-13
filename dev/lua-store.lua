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
local function hash_call(command, key, field, value)
  if command == 'HINCRBY' and not canonical(value) then
    return {err='ERR value is not an integer or out of range'}
  end
  if values[key] ~= nil and (type(values[key]) ~= 'table'
    or values[key][set_kind] ~= nil or values[key][list_kind] ~= nil) then
    return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
  end
  local fields = values[key] or {}
  if command == 'HGET' then return fields[field] or false end
  if command == 'HEXISTS' then return fields[field] ~= nil and 1 or 0 end
  if command == 'HLEN' then
    local count = 0
    for _ in pairs(fields) do count = count + 1 end
    return count
  end
  if command == 'HDEL' then
    local count = fields[field] ~= nil and 1 or 0
    fields[field] = nil
    if next(fields) == nil then values[key] = nil end
    return count
  end
  if command == 'HSET' then
    local count = fields[field] ~= nil and 0 or 1
    fields[field], values[key] = value, fields
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
local function set_call(command, key, member)
  local stored = values[key]
  if stored ~= nil and (type(stored) ~= 'table' or stored[set_kind] == nil) then
    return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
  end
  local members = stored and stored[set_kind] or {}
  if command == 'SISMEMBER' then return members[member] and 1 or 0 end
  if command == 'SCARD' then
    local count = 0
    for _ in pairs(members) do count = count + 1 end
    return count
  end
  if command == 'SADD' then
    local added = members[member] and 0 or 1
    members[member], values[key] = true, {[set_kind]=members}
    return added
  end
  if command ~= 'SREM' then error('TWIN unsupported set command') end
  local removed = members[member] and 1 or 0
  members[member] = nil
  if next(members) == nil then values[key] = nil end
  return removed
end
local function list_call(command, key, value)
  local stored = values[key]
  if stored ~= nil and (type(stored) ~= 'table' or stored[list_kind] == nil) then
    return {err='WRONGTYPE Operation against a key holding the wrong kind of value'}
  end
  local items = stored and stored[list_kind] or {}
  if command == 'LLEN' then return #items end
  if command == 'LPUSH' or command == 'RPUSH' then
    table.insert(items, command == 'LPUSH' and 1 or #items + 1, value)
    values[key] = {[list_kind]=items}
    return #items
  end
  if command ~= 'LPOP' and command ~= 'RPOP' then error('TWIN unsupported list command') end
  if #items == 0 then return false end
  local popped = table.remove(items, command == 'LPOP' and 1 or #items)
  if #items == 0 then values[key] = nil end
  return popped
end
local function call(command, key, amount, value)
  if command:sub(1,1) == 'H' then return hash_call(command, key, amount, value) end
  if command == 'SADD' or command == 'SREM' or command == 'SISMEMBER' or command == 'SCARD' then
    return set_call(command, key, amount)
  end
  if command == 'LPUSH' or command == 'RPUSH' or command == 'LPOP' or command == 'RPOP' or command == 'LLEN' then
    return list_call(command, key, amount)
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
local function frozen(members)
  return setmetatable({}, {__index=function(_, key)
    local value = members[key]
    if value == nil then error('NO-GLOBALS read ' .. key) end
    return value
  end, __newindex=function(_, key) error('NO-GLOBALS write ' .. key) end})
end
local answers = {}
for i, invocation in ipairs(config.invokes) do
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
if output == false then io.write('\n')
elseif type(output) == 'string' then io.write(output, '\n')
elseif type(output) == 'table' and output.ok then io.write(output.ok, '\n')
else error('TWIN reply outside spine') end
