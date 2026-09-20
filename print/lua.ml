module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let all xs = List.fold_right (fun x acc -> let* x = x in let* xs = acc in Ok (x :: xs)) xs (Ok [])
let quote_bytes ns = "\"" ^ String.concat "" (List.map (Printf.sprintf "\\%03d") ns) ^ "\""
let quote s = quote_bytes (List.of_seq (Seq.map Char.code (String.to_seq s)))
type artifact = { body : string; sha1 : string; no_writes : bool; keys : int list list }
let rec literal_bytes = function
  | E.KTag (E.Tid "mu<Bytes>", 0, []) -> Some []
  | E.KTag (E.Tid "mu<Bytes>", 1, [E.KLit (Kanon_kernel.Literal.LInt n); tail]) ->
      Option.bind (int_of_string_opt (Kanon_kernel.Bignum.to_string n)) (fun n ->
        if n < 0 || n > 255 then None else Option.map (List.cons n) (literal_bytes tail))
  | E.KVar _ | E.KLit _ | E.KGlobal _ | E.KErased | E.KLet _ | E.KClos _
  | E.KApp _ | E.KTail _ | E.KStruct _ | E.KProj _ | E.KTag _ | E.KCase _
  | E.KDelay _ | E.KForce _ -> None
let runtime = {|local function bytes(s)
  local b = {tag=0}; for i = #s, 1, -1 do b = {tag=1, string.byte(s,i), b} end
  return b end
local function text(b) local out = {}; while b.tag == 1 do out[#out+1] = string.char(b[1]); b = b[2] end
  return table.concat(out) end
local function key(k)
  local wanted = text(k[1]); for i = 1, #KEYS do if KEYS[i] == wanted then return KEYS[i] end end
  error('LUA-KEY missing declared key')
end
local function clos(f,n,c) return {f=f,n=n,c=c} end
local function bulkargs(xs,tail) for i = #xs, 1, -1 do tail = {tag=1,xs[i],tail} end; return tail end
local function bulkpairs(xs,tail) if #xs % 2 ~= 0 then error('LUA-PAIRS odd head') end for i = #xs - 1, 1, -2 do tail = {tag=1,xs[i],xs[i+1],tail} end; return tail end
local function app(f,args)
  local values = {}
  for i = 1, #f.c do values[#values+1] = f.c[i] end
  for i = 1, math.min(#args,f.n) do values[#values+1] = args[i] end
  if #args < f.n then return clos(f.f,f.n-#args,values) end
  if #args == f.n then return f.f(unpack(values)) end
  local rest = {}
  for i = f.n+1, #args do rest[#rest+1] = args[i] end
  return app(f.f(unpack(values)),rest)
end
local function reply(r) if r.tag == 0 then return false end
  if r.tag == 1 or r.tag == 2 then return text(r.tag == 1 and r[1][1] or r[1]) end
  if r.tag == 3 then return {ok=text(r[1])} end
  if r.tag == 4 then return {err=text(r[1])} end
  if r.tag == 5 then
    local out, rs = {}, r[1]
    while rs.tag == 1 do out[#out+1] = reply(rs[1]); rs = rs[2] end
    return out
  end
  error('LUA-REPLY unsupported tag')
end
local function byte_less(a,b) for i = 1, math.min(#a,#b) do
    local x,y = string.byte(a,i),string.byte(b,i); if x ~= y then return x < y end
  end; return #a < #b
end
local function run(s) while s.tag ~= 0 do
    local k, r, next = key(s[1]), false, s[2]
    if s.tag == 1 or s.tag == 5 or s.tag == 6 or s.tag == 14 then
      local changed; if s.tag == 14 then changed = redis.pcall('HINCRBY',k,text(s[2]),text(s[3][1])); next = s[4]
      elseif s.tag == 5 then changed = redis.pcall('INCRBY',k,text(s[2][1])); next = s[3]
      else changed = redis.pcall(s.tag == 1 and 'INCR' or 'DECR',k) end
      if type(changed) == 'table' and changed.err then r = {tag=4,bytes(changed.err)}
      else local read; if s.tag == 14 then read = redis.pcall('HGET',k,text(s[2])) else read = redis.pcall('GET',k) end
        if type(read) == 'table' and read.err then r = {tag=4,bytes(read.err)}
        elseif read == false then r = {tag=0}
        else r = {tag=1,{tag=0,bytes(read)}} end
      end
    elseif s.tag == 2 or s.tag == 3 or s.tag == 4 or s.tag == 10 or s.tag == 21 or s.tag == 22 or (s.tag >= 24 and s.tag <= 34) or s.tag == 52 or s.tag == 68 then
      local got; if s.tag == 10 then got = redis.pcall('HGET',k,text(s[2])); next = s[3]
      elseif s.tag == 2 then got = redis.pcall('GET',k)
      elseif s.tag == 52 then local args, fs = {k}, s[2]; while fs.tag == 1 do args[#args+1], fs = text(fs[1]), fs[2] end; args[#args+1] = text(fs[1]); got = redis.pcall('HMGET',unpack(args)); next = s[3]
      elseif s.tag >= 28 and s.tag <= 34 then
        local args = {k}; if s.tag >= 32 then args[2], next = key(s[2]), s[3] end
        got = redis.pcall(({[28]='SMEMBERS',[29]='HGETALL',[30]='HKEYS',[31]='HVALS',[32]='SUNION',[33]='SINTER',[34]='SDIFF'})[s.tag],unpack(args))
      elseif s.tag == 21 or s.tag == 22 then got = redis.pcall(s.tag == 21 and 'LPOP' or 'RPOP',k)
      elseif s.tag == 68 then got = redis.pcall('LMOVE',k,key(s[2]),s[3].tag == 0 and 'LEFT' or 'RIGHT',s[4].tag == 0 and 'LEFT' or 'RIGHT'); next = s[5]
      elseif s.tag == 24 then got = redis.pcall('LINDEX',k,text(s[2][1])); next = s[3]
      elseif s.tag == 25 then got = redis.pcall('LSET',k,text(s[2][1]),text(s[3])); next = s[4]
      elseif s.tag == 26 or s.tag == 27 then got = redis.pcall(s.tag == 26 and 'LTRIM' or 'LRANGE',k,text(s[2][1]),text(s[3][1])); next = s[4]
      else got = redis.pcall('SET',k,text(s.tag == 3 and s[2] or s[2][1])); next = s[3] end
      if type(got) == 'table' and got.err then r = {tag=4,bytes(got.err)} elseif type(got) == 'table' and got.ok then r = {tag=3,bytes(got.ok)}
      elseif (s.tag >= 27 and s.tag <= 34) or s.tag == 52 then
        local stride, order = s.tag == 29 and 2 or 1, {}; for i = 1, #got, stride do order[#order+1] = i end
        if s.tag ~= 27 and s.tag ~= 52 then table.sort(order,function(a,b) return byte_less(got[a],got[b]) end) end
        local rs = {tag=0}; for n = #order, 1, -1 do for i = order[n]+stride-1, order[n], -1 do rs = {tag=1,got[i] == false and {tag=0} or {tag=2,bytes(got[i])},rs} end end; r = {tag=5,rs}
      elseif got == false then r = {tag=0} else r = {tag=2,bytes(got)} end
    elseif (s.tag >= 7 and s.tag <= 13) or (s.tag >= 15 and s.tag <= 20) or s.tag == 23 or (s.tag >= 35 and s.tag <= 51) or (s.tag >= 53 and s.tag <= 67) then
      local got; if s.tag == 9 or s.tag == 59 then got = redis.pcall(s.tag == 59 and 'HSETNX' or 'HSET',k,text(s[2]),text(s[3])); next = s[4]
      elseif s.tag == 58 then local args, ps = {k}, s[2]; while ps.tag == 1 do args[#args+1], args[#args+2], ps = text(ps[1]), text(ps[2]), ps[3] end; args[#args+1], args[#args+2] = text(ps[1]), text(ps[2]); got = redis.pcall('HSET',unpack(args)); next = s[3]
      elseif s.tag == 65 then got = redis.pcall('LREM',k,text(s[2][1]),text(s[3])); next = s[4]
      elseif s.tag == 66 or s.tag == 67 then got = redis.pcall('LINSERT',k,s.tag == 66 and 'BEFORE' or 'AFTER',text(s[2]),text(s[3])); next = s[4]
      elseif (s.tag >= 53 and s.tag <= 57) or s.tag == 63 or s.tag == 64 then local args, vs = {k}, s[2]; while vs.tag == 1 do args[#args+1], vs = text(vs[1]), vs[2] end; args[#args+1] = text(vs[1]); got = redis.pcall(({[53]='LPUSH',[54]='RPUSH',[55]='SADD',[56]='SREM',[57]='HDEL',[63]='LPUSHX',[64]='RPUSHX'})[s.tag],unpack(args)); next = s[3]
      elseif s.tag >= 39 and s.tag <= 51 then
        local args = {k}; if s.tag <= 40 or s.tag == 44 or s.tag == 45 or s.tag >= 48 then args[2], next = text(s[2][1]), s[3] end
        if s.tag >= 48 then args[3], next = ({[0]='NX',[1]='XX',[2]='GT',[3]='LT'})[s[3].tag], s[4] end
        got = redis.pcall(({[39]='EXPIRE',[40]='PEXPIRE',[41]='TTL',[42]='PTTL',[43]='PERSIST',[44]='EXPIREAT',[45]='PEXPIREAT',[46]='EXPIRETIME',[47]='PEXPIRETIME',[48]='EXPIRE',[49]='PEXPIRE',[50]='EXPIREAT',[51]='PEXPIREAT'})[s.tag],unpack(args))
      elseif s.tag >= 35 and s.tag <= 38 then
        got = redis.pcall(({[35]='SUNIONSTORE',[36]='SINTERSTORE',[37]='SDIFFSTORE',[38]='SMOVE'})[s.tag],k,key(s[2]),s.tag == 38 and text(s[3]) or key(s[3])); next = s[4]
      elseif s.tag == 11 or s.tag == 12 or s.tag == 60 then
        got = redis.pcall(s.tag == 60 and 'HSTRLEN' or (s.tag == 11 and 'HDEL' or 'HEXISTS'),k,text(s[2])); next = s[3]
      elseif s.tag == 13 or s.tag == 18 or s.tag == 23 then got = redis.pcall(s.tag == 13 and 'HLEN' or (s.tag == 18 and 'SCARD' or 'LLEN'),k)
      elseif s.tag == 15 or s.tag == 16 or s.tag == 17 then
        got = redis.pcall(s.tag == 15 and 'SADD' or (s.tag == 16 and 'SREM' or 'SISMEMBER'),k,text(s[2])); next = s[3]
      elseif s.tag == 19 or s.tag == 20 or s.tag == 61 or s.tag == 62 then got = redis.pcall(({[19]='LPUSH',[20]='RPUSH',[61]='LPUSHX',[62]='RPUSHX'})[s.tag],k,text(s[2])); next = s[3]
      else got = redis.pcall(s.tag == 7 and 'DEL' or 'EXISTS',k) end
      if type(got) == 'table' and got.err then r = {tag=4,bytes(got.err)}
      elseif s.tag >= 39 and s.tag <= 51 and (type(got) ~= 'number' or got >= 9007199254740992 or got < -2 or got ~= math.floor(got)) then r = {tag=4,bytes('ERR expiry reply is outside exact integer range')}
      elseif type(got) ~= 'number' then local what = s.tag == 65 and 'removed count' or (s.tag == 7 or s.tag == 8) and 'key count' or ((s.tag == 17 or s.tag == 38) and 'membership'
          or (s.tag >= 61 and 'list length' or (s.tag == 60 and 'field length' or (s.tag >= 57 and 'field count' or (((s.tag >= 35 and s.tag <= 37) or s.tag >= 55) and 'member count' or (s.tag >= 19 and 'list length' or (s.tag >= 15 and 'member count' or 'field count')))))))
        r = {tag=4,bytes('ERR ' .. what .. ' reply is not an integer')}
      else r = {tag=1,{tag=0,bytes(string.format('%d',got))}} end
    else error('LUA-SCRIPT unsupported tag') end
    s = app(next,{r})
  end
  return reply(s[1])
end|}
let emit rows ~entry =
  let* functions = Flags.reachable rows entry in
  let lookup name = List.assoc_opt name functions |> Option.to_result ~none:("LUA-GLOBAL " ^ name) in
  let* params, repr, _body = lookup entry in
  let* () = if params = [] && repr = E.RUnion (E.Tid "mu<Script>") then Ok ()
    else Error "LUA-ENTRY expected a closed Script Reply" in
  let names = List.mapi (fun i (name, _) -> name, "f" ^ string_of_int i) functions in
  let fname name = List.assoc_opt name names |> Option.to_result ~none:("LUA-GLOBAL " ^ name) in
  let rec expr depth env term =
    let many xs = all (List.map (expr depth env) xs) |> Result.map (String.concat ",") in
    let ordinary () = match term with
    | E.KVar i -> Kanon_kernel.Rules.at i env |> Option.to_result ~none:"LUA-VAR"
    | E.KErased -> Ok "false"
    | E.KLit (Kanon_kernel.Literal.LString s) -> Ok (quote s)
    | E.KLit (Kanon_kernel.Literal.LInt n) -> let text = Kanon_kernel.Bignum.to_string n in
        if String.length text < 16 || (String.length text = 16 && text <= "9007199254740991")
        then Ok text else Error "LUA-NAT-RANGE use Signed64 bytes for Int64"
    | E.KGlobal name -> let* ps, _r, _b = lookup name in let* f = fname name in
        Ok (if ps = [] then f ^ "()" else Printf.sprintf "clos(%s,%d,{})" f (List.length ps))
    | E.KClos (E.Fid name, arity, captures) -> let* f = fname name in let* cs = many captures in
        Ok (Printf.sprintf "clos(%s,%d,{%s})" f arity cs)
    | E.KApp (f, args) | E.KTail (f, args) ->
        let* f = expr depth env f in let* args = many args in Ok ("app(" ^ f ^ ",{" ^ args ^ "})")
    | E.KStruct (_tid, fields) -> let* fields = many fields in Ok ("{" ^ fields ^ "}")
    (* Flat constructor spines avoid Redis Lua's expression nesting limit. *)
    | E.KTag (E.Tid "mu<BulkArgs>", 1, [head; tail]) ->
        let rec collect acc = function E.KTag (E.Tid "mu<BulkArgs>", 1, [head; tail]) -> collect (head :: acc) tail
          | (E.KVar _ | E.KLit _ | E.KErased | E.KGlobal _ | E.KClos _ | E.KApp _ | E.KTail _ | E.KStruct _ | E.KTag _ | E.KProj _ | E.KLet _ | E.KCase _ | E.KDelay _ | E.KForce _) as tail -> List.rev acc, tail in
        let heads, tail = collect [head] tail in let* heads = many heads in let* tail = expr depth env tail in Ok ("bulkargs({" ^ heads ^ "}," ^ tail ^ ")")
    | E.KTag (E.Tid "mu<BulkPairs>", 1, [field; value; tail]) ->
        let rec collect acc = function E.KTag (E.Tid "mu<BulkPairs>", 1, [f; v; tail]) -> collect (v :: f :: acc) tail
          | (E.KVar _ | E.KLit _ | E.KErased | E.KGlobal _ | E.KClos _ | E.KApp _ | E.KTail _ | E.KStruct _ | E.KTag _ | E.KProj _ | E.KLet _ | E.KCase _ | E.KDelay _ | E.KForce _) as tail -> List.rev acc, tail in let heads, tail = collect [value; field] tail in let* heads = many heads in let* tail = expr depth env tail in Ok ("bulkpairs({" ^ heads ^ "}," ^ tail ^ ")")
    | E.KTag (_tid, tag, fields) -> let* fields = many fields in Ok (Printf.sprintf "{tag=%d%s%s}" tag (if fields = "" then "" else ",") fields)
    | E.KProj (_tid, index, value) -> let* value = expr depth env value in Ok (Printf.sprintf "(%s)[%d]" value (index + 1))
    | E.KLet (_name, value, body) ->
        let name = "v" ^ string_of_int depth in
        let* value = expr depth env value in let* body = expr (depth + 1) (name :: env) body in
        Ok ("(function(" ^ name ^ ") return " ^ body ^ " end)(" ^ value ^ ")")
    | E.KCase (_tid, value, branches) ->
        let name = "s" ^ string_of_int depth in let* value = expr depth env value in
        let* arms = all (List.map (fun (b : E.kbranch) ->
          let payload = List.init b.arity (fun i -> Printf.sprintf "%s[%d]" name (i + 1)) in
          let* body = expr (depth + 1) (List.rev payload @ env) b.body in
          Ok (Printf.sprintf "if %s.tag == %d then return %s end" name b.tag body)) branches) in
        Ok ("(function(" ^ name ^ ") " ^ String.concat " " arms ^
          " error('LUA-CASE uncovered tag') end)(" ^ value ^ ")")
    | E.KDelay _ | E.KForce _ -> Error "LUA-UNSUPPORTED delayed computation" in
    Option.fold ~none:ordinary ~some:(fun ns () -> Ok ("bytes(" ^ quote_bytes ns ^ ")"))
      (literal_bytes term) () in
  let* definitions = all (List.map (fun (name, (ps, _r, body)) ->
    let* f = fname name in let params = List.mapi (fun i _p -> "p" ^ string_of_int i) ps in
    let* body = expr 0 (List.rev params) body in
    Ok (f ^ " = function(" ^ String.concat "," params ^ ") return " ^ body ^ " end")) functions) in
  let keys = List.concat_map (fun (_, (_, _, body)) -> List.filter_map (function
    | E.KTag (E.Tid "mu<Key>", 0, [key]) -> literal_bytes key
    | E.KVar _ | E.KLit _ | E.KGlobal _ | E.KErased | E.KLet _ | E.KClos _
    | E.KApp _ | E.KTail _ | E.KStruct _ | E.KProj _ | E.KTag _ | E.KCase _
    | E.KDelay _ | E.KForce _ -> None) (Flags.terms body)) functions
    |> List.sort_uniq compare in
  let no_writes = Flags.no_writes functions in
  let* entry = fname entry in
  let header = if no_writes then "#!lua flags=no-writes\n" else "#!lua\n" in
  let body = header ^ runtime ^ "\nlocal " ^ String.concat "," (List.map snd names) ^ "\n" ^
    String.concat "\n" definitions ^ "\nreturn run(" ^ entry ^ "())" in
  let* sha1 = Sha1.digest body in Ok { body; sha1; no_writes; keys }
