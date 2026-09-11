local body, config = arg[1], dofile(arg[2])
local calls = {}
local value = config.value
local function invoke(command, key)
  calls[#calls+1] = command
  if key ~= config.keys[1] then error('WRONG-KEY') end
  if command == 'GET' then
    if config.getFault then return {err=config.getFault} end
    return value or false
  end
  if command == 'INCR' then
    if config.fault then return {err=config.fault} end
    value = config.next
    return 9007199254740992
  end
  error('UNEXPECTED-COMMAND')
end
-- Real Redis returns the error table from redis.pcall and raises a Lua error
-- from redis.call. The twin keeps the two entry points apart.
local function protected(command, key) return invoke(command, key) end
local function unprotected(command, key)
  local answer = invoke(command, key)
  if type(answer) == 'table' and answer.err then error(answer.err) end
  return answer
end
-- A frozen table stays empty, so every read and every write reaches the
-- metatable, including the names the sandbox binds.
local function frozen(members, label)
  return setmetatable({}, {
    __index=function(_, name)
      local bound = members[name]
      if bound == nil then error('NO-GLOBALS read '..label..name) end
      return bound
    end,
    __newindex=function(_, name) error('NO-GLOBALS write '..label..name) end
  })
end
local environment = frozen({KEYS=config.keys, ARGV={}, string=string, table=table,
  math=math, unpack=unpack, type=type, error=error,
  redis=frozen({call=unprotected, pcall=protected}, 'redis.')}, '')
local chunk, reason = loadfile(body)
if not chunk then error('LUA-SYNTAX '..reason) end
setfenv(chunk, environment)
local function hex(s)
  return (s:gsub('.', function(c) return string.format('%02x',string.byte(c)) end))
end
local function encode(r)
  if r == false then return 'nil' end
  if type(r) == 'string' then return 'bulk:'..hex(r) end
  if type(r) ~= 'table' then error('INTEGER-BOUNDARY numeric reply') end
  if r.ok then return 'status:'..hex(r.ok) end
  if r.err then return 'err:'..hex(r.err) end
  local items = {}
  for i=1,#r do items[#items+1] = encode(r[i]) end
  return 'array:['..table.concat(items,',')..']'
end
print(encode(chunk()))
print('CALLS '..table.concat(calls,','))
