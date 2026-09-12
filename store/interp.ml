module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
type value = Data of E.tid * int * value list | Fields of value list
  | Literal of Kanon_kernel.Literal.t | Closure of string * int * value list | Erased
type reply = Nil | Int of string | Bulk of string | Status of string | Err of string | Array of reply list
let all xs = List.fold_right (fun x acc -> let* x = x in let* xs = acc in Ok (x :: xs)) xs (Ok [])
let data name tag xs = Data (E.Tid ("mu<" ^ name ^ ">"), tag, xs)
let octets = "\000\001\002\003\004\005\006\007\008\009\010\011\012\013\014\015\016\017\018\019\020\021\022\023\024\025\026\027\028\029\030\031\032\033\034\035\036\037\038\039\040\041\042\043\044\045\046\047\048\049\050\051\052\053\054\055\056\057\058\059\060\061\062\063\064\065\066\067\068\069\070\071\072\073\074\075\076\077\078\079\080\081\082\083\084\085\086\087\088\089\090\091\092\093\094\095\096\097\098\099\100\101\102\103\104\105\106\107\108\109\110\111\112\113\114\115\116\117\118\119\120\121\122\123\124\125\126\127\128\129\130\131\132\133\134\135\136\137\138\139\140\141\142\143\144\145\146\147\148\149\150\151\152\153\154\155\156\157\158\159\160\161\162\163\164\165\166\167\168\169\170\171\172\173\174\175\176\177\178\179\180\181\182\183\184\185\186\187\188\189\190\191\192\193\194\195\196\197\198\199\200\201\202\203\204\205\206\207\208\209\210\211\212\213\214\215\216\217\218\219\220\221\222\223\224\225\226\227\228\229\230\231\232\233\234\235\236\237\238\239\240\241\242\243\244\245\246\247\248\249\250\251\252\253\254\255"
let bytes text = List.fold_right (fun c tail -> data "Bytes" 1
  [Literal (Kanon_kernel.Literal.LInt (Kanon_kernel.Bignum.of_int (Char.code c))); tail])
  (List.of_seq (String.to_seq text)) (data "Bytes" 0 [])
let rec text = function
  | Data (E.Tid "mu<Bytes>", 0, []) -> Ok ""
  | Data (E.Tid "mu<Bytes>", 1, [Literal (Kanon_kernel.Literal.LInt n); tail]) ->
      let* byte = int_of_string_opt (Kanon_kernel.Bignum.to_string n) |> Option.to_result ~none:"STORE-BYTE" in
      let* c = Seq.find (fun c -> Char.code c = byte) (String.to_seq octets)
        |> Option.to_result ~none:"STORE-BYTE" in
      let* tail = text tail in Ok (String.make 1 c ^ tail)
  | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-BYTES"
let rec reply = function
  | Data (E.Tid "mu<Reply>", 0, []) -> Ok Nil
  | Data (E.Tid "mu<Reply>", 1, [Data (E.Tid "mu<Signed64>", 0, [b])]) ->
      let* s = text b in let* _n = Store.integer s |> Result.map_error Store.message in Ok (Int s)
  | Data (E.Tid "mu<Reply>", 2, [b]) -> let* s = text b in Ok (Bulk s)
  | Data (E.Tid "mu<Reply>", 3, [b]) -> let* s = text b in Ok (Status s)
  | Data (E.Tid "mu<Reply>", 4, [b]) -> let* s = text b in Ok (Err s)
  | Data (E.Tid "mu<Reply>", 5, [rs]) -> let* rs = replies rs in Ok (Array rs)
  | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-REPLY"
and replies = function
  | Data (E.Tid "mu<Replies>", 0, []) -> Ok []
  | Data (E.Tid "mu<Replies>", 1, [r; rs]) -> let* r = reply r in let* rs = replies rs in Ok (r :: rs)
  | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-REPLIES"

(* Evaluate the erased term itself, independently of both printers. *)
let run ~budget rows ~entry store =
  let functions = List.concat_map (fun (_name, entry) -> match entry with
    | Kanon_kernel.Erase.Dropped | Kanon_kernel.Erase.Postulate _ -> []
    | Kanon_kernel.Erase.Code ds -> List.filter_map (function
        | E.KFun (E.Fid n, ps, _r, body) -> Some (n, (ps, body))
        | E.KRec _ -> None) ds) rows in
  let lookup name = List.assoc_opt name functions |> Option.to_result ~none:("STORE-GLOBAL " ^ name) in
  let poll () = if Kanon_kernel.Budget.exhausted budget then Error "STORE-BUDGET" else Ok () in
  let rec eval env term =
    let* () = poll () in let many xs = all (List.map (eval env) xs) in
    match term with
    | E.KVar i -> Kanon_kernel.Rules.at i env |> Option.to_result ~none:"STORE-VAR"
    | E.KLit l -> Ok (Literal l)
    | E.KErased -> Ok Erased
    | E.KGlobal n -> let* ps, b = lookup n in
        if ps = [] then eval [] b else Ok (Closure (n, List.length ps, []))
    | E.KClos (E.Fid n, arity, xs) -> let* xs = many xs in Ok (Closure (n, arity, xs))
    | E.KApp (f, xs) | E.KTail (f, xs) -> let* f = eval env f in let* xs = many xs in apply f xs
    | E.KLet (_n, x, b) -> let* x = eval env x in eval (x :: env) b
    | E.KTag (tid, tag, xs) -> let* xs = many xs in Ok (Data (tid, tag, xs))
    | E.KStruct (_tid, xs) -> let* xs = many xs in Ok (Fields xs)
    | E.KProj (_tid, i, x) -> let* x = eval env x in (match x with
        | Fields xs -> Kanon_kernel.Rules.at i xs |> Option.to_result ~none:"STORE-PROJECTION"
        | Data _ | Literal _ | Closure _ | Erased -> Error "STORE-PROJECTION")
    | E.KCase (_tid, x, bs) -> let* x = eval env x in (match x with
        | Data (_t, tag, xs) ->
            let* b = List.find_opt (fun (b : E.kbranch) -> b.tag = tag) bs |> Option.to_result ~none:"STORE-CASE" in
            if List.length xs = b.arity then eval (List.rev xs @ env) b.body else Error "STORE-CASE-ARITY"
        | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-CASE")
    | E.KDelay _ | E.KForce _ -> Error "STORE-DELAYED"
  and apply f xs = let* () = poll () in match f with
    | Closure (n, arity, captures) ->
        if List.length xs < arity then Ok (Closure (n, arity - List.length xs, captures @ xs)) else
        let args, rest = List.partition (fun (i, _x) -> i < arity) (List.mapi (fun i x -> i, x) xs) in
        let* ps, b = lookup n in let values = captures @ List.map snd args in
        if List.length ps <> List.length values then Error "STORE-ARITY" else
        let* result = eval (List.rev values) b in if rest = [] then Ok result else apply result (List.map snd rest)
    | Data _ | Fields _ | Literal _ | Erased -> Error "STORE-APPLICATION" in
  let rec script store value = let* () = poll () in match value with
    | Data (E.Tid "mu<Script>", 0, [answer]) -> Ok (answer, store)
    | Data (E.Tid "mu<Script>", tag, Data (E.Tid "mu<Key>", 0, [key]) :: args) ->
        let* key = text key in
        let integer result = Result.map (fun (s, st) -> data "Reply" 1 [data "Signed64" 0 [bytes s]], st) result in
        let status (s, st) = data "Reply" 3 [bytes s], st in
        let* result, k = match tag, args with
          | 1, [k] -> Ok (integer (Store.incr key store), k)
          | 2, [k] -> Ok (Store.get key store |> Result.map (fun s ->
              Option.fold ~none:(data "Reply" 0 []) ~some:(fun s -> data "Reply" 2 [bytes s]) s, store), k)
          | 3, [v; k] -> let* s = text v in Ok (Ok (status (Store.set key s store)), k)
          | 4, [Data (E.Tid "mu<Signed64>", 0, [v]); k] -> let* s = text v in
              Ok (Store.integer s |> Result.map (fun _n -> status (Store.set key s store)), k)
          | 5, [Data (E.Tid "mu<Signed64>", 0, [v]); k] -> let* s = text v in
              Ok (integer (Store.incrby key s store), k)
          | 6, [k] -> Ok (integer (Store.decr key store), k)
          | 7, [k] -> Ok (integer (Ok (Store.del key store)), k)
          | 8, [k] -> Ok (integer (Ok (Store.exists key store, store)), k)
          | _, _ -> Error "STORE-SCRIPT-COMMAND" in
        let answer, store = Result.fold ~ok:Fun.id ~error:(fun e ->
          data "Reply" 4 [bytes (Store.message e)], store) result in
        let* next = apply k [answer] in script store next
    | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-SCRIPT" in
  let rec client store value = let* () = poll () in match value with
    | Data (E.Tid "mu<Client>", 0, [answer]) -> let* answer = reply answer in Ok (answer, store)
    | Data (E.Tid "mu<Client>", 1, [body; k]) ->
        let* answer, store = script store body in let* decoded = reply answer in
        (match decoded with
         | Err error -> Error error
         | Nil | Int _ | Bulk _ | Status _ | Array _ ->
             let* next = apply k [answer] in client store next)
    | Data (E.Tid "mu<Client>", 2, [_fault]) -> Error "STORE-CLIENT-FAULT"
    | Data _ | Fields _ | Literal _ | Closure _ | Erased -> Error "STORE-CLIENT" in
  let* ps, body = lookup entry in
  if ps <> [] then Error "STORE-ENTRY" else let* value = eval [] body in client store value
