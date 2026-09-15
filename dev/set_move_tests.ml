module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("SET-MOVE-UNIT " ^ reason)
let same a b = S.Keys.bindings a = S.Keys.bindings b
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let key s = E.KTag (E.Tid "mu<Key>", 0, [bytes s])
let execute ?(expose=false) ?(poll=fun () -> false) source tag args before =
  let script = E.KTag (E.Tid "mu<Script>", tag, key source :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll poll) rows ~entry:"main" before
let initial = S.put "other" (S.Str "kept") S.empty
let seed left right =
  let put name value store = Option.fold ~none:store ~some:(fun v -> S.put name v store) value in
  initial |> put "source" left |> put "destination" right
let set xs = Some (S.Set xs)
let good source destination member before expected after =
  let* reply, actual = S.smove source destination member before |> Result.map_error S.message in
  let* () = require (reply = expected && same actual after) "store reply and complete state" in
  let* reply, actual = execute source 38 [key destination; bytes member] before in
  require (reply = I.Int expected && same actual after) "interpreter integer and complete state"
let absent source destination before =
  let* () = require (S.smove source destination "m" before |> Result.map fst = Ok "0") "missing source precedence" in
  good source destination "m" before "0" before
let bad source destination before =
  let* () = require (S.smove source destination "m" before = Error S.Wrong_type) "wrong type" in
  let* reply, actual = execute ~expose:true source 38 [key destination; bytes "m"] before in
  let* () = require (reply = I.Status (S.message S.Wrong_type) && same actual before) "catchable atomic error" in
  require (execute source 38 [key destination; bytes "m"] before = Error (S.message S.Wrong_type)) "uncaught error"
let run () =
  let cases = [
    None, None, "m", "0", None, None;
    None, set ["n"], "m", "0", None, set ["n"];
    set ["m"], None, "m", "1", None, set ["m"];
    set ["m"; "x"], set ["n"], "m", "1", set ["x"], set ["m"; "n"];
    set ["m"], set ["m"; "n"], "m", "1", None, set ["m"; "n"];
    set ["n"], None, "m", "0", set ["n"], None;
    set ["n"], set ["x"], "m", "0", set ["n"], set ["x"];
    set [""; "m"], None, "", "1", set ["m"], set [""];
    set ["m"; "m"; "x"], None, "m", "1", set ["x"], set ["m"]] in
  let* basic = fold (fun (left, right, member, reply, after_left, after_right) ->
    good "source" "destination" member (seed left right) reply (seed after_left after_right)) cases in
  let* aliases = fold (fun (value, member, reply) ->
    let before = seed value (set ["kept"]) in good "source" "source" member before reply before)
    [None, "m", "0"; set ["m"], "m", "1"; set ["n"], "m", "0"; set [""], "", "1"] in
  let octets = "" :: (List.of_seq (String.to_seq I.octets) |> List.map (String.make 1)) in
  let* binary = fold (fun member -> good "source" "destination" member
    (seed (set [member]) None) "1" (seed None (set [member]))) octets in
  let wrong = [S.Str "old"; S.Hash ["f", "v"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream ["entry", "v"]] in
  let* faults = fold (fun value ->
    let* () = bad "source" "destination" (seed (Some value) None) in
    let* () = bad "source" "destination" (seed (set ["m"]) (Some value)) in
    let* () = bad "source" "destination" (seed (set ["n"]) (Some value)) in
    let* () = bad "source" "source" (seed (Some value) None) in
    let before = seed None (Some value) in absent "source" "destination" before) wrong in
  let signed = E.KTag (E.Tid "mu<Signed64>", 0, [bytes "0"]) in
  let malformed = [ []; [key "destination"]; [bytes "destination"; bytes "m"];
    [key "destination"; key "m"]; [key "destination"; signed];
    [key "destination"; bytes "m"; bytes "extra"] ] in
  let* shapes = fold (fun args -> require (execute "source" 38 args initial = Error "STORE-SCRIPT-COMMAND") "operand shape") malformed in
  let* () = require (execute "source" 39 [key "destination"; bytes "m"] initial = Error "STORE-SCRIPT-COMMAND") "unknown tag" in
  let* () = require (execute ~poll:(fun () -> true) "source" 38 [key "destination"; bytes "m"] initial = Error "STORE-BUDGET") "fuel" in
  let* () = good "destination" "source" "m" (seed (set ["n"]) (set ["m"])) "1" (seed (set ["m"; "n"]) None) in
  Ok (basic + aliases + binary + faults * 5 + shapes + 3)
let () = Result.fold
  ~ok:(fun count -> Printf.printf "PASS SET-MOVE-UNIT cases=%d\n" count)
  ~error:(fun reason -> Printf.eprintf "FAIL %s\n" reason; exit 1) (run ())
