-- Test twin for the M0 GET/INCR surface, using decimal strings throughout.
local config = dofile(arg[1])
local values, output = config.values, nil
local function canonical(s)
  local negative = s:sub(1,1) == '-'
  local digits = negative and s:sub(2) or s
  local limit = negative and '9223372036854775808' or '9223372036854775807'
  return digits:match('^%d+$') and (#digits == 1 or digits:sub(1,1) ~= '0')
    and not (negative and digits == '0') and
    (#digits < #limit or (#digits == #limit and digits <= limit))
end
local function increment(s)
  if not canonical(s) then return nil, 'ERR value is not an integer or out of range' end
  if s == '9223372036854775807' then return nil, 'ERR increment or decrement would overflow' end
  local negative = s:sub(1,1) == '-'
  local digits, carry = negative and s:sub(2) or s, 1
  local out = {}
  for i = #digits, 1, -1 do
    local n = digits:byte(i) - 48 + (negative and -carry or carry)
    if n == 10 then n, carry = 0, 1 elseif n == -1 then n, carry = 9, 1 else carry = 0 end
    out[i] = string.char(48 + n)
  end
  local result = table.concat(out)
  if negative then
    result = result:gsub('^0+', '')
    return result == '' and '0' or '-' .. result
  end
  return (carry == 1 and '1' or '') .. result
end
local function call(command, key)
  if command == 'GET' then return values[key] or false end
  if command ~= 'INCR' then error('TWIN unsupported command') end
  local next, reason = increment(values[key] or '0')
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
if config.answer < 0 then error('Client fault') end
output = answers[config.answer + 1]
if output == false then io.write('\n')
elseif type(output) == 'string' then io.write(output, '\n')
elseif type(output) == 'table' and output.ok then io.write(output.ok, '\n')
else error('TWIN reply outside spine') end
