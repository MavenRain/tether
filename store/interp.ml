module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
type value = Data of E.tid * int * value list | Fields of value list
  | Literal of Kanon_kernel.Literal.t | Closure of string * int * value list | Erased
type reply = Nil | Int of string | Bulk of string | Status of string | Err of string | Array of reply list
type operand = Octets of string | Signed of string | KeyName of string | Condition of Store.expiry_condition | BulkFields of string * string list
let all xs = List.fold_right (fun x acc -> let* x = x in let* xs = acc in Ok (x :: xs)) xs (Ok [])
let data name tag xs = Data (E.Tid ("mu<" ^ name ^ ">"), tag, xs)
let octets = "\000\001\002\003\004\005\006\007\008\009\010\011\012\013\014\015\016\017\018\019\020\021\022\023\024\025\026\027\028\029\030\031\032\033\034\035\036\037\038\039\040\041\042\043\044\045\046\047\048\049\050\051\052\053\054\055\056\057\058\059\060\061\062\063\064\065\066\067\068\069\070\071\072\073\074\075\076\077\078\079\080\081\082\083\084\085\086\087\088\089\090\091\092\093\094\095\096\097\098\099\100\101\102\103\104\105\106\107\108\109\110\111\112\113\114\115\116\117\118\119\120\121\122\123\124\125\126\127\128\129\130\131\132\133\134\135\136\137\138\139\140\141\142\143\144\145\146\147\148\149\150\151\152\153\154\155\156\157\158\159\160\161\162\163\164\165\166\167\168\169\170\171\172\173\174\175\176\177\178\179\180\181\182\183\184\185\186\187\188\189\190\191\192\193\194\195\196\197\198\199\200\201\202\203\204\205\206\207\208\209\210\211\212\213\214\215\216\217\218\219\220\221\222\223\224\225\226\227\228\229\230\231\232\233\234\235\236\237\238\239\240\241\242\243\244\245\246\247\248\249\250\251\252\253\254\255"
let bytes text = List.fold_right (fun c tail -> data "Bytes" 1 [Literal (Kanon_kernel.Literal.LInt (Kanon_kernel.Bignum.of_int (Char.code c))); tail])
  (List.of_seq (String.to_seq text)) (data "Bytes" 0 [])
let rec text = function
  | Data (E.Tid "mu<Bytes>", 0, []) -> Ok ""
  | Data (E.Tid "mu<Bytes>", 1, [Literal (Kanon_kernel.Literal.LInt n); tail]) -> let* byte = int_of_string_opt (Kanon_kernel.Bignum.to_string n) |> Option.to_result ~none:"STORE-BYTE" in
      let* c = Seq.find (fun c -> Char.code c = byte) (String.to_seq octets) |> Option.to_result ~none:"STORE-BYTE" in
      let* tail = text tail in Ok (String.make 1 c ^ tail)
  | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-BYTES"
let rec bulk_args = function
  | Data (E.Tid "mu<BulkArgs>", 0, [b]) -> let* b = text b in Ok (b, [])
  | Data (E.Tid "mu<BulkArgs>", 1, [b; rest]) -> let* b = text b in let* first, rest = bulk_args rest in Ok (b, first :: rest)
  | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-BULK-ARGS"
let operand = function
  | (Data (E.Tid "mu<BulkArgs>", _, _) as args) -> Result.map (fun (first, rest) -> BulkFields (first, rest)) (bulk_args args)
  | Data (E.Tid "mu<Signed64>", 0, [b]) -> Result.map (fun s -> Signed s) (text b)
  | Data (E.Tid "mu<Key>", 0, [b]) -> Result.map (fun s -> KeyName s) (text b)
  | Data (E.Tid "mu<ExpiryCondition>", tag, []) -> List.assoc_opt tag [0, Store.NX; 1, Store.XX; 2, Store.GT; 3, Store.LT] |> Option.to_result ~none:"STORE-EXPIRY-CONDITION" |> Result.map (fun c -> Condition c)
  | (Data _ | Fields _ | Literal _ | Closure _ | Erased) as b -> Result.map (fun s -> Octets s) (text b)
let rec reply = function
  | Data (E.Tid "mu<Reply>", 0, []) -> Ok Nil
  | Data (E.Tid "mu<Reply>", 1, [Data (E.Tid "mu<Signed64>", 0, [b])]) -> let* s = text b in Store.integer s |> Result.map_error Store.message |> Result.map (fun _ -> Int s)
  | Data (E.Tid "mu<Reply>", (2 | 3 | 4 as tag), [b]) -> let* s = text b in Ok (if tag = 2 then Bulk s else if tag = 3 then Status s else Err s)
  | Data (E.Tid "mu<Reply>", 5, [rs]) -> let* rs = replies rs in Ok (Array rs)
  | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-REPLY"
and replies = function | Data (E.Tid "mu<Replies>", 0, []) -> Ok []
  | Data (E.Tid "mu<Replies>", 1, [r; rs]) -> let* r = reply r in let* rs = replies rs in Ok (r :: rs)
  | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-REPLIES"
let run ~budget rows ~entry store =
  let functions = List.concat_map (fun (_name, entry) -> match entry with
    | Kanon_kernel.Erase.Dropped | Kanon_kernel.Erase.Postulate _ -> []
    | Kanon_kernel.Erase.Code ds -> List.filter_map (function E.KFun (E.Fid n, ps, _r, body) -> Some (n, (ps, body))
        | E.KRec _ -> None) ds) rows in
  let lookup name = List.assoc_opt name functions |> Option.to_result ~none:("STORE-GLOBAL " ^ name) in
  let poll () = if Kanon_kernel.Budget.exhausted budget then Error "STORE-BUDGET" else Ok () in
  let rec eval env term = let* () = poll () in
    let many xs = all (List.map (eval env) xs) in match term with
    | E.KVar i -> Kanon_kernel.Rules.at i env |> Option.to_result ~none:"STORE-VAR"
    | E.KLit l -> Ok (Literal l) | E.KErased -> Ok Erased
    | E.KGlobal n -> let* ps, b = lookup n in if ps = [] then eval [] b else Ok (Closure (n, List.length ps, []))
    | E.KClos (E.Fid n, arity, xs) -> let* xs = many xs in Ok (Closure (n, arity, xs))
    | E.KApp (f, xs) | E.KTail (f, xs) -> let* f = eval env f in let* xs = many xs in apply f xs
    | E.KLet (_n, x, b) -> let* x = eval env x in eval (x :: env) b
    | E.KTag (tid, tag, xs) -> let* xs = many xs in Ok (Data (tid, tag, xs))
    | E.KStruct (_tid, xs) -> let* xs = many xs in Ok (Fields xs)
    | E.KProj (_tid, i, x) -> let* x = eval env x in (match x with
        | Fields xs -> Kanon_kernel.Rules.at i xs |> Option.to_result ~none:"STORE-PROJECTION"
        | Data _ | Literal _ | Closure _ | Erased -> Error "STORE-PROJECTION")
    | E.KCase (_tid, x, bs) -> let* x = eval env x in (match x with
        | Data (_t, tag, xs) -> let* b = List.find_opt (fun (b : E.kbranch) -> b.tag = tag) bs |> Option.to_result ~none:"STORE-CASE" in
            if List.length xs = b.arity then eval (List.rev xs @ env) b.body else Error "STORE-CASE-ARITY"
        | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-CASE")
    | E.KDelay _ | E.KForce _ -> Error "STORE-DELAYED"
  and apply f xs = let* () = poll () in match f with
    | Closure (n, arity, captures) -> if List.length xs < arity then Ok (Closure (n, arity - List.length xs, captures @ xs)) else
        let args, rest = List.partition (fun (i, _x) -> i < arity) (List.mapi (fun i x -> i, x) xs) in
        let* ps, b = lookup n in let values = captures @ List.map snd args in if List.length ps <> List.length values then Error "STORE-ARITY" else
        let* result = eval (List.rev values) b in if rest = [] then Ok result else apply result (List.map snd rest)
    | Data _ | Fields _ | Literal _ | Erased -> Error "STORE-APPLICATION" in
  let rec script store value = let* () = poll () in match value with
    | Data (E.Tid "mu<Script>", 0, [answer]) -> Ok (answer, store)
    | Data (E.Tid "mu<Script>", tag, Data (E.Tid "mu<Key>", 0, [key]) :: args) -> let* key = text key in
        let* args, k = match List.rev args with [] -> Error "STORE-SCRIPT-COMMAND" | k :: vs -> let* vs = all (List.rev_map operand vs) in Ok (vs, k) in
        let finish encode result = Ok (Result.fold ~ok:(fun (s, st) -> encode s, st) ~error:(fun e -> data "Reply" 4 [bytes (Store.message e)], store) result) in
        let scalar tag s = data "Reply" tag [bytes s] in let keep r = Result.map (fun s -> s, store) r in
        let integer = finish (fun s -> data "Reply" 1 [data "Signed64" 0 [bytes s]]) in
        let nullable = Option.fold ~none:(data "Reply" 0 []) ~some:(scalar 2) in let bulk = finish nullable in let status = finish (scalar 3) in
        let array encode = finish (fun ss -> data "Reply" 5 [List.fold_right (fun s rs -> data "Replies" 1 [encode s; rs]) ss (data "Replies" 0 [])]) in
        let* answer, store = match tag, args with
          | (1 | 6), [] -> integer (Store.incrby key (if tag = 1 then "1" else "-1") store)
          | 2, [] -> bulk (keep (Store.get key store))
          | 3, [Octets s] -> status (Ok (Store.set key s store))
          | 4, [Signed s] -> status (Store.integer s |> Result.map (fun _ -> Store.set key s store))
          | 5, [Signed s] -> integer (Store.incrby key s store)
          | (7 | 8), [] -> integer (Ok (if tag = 7 then Store.del key store else (Store.exists key store, store)))
          | 9, [Octets f; Octets v] -> integer (Store.hset key f v store)
          | 10, [Octets f] -> bulk (keep (Store.hget key f store))
          | (11 | 12), [Octets f] -> integer (if tag = 11 then Store.hdel key f store else keep (Store.hexists key f store))
          | (13 | 18 | 23), [] -> integer (keep ((if tag = 13 then Store.hlen else if tag = 18 then Store.scard else Store.llen) key store))
          | 14, [Octets f; Signed v] -> integer (Store.hincrby key f v store)
          | (15 | 16), [Octets m] -> integer ((if tag = 15 then Store.sadd else Store.srem) key m store)
          | 17, [Octets m] -> integer (keep (Store.sismember key m store))
          | (19 | 20), [Octets v] -> integer (Store.push (if tag = 19 then Store.Left else Store.Right) key v store)
          | (21 | 22), [] -> bulk (Store.pop (if tag = 21 then Store.Left else Store.Right) key store)
          | 24, [Signed i] -> bulk (keep (Store.lindex key i store))
          | 25, [Signed i; Octets v] -> status (Store.lset key i v store)
          | 26, [Signed i; Signed j] -> status (Store.ltrim key i j store)
          | 27, [Signed i; Signed j] -> array (scalar 2) (keep (Store.lrange key i j store))
          | (28 | 29), [] -> array (scalar 2) (keep ((if tag = 28 then Store.smembers else Store.hgetall) key store))
          | (30 | 31), [] -> array (scalar 2) (keep (Store.hproject (if tag = 30 then fst else snd) key store))
          | (32 | 33 | 34), [KeyName other] -> array (scalar 2) (keep (Store.scombine (if tag = 32 then Store.Members.union else if tag = 33 then Store.Members.inter else Store.Members.diff) key other store))
          | (35 | 36 | 37), [KeyName left; KeyName right] -> integer (Store.sstore (if tag = 35 then Store.Members.union else if tag = 36 then Store.Members.inter else Store.Members.diff) key left right store)
          | 38, [KeyName other; Octets member] -> integer (Store.smove key other member store)
          | (39 | 40 | 44 | 45), [Signed duration] -> integer (Store.expire ~absolute:(tag >= 44) ~seconds:(tag = 39 || tag = 44) key duration store)
          | (41 | 42 | 46 | 47), [] -> integer (keep (Store.ttl ~absolute:(tag >= 46) ~seconds:(tag = 41 || tag = 46) key store))
          | 43, [] -> integer (Ok (Store.persist key store))
          | (48 | 49 | 50 | 51), [Signed duration; Condition condition] -> integer (Store.expire ~condition ~absolute:(tag >= 50) ~seconds:(tag = 48 || tag = 50) key duration store)
          | 52, [BulkFields (first, rest)] -> array nullable (keep (Store.hmget key first rest store))
          | (53 | 54), [BulkFields (first, rest)] -> integer (Store.push ~rest (if tag = 53 then Store.Left else Store.Right) key first store)
          | _, _ -> Error "STORE-SCRIPT-COMMAND" in
        let* next = apply k [answer] in script store next
    | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-SCRIPT" in
  let rec client store value = let* () = poll () in match value with
    | Data (E.Tid "mu<Client>", 0, [answer]) -> let* answer = reply answer in Ok (answer, store)
    | Data (E.Tid "mu<Client>", 1, [body; k]) ->
        let* answer, store = script store body in let* decoded = reply answer in let* () = match decoded with Err error -> Error error | Nil | Int _ | Bulk _ | Status _ | Array _ -> Ok () in
        let* next = apply k [answer] in client store next
    | Data (E.Tid "mu<Client>", 2, [_fault]) -> Error "STORE-CLIENT-FAULT"
    | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-CLIENT" in
  let* ps, body = lookup entry in if ps <> [] then Error "STORE-ENTRY" else let* value = eval [] body in client store value
