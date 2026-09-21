module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("STRING-BYTES-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let base = S.put "other" (S.Str "kept") { S.empty with now = 1000L; deadlines = S.Keys.singleton "other" 9000L }
let hash fields = S.put "k" (S.Hash fields) base
let expiring store = { store with S.deadlines = S.Keys.add "k" 7000L store.S.deadlines }
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let execute ?(recover = false) tag args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", tag, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let answer = if recover then E.KTag (E.Tid "mu<Reply>", 3, [bytes "caught"]) else E.KVar 0 in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run () =
  let strings = [None; Some ""; Some "hello"; Some "\195\169\240\159\153\130";
    Some "\000\255\000"; Some I.octets; Some "9007199254740993"; Some "01"] in
  let* lengths = fold (fun value ->
    let before = Option.fold ~none:base ~some:(fun s -> expiring (S.put "k" (S.Str s) base)) value in
    let expected = string_of_int (Option.fold ~none:0 ~some:String.length value) in
    let* actual = S.strlen "k" before |> Result.map_error S.message in
    let* () = require (actual = expected) "byte length" in
    let* reply, state = execute 72 [] before in
    require (reply = I.Int expected && state = before) "length reply and complete state") strings in
  let* appended = fold (fun (value, suffix) ->
    let before = Option.fold ~none:base ~some:(fun s -> expiring (S.put "k" (S.Str s) base)) value in
    let joined = Option.value ~default:"" value ^ suffix in
    let expected = string_of_int (String.length joined), S.put "k" (S.Str joined) before in
    let* actual = S.append "k" suffix before |> Result.map_error S.message in
    let* () = require (actual = expected) "append order, value and expiry" in
    let* reply, state = execute 71 [bytes suffix] before in
    require (reply = I.Int (fst expected) && state = snd expected) "append interpreter")
    (List.concat_map (fun v -> List.map (fun s -> v, s) [""; "!"; "\000\255"; I.octets]) strings) in
  let* faults = fold (fun value ->
    let before = expiring (S.put "k" value base) in
    let* () = require (S.append "k" "" before = Error S.Wrong_type
      && S.strlen "k" before = Error S.Wrong_type) "wrong type, including empty append" in
    let* _ = fold (fun (tag, args) ->
      let* () = require (execute tag args before = Error (S.message S.Wrong_type)) "unhandled error" in
      let* reply, state = execute ~recover:true tag args before in
      require (reply = I.Status "caught" && state = before) "caught error preserves state")
      [71, [bytes ""]; 72, []] in Ok ())
    [S.Hash ["f", "v"]; S.List ["x"]; S.Set ["x"]; S.ZSet ["x", "1"]; S.Stream ["f", "v"]] in
  let* expired = S.advance "6001" (expiring (S.put "k" (S.Str "old") base)) |> Result.map_error S.message in
  let* () = require (S.strlen "k" expired = Ok "0") "expired length" in
  let* count, recreated = S.append "k" "" expired |> Result.map_error S.message in
  let* () = require (count = "0" && S.get "k" recreated = Ok (Some "")
    && not (S.Keys.mem "k" recreated.deadlines)) "empty append recreates persistent string" in
  let* sizes = fold (fun (before, extra, accepted) ->
    require (S.message S.String_size = "ERR string exceeds maximum allowed size (proto-max-bulk-len)"
      && S.append_size before extra = (if accepted then Ok () else Error S.String_size)) "size boundary")
    [0, 0, true; 0, 536870912, true; 536870911, 1, true; 536870912, 0, true;
     536870912, 1, false; 0, 536870913, false; max_int, 1, false; 1, max_int, false] in
  let big = String.make 268435457 'x' in
  let* () = require (S.append "k" big (S.put "k" (S.Str big) base) = Error S.String_size
    && S.append "k" big (hash ["f", "v"]) = Error S.Wrong_type) "size limit at the append call site" in
  let* malformed = fold (fun (tag, args) -> require (execute tag args base = Error "STORE-SCRIPT-COMMAND") "malformed operands")
    [71, []; 71, [bytes "x"; bytes "y"]; 72, [bytes "x"];
     71, [E.KTag (E.Tid "mu<Signed64>", 0, [bytes "1"])]] in
  Ok (lengths + appended + faults + sizes + malformed + 3)
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS STRING-BYTES-UNIT cases=%d\n" count)
  ~error:(fun error -> prerr_endline ("FAIL " ^ error); exit 1)
