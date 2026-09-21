module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("LIST-POP-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let same a b = S.bindings a = S.bindings b && S.Keys.bindings a.S.deadlines = S.Keys.bindings b.S.deadlines && a.S.now = b.S.now
let base = { (S.put "other" (S.Str "kept") S.empty) with now = 1000L; deadlines = S.Keys.singleton "other" 9000L }
let stored value = { (S.put "k" value base) with deadlines = S.Keys.add "k" 5000L base.S.deadlines }
let queue = function [] -> base | xs -> stored (S.List xs)
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let signed s = E.KTag (E.Tid "mu<Signed64>", 0, [bytes s])
let execute ?(expose=false) tag args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", tag, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let check side count before expected after =
  let* reply, actual = S.pop_many side "k" count before |> Result.map_error S.message in
  let* () = require (reply = expected && same actual after) "store reply and complete state" in
  let* reply, actual = execute (match side with S.Left -> 69 | S.Right -> 70) [signed count] before in
  require (reply = Option.fold ~none:I.Nil ~some:(fun xs -> I.Array (List.map (fun s -> I.Bulk s) xs)) expected && same actual after) "interpreter reply and complete state"
let run () =
  let samples = ["0", Some [], ["c"; "a"; "b"];
    "1", Some ["c"], ["a"; "b"]; "2", Some ["c"; "a"], ["b"];
    "3", Some ["c"; "a"; "b"], []; "4", Some ["c"; "a"; "b"], [];
    "9223372036854775807", Some ["c"; "a"; "b"], []] in
  let* normal = fold (fun side ->
    let* _ = fold (fun (count, expected, rest) ->
      check side count (queue (S.orient side ["c"; "a"; "b"])) expected (queue (S.orient side rest))) samples in Ok ()) [S.Left; S.Right] in
  let* missing = fold (fun (side, count) -> check side count base None base)
    (List.concat_map (fun side -> List.map (fun (count, _, _) -> side, count) samples) [S.Left; S.Right]) in
  let* binary = fold (fun side -> let values = [""; "\000\255\n"; "dup"; "dup"] in
    check side "4" (queue (S.orient side values)) (Some values) base) [S.Left; S.Right] in
  let wrong = [S.Str "x"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream ["1", "v"]] in
  let* errors = fold (fun (side, count, before, fault) ->
    let* () = require (S.pop_many side "k" count before = Error fault) "store validation" in
    let* reply, after = execute ~expose:true (match side with S.Left -> 69 | S.Right -> 70) [signed count] before in
    require (reply = I.Status (S.message fault) && same after before) "error atomicity")
    (List.concat_map (fun side ->
      List.concat_map (fun value -> List.map (fun count -> side, count, stored value, S.Wrong_type) ["0"; "1"; "9223372036854775807"]) wrong @
      List.concat_map (fun before -> List.map (fun count -> side, count, before, S.Pop_range) ["-1"; "-9223372036854775808"] @
        List.map (fun count -> side, count, before, S.Pop_range) ["01"; "+1"; "-0"; "9223372036854775808"; " 1"; "x"])
        [base; queue ["a"]; stored (S.Str "wrong")]) [S.Left; S.Right]) in
  let* expired = S.advance "4001" (queue ["old"]) |> Result.map_error S.message in
  let* () = check S.Left "1" expired None expired in
  let* malformed = fold (fun (tag, args, want) ->
    require (execute tag args (queue ["a"]) = Error want) "malformed command")
    [69, [], "STORE-SCRIPT-COMMAND"; 70, [signed "1"; signed "1"], "STORE-SCRIPT-COMMAND";
     69, [bytes "1"], "STORE-SCRIPT-COMMAND"; 70, [E.KErased], "STORE-BYTES"] in
  Ok (normal * List.length samples + missing + binary + errors + malformed + 1)
let () = Result.fold ~ok:(fun count -> Printf.printf "PASS LIST-POP-UNIT cases=%d\n" count)
  ~error:(fun message -> prerr_endline ("FAIL " ^ message); exit 1) (run ())
