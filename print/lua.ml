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
  local b = {tag=0}
  for i = #s, 1, -1 do b = {tag=1, string.byte(s,i), b} end
  return b
end
local function text(b)
  local out = {}
  while b.tag == 1 do out[#out+1] = string.char(b[1]); b = b[2] end
  return table.concat(out)
end
local function key(k)
  local wanted = text(k[1])
  for i = 1, #KEYS do if KEYS[i] == wanted then return KEYS[i] end end
  error('LUA-KEY missing declared key')
end
local function clos(f,n,c) return {f=f,n=n,c=c} end
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
local function reply(r)
  if r.tag == 0 then return false end
  if r.tag == 1 then return text(r[1][1]) end
  if r.tag == 2 then return text(r[1]) end
  if r.tag == 3 then return {ok=text(r[1])} end
  if r.tag == 4 then return {err=text(r[1])} end
  if r.tag == 5 then
    local out, rs = {}, r[1]
    while rs.tag == 1 do out[#out+1] = reply(rs[1]); rs = rs[2] end
    return out
  end
  error('LUA-REPLY unsupported tag')
end
local function run(s)
  while s.tag ~= 0 do
    local k, r, next = key(s[1]), false, s[2]
    if s.tag == 1 or s.tag == 5 or s.tag == 6 then
      local changed
      if s.tag == 5 then changed = redis.pcall('INCRBY',k,text(s[2][1])); next = s[3]
      else changed = redis.pcall(s.tag == 1 and 'INCR' or 'DECR',k) end
      if type(changed) == 'table' and changed.err then r = {tag=4,bytes(changed.err)}
      else
        local read = redis.pcall('GET',k)
        if type(read) == 'table' and read.err then r = {tag=4,bytes(read.err)}
        elseif read == false then r = {tag=0}
        else r = {tag=1,{tag=0,bytes(read)}} end
      end
    elseif s.tag == 2 or s.tag == 3 or s.tag == 4 then
      local got
      if s.tag == 2 then got = redis.pcall('GET',k)
      else got = redis.pcall('SET',k,text(s.tag == 3 and s[2] or s[2][1])); next = s[3] end
      if type(got) == 'table' and got.err then r = {tag=4,bytes(got.err)}
      elseif type(got) == 'table' and got.ok then r = {tag=3,bytes(got.ok)}
      elseif got == false then r = {tag=0} else r = {tag=2,bytes(got)} end
    elseif s.tag == 7 or s.tag == 8 then
      local got = redis.pcall(s.tag == 7 and 'DEL' or 'EXISTS',k)
      if type(got) == 'table' and got.err then r = {tag=4,bytes(got.err)}
      elseif type(got) ~= 'number' then r = {tag=4,bytes('ERR key count reply is not an integer')}
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
    | E.KLit (Kanon_kernel.Literal.LInt n) ->
        let text = Kanon_kernel.Bignum.to_string n in
        if String.length text < 16 || (String.length text = 16 && text <= "9007199254740991")
        then Ok text else Error "LUA-NAT-RANGE use Signed64 bytes for Int64"
    | E.KGlobal name ->
        let* ps, _r, _b = lookup name in let* f = fname name in
        Ok (if ps = [] then f ^ "()" else Printf.sprintf "clos(%s,%d,{})" f (List.length ps))
    | E.KClos (E.Fid name, arity, captures) ->
        let* f = fname name in let* cs = many captures in
        Ok (Printf.sprintf "clos(%s,%d,{%s})" f arity cs)
    | E.KApp (f, args) | E.KTail (f, args) ->
        let* f = expr depth env f in let* args = many args in Ok ("app(" ^ f ^ ",{" ^ args ^ "})")
    | E.KStruct (_tid, fields) -> let* fields = many fields in Ok ("{" ^ fields ^ "}")
    | E.KTag (_tid, tag, fields) -> let* fields = many fields in
        Ok (Printf.sprintf "{tag=%d%s%s}" tag (if fields = "" then "" else ",") fields)
    | E.KProj (_tid, index, value) -> let* value = expr depth env value in
        Ok (Printf.sprintf "(%s)[%d]" value (index + 1))
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
