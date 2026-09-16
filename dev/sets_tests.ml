module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("SETS-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let set values = S.put "k" (S.Set values) S.empty
let same a b = S.bindings a = S.bindings b
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
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
let run () =
  let* basic = fold (fun (ok, name) -> require ok name) [
    S.sismember "k" "m" S.empty = Ok "0", "missing membership";
    S.scard "k" S.empty = Ok "0", "missing cardinality";
    S.srem "k" "m" S.empty = Ok ("0", S.empty), "missing remove";
    S.srem "k" "m" (set ["m"]) = Ok ("1", S.empty), "remove last member";
    S.srem "k" "missing" (set ["m"]) = Ok ("0", set ["m"]), "remove absent member";
    S.sadd "k" "m" (set ["m"]) = Ok ("0", set ["m"]), "duplicate count";
    S.sadd "k" "m" S.empty = Ok ("1", set ["m"]), "create set";
    S.scard "k" (set ["m"; "m"; "a"]) = Ok "2", "normalize fixture members";
    S.sismember "k" "" (set [""]) = Ok "1", "empty member exists";
    S.scard "k" (set ["1"; "01"; "-0"; "0"]) = Ok "4", "byte identity"] in
  let samples = [
    15, [bytes "m"], S.empty, I.Int "1", set ["m"], "interpreter creates set";
    15, [bytes "m"], set ["m"], I.Int "0", set ["m"], "interpreter duplicate";
    15, [bytes "a"], set ["z"], I.Int "1", set ["a"; "z"], "preserve sibling";
    15, [bytes "\000\255"], S.empty, I.Int "1", set ["\000\255"], "binary add";
    15, [bytes ""], S.empty, I.Int "1", set [""], "empty add";
    16, [bytes "m"], S.empty, I.Int "0", S.empty, "interpreter missing remove";
    16, [bytes "m"], set ["m"], I.Int "1", S.empty, "interpreter deletes key";
    16, [bytes "a"], set ["a"; "z"], I.Int "1", set ["z"], "remove preserves sibling";
    16, [bytes "missing"], set ["m"], I.Int "0", set ["m"], "interpreter absent remove";
    16, [bytes "\000\255"], set ["\000\255"], I.Int "1", S.empty, "binary remove";
    16, [bytes ""], set [""], I.Int "1", S.empty, "empty remove";
    17, [bytes "m"], S.empty, I.Int "0", S.empty, "interpreter missing membership";
    17, [bytes "m"], set ["m"; "z"], I.Int "1", set ["m"; "z"], "membership reply";
    17, [bytes "no"], set ["m"], I.Int "0", set ["m"], "membership absent";
    17, [bytes "\000\255"], set ["\000\255"], I.Int "1", set ["\000\255"], "binary membership";
    17, [bytes ""], set [""], I.Int "1", set [""], "empty membership";
    18, [], S.empty, I.Int "0", S.empty, "interpreter missing cardinality";
    18, [], set ["a"; "z"], I.Int "2", set ["a"; "z"], "cardinality reply"] in
  let* interpreted = fold (fun (tag, args, before, expected, after, name) ->
    let before = S.put "other" (S.Str "kept") before in
    let* reply, actual = execute tag args before in
    require (reply = expected && same actual (S.put "other" (S.Str "kept") after)) name) samples in
  let wrong_types = [S.Str "old"; S.Hash ["f", "v"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let operations = [15, [bytes "m"], (fun s -> Result.map (fun _ -> ()) (S.sadd "k" "m" s)), "sadd";
    16, [bytes "m"], (fun s -> Result.map (fun _ -> ()) (S.srem "k" "m" s)), "srem";
    17, [bytes "m"], (fun s -> Result.map (fun _ -> ()) (S.sismember "k" "m" s)), "sismember";
    18, [], (fun s -> Result.map (fun _ -> ()) (S.scard "k" s)), "scard"] in
  let* wrong = fold (fun (tag, args, operation, name, value) ->
    let before = S.put "k" value (S.put "other" (S.Str "kept") S.empty) in
    let* () = require (operation before = Error S.Wrong_type
      && execute tag args before = Error (S.message S.Wrong_type)) (name ^ " wrong type stops client") in
    let* reply, after = execute ~expose:true tag args before in
    require (reply = I.Status (S.message S.Wrong_type) && same before after) (name ^ " err preserves store"))
    (List.concat_map (fun (tag, args, f, name) -> List.map (fun v -> tag, args, f, name, v) wrong_types) operations) in
  let* identity = fold (fun member ->
    let* count, after = S.sadd "k" member S.empty |> Result.map_error S.message in
    let* duplicate, unchanged = S.sadd "k" member after |> Result.map_error S.message in
    let* removed, empty = S.srem "k" member after |> Result.map_error S.message in
    require (count = "1" && duplicate = "0" && same after unchanged && removed = "1"
      && same empty S.empty && S.sismember "k" member after = Ok "1") "member roundtrip")
    [""; "\000"; "\255"; "\000\255\n\"$(touch forbidden)\\"; "1"; "01"; "-0"; "0"] in
  Ok (basic + interpreted + wrong + identity)
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS SETS-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
