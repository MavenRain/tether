module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("LIST-MOVE-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let same a b = S.bindings a = S.bindings b && S.Keys.bindings a.S.deadlines = S.Keys.bindings b.S.deadlines && a.S.now = b.S.now
let base = { (S.put "other" (S.Str "kept") S.empty) with now = 1000L; deadlines = S.Keys.singleton "other" 9000L }
let stored key value deadline store = { (S.put key value store) with deadlines = S.Keys.add key deadline store.S.deadlines }
let queues source destination =
  let before = match source with [] -> base | xs -> stored "k" (S.List xs) 5000L base in
  match destination with [] -> before | xs -> stored "d" (S.List xs) 7000L before
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let key s = E.KTag (E.Tid "mu<Key>", 0, [bytes s])
let endpoint side = E.KTag (E.Tid "mu<ListEnd>", (match side with S.Left -> 0 | S.Right -> 1), [])
let execute ?(expose=false) args before =
  let script = E.KTag (E.Tid "mu<Script>", 68, key "k" :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let directions = [S.Left, S.Left; S.Left, S.Right; S.Right, S.Left; S.Right, S.Right]
let check from_side to_side other before expected after =
  let* reply, actual = S.lmove from_side to_side "k" other before |> Result.map_error S.message in
  let* () = require (reply = expected && same actual after) "store reply and complete state" in
  let* reply, actual = execute [key other; endpoint from_side; endpoint to_side] before in
  require (reply = Option.fold ~none:I.Nil ~some:(fun s -> I.Bulk s) expected && same actual after) "interpreter reply and complete state"
let run () =
  let samples = [
    S.Left, S.Left, "a", ["b"; "c"], ["a"; "x"; "y"];
    S.Left, S.Right, "a", ["b"; "c"], ["x"; "y"; "a"];
    S.Right, S.Left, "c", ["a"; "b"], ["c"; "x"; "y"];
    S.Right, S.Right, "c", ["a"; "b"], ["x"; "y"; "c"]] in
  let* distinct = fold (fun (f, t, moved, source, destination) ->
    check f t "d" (queues ["a"; "b"; "c"] ["x"; "y"]) (Some moved) (queues source destination)) samples in
  let rotations = [S.Left, S.Left, "a", ["a"; "b"; "c"]; S.Left, S.Right, "a", ["b"; "c"; "a"];
    S.Right, S.Left, "c", ["c"; "a"; "b"]; S.Right, S.Right, "c", ["a"; "b"; "c"]] in
  let* aliases = fold (fun (f, t, moved, after) -> check f t "k" (queues ["a"; "b"; "c"] []) (Some moved) (queues after [])) rotations in
  let values = [""; I.octets; "\239\187\191hello\000\n\n"; "01"; "9007199254740993"] in
  let* binary = fold (fun (f, t, value) ->
    let before = queues [value] [] in
    let* () = check f t "k" before (Some value) before in
    check f t "d" before (Some value) (S.put "d" (S.List [value]) base))
    (List.concat_map (fun (f, t) -> List.map (fun value -> f, t, value) values) directions) in
  let* missing = fold (fun (f, t) ->
    let* () = check f t "k" base None base in
    let before = queues [] ["x"; "y"] in check f t "d" before None before) directions in
  let wrong = [S.Str "old"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream ["1-0", "v"]] in
  let* errors = fold (fun (f, t, value, source) ->
    let before = if source then stored "k" value 5000L (queues [] ["x"]) else stored "d" value 7000L (queues ["a"] []) in
    let args = [key "d"; endpoint f; endpoint t] in
    let* () = require (S.lmove f t "k" "d" before = Error S.Wrong_type) "store wrong type" in
    let* () = require (execute args before = Error (S.message S.Wrong_type)) "unhandled error stops client" in
    let* reply, after = execute ~expose:true args before in
    require (reply = I.Status (S.message S.Wrong_type) && same before after) "error preserves complete state")
    (List.concat_map (fun (f, t) -> List.concat_map (fun value -> [f, t, value, true; f, t, value, false]) wrong) directions) in
  let* precedence = fold (fun (f, t, value) ->
    let before = stored "d" value 7000L base in check f t "d" before None before)
    (List.concat_map (fun (f, t) -> List.map (fun value -> f, t, value) wrong) directions) in
  let* expired = fold (fun (f, t) ->
    let* before = S.advance "4001" (queues ["a"] ["x"]) |> Result.map_error S.message in
    let* () = check f t "d" before None before in
    let original = stored "d" (S.Str "wrong") 2000L (queues ["a"] []) in
    let* before = S.advance "1001" original |> Result.map_error S.message in
    check f t "d" before (Some "a") (S.put "d" (S.List ["a"]) (S.remove "k" before))) directions in
  let shape_args = [[key "d"; bytes "LEFT"; endpoint S.Right]; [key "d"; endpoint S.Left; bytes "RIGHT"];
    [bytes "d"; endpoint S.Left; endpoint S.Right]; [key "d"; endpoint S.Left]; [];
    [key "d"; endpoint S.Left; endpoint S.Right; bytes "extra"]] in
  let* shapes = fold (fun args -> require (execute args (queues ["a"] []) = Error "STORE-SCRIPT-COMMAND") "operand shape") shape_args in
  let* invalid = fold (fun tag -> require
    (execute [key "d"; E.KTag (E.Tid "mu<ListEnd>", tag, []); endpoint S.Right] base = Error "STORE-LIST-END") "invalid endpoint") [-1; 2] in
  let total = distinct + aliases + binary + missing + errors + precedence + expired + shapes + invalid in
  let* () = require (total = 104) (Printf.sprintf "expected 104 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS LIST-MOVE-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
