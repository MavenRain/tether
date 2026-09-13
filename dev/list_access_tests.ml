module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("LIST-ACCESS-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let list values = S.put "k" (S.List values) S.empty
let same a b = S.Keys.bindings a = S.Keys.bindings b
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
let run () =
  let values = ["a"; "b"; "c"] in
  let samples = [
    24, [signed "0"], list values, I.Bulk "a", list values, "index first";
    24, [signed "-1"], list values, I.Bulk "c", list values, "index negative";
    24, [signed "-3"], list values, I.Bulk "a", list values, "index negative boundary";
    24, [signed "3"], list values, I.Nil, list values, "index outside";
    24, [signed "-4"], list values, I.Nil, list values, "index before start";
    24, [signed "9223372036854775807"], list values, I.Nil, list values, "index max";
    24, [signed "-9223372036854775808"], list values, I.Nil, list values, "index min";
    24, [signed "01"], S.empty, I.Nil, S.empty, "missing index before invalid integer";
    25, [signed "0"; bytes "x"], list values, I.Status "OK", list ["x"; "b"; "c"], "set first";
    25, [signed "-1"; bytes "x"], list values, I.Status "OK", list ["a"; "b"; "x"], "set negative";
    25, [signed "-3"; bytes "x"], list values, I.Status "OK", list ["x"; "b"; "c"], "set negative boundary";
    26, [signed "1"; signed "1"], list values, I.Status "OK", list ["b"], "trim inclusive";
    26, [signed "-2"; signed "-1"], list values, I.Status "OK", list ["b"; "c"], "trim negative";
    26, [signed "2"; signed "0"], list values, I.Status "OK", S.empty, "trim reversed deletes key";
    26, [signed "0"; signed "-4"], list values, I.Status "OK", S.empty, "trim negative end deletes key";
    26, [signed "3"; signed "99"], list values, I.Status "OK", S.empty, "trim outside deletes key";
    26, [signed "-9223372036854775808"; signed "9223372036854775807"], list values,
      I.Status "OK", list values, "trim clamps extremes";
    26, [signed "0"; signed "-1"], S.empty, I.Status "OK", S.empty, "trim missing"] in
  let* cases = fold (fun (tag, args, before, expected, after, name) ->
    let other = S.put "other" (S.Str "kept") in
    let* reply, actual = execute tag args (other before) in
    require (reply = expected && same actual (other after)) name) samples in
  let faults = [
    25, [signed "0"; bytes "x"], S.empty, S.Missing_key, "set missing";
    25, [signed "01"; bytes "x"], S.empty, S.Missing_key, "set missing precedes integer";
    25, [signed "3"; bytes "x"], list values, S.Index_range, "set out of range";
    25, [signed "-4"; bytes "x"], list values, S.Index_range, "set before start";
    25, [signed "-9223372036854775808"; bytes "x"], list values, S.Index_range, "set minimum";
    25, [signed "9223372036854775807"; bytes "x"], list values, S.Index_range, "set maximum"] in
  let operations index = [24, [signed index]; 25, [signed index; bytes "x"]; 26, [signed index; signed "-1"]] in
  let wrong_types = [S.Str "old"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let wrong = List.concat_map (fun value -> List.map (fun (tag, args) ->
    tag, args, S.put "k" value S.empty, S.Wrong_type, "wrong type") (operations "0")) wrong_types in
  let malformed = [""; "01"; "-0"; "+1"; "1.0"; " 1"; "1\000"; "0x1";
    "9223372036854775808"; "-9223372036854775809"] in
  let invalid = List.concat_map (fun index -> List.map (fun (tag, args) ->
    tag, args, list values, S.Not_integer, "invalid index") (operations index)) malformed in
  let precedence = [
    24, [signed "01"], S.put "k" (S.Str "old") S.empty, S.Wrong_type, "index wrong type precedence";
    25, [signed "01"; bytes "x"], S.put "k" (S.Str "old") S.empty, S.Wrong_type, "set wrong type precedence";
    26, [signed "01"; signed "0"], S.put "k" (S.Str "old") S.empty, S.Not_integer, "trim integer precedence";
    26, [signed "0"; signed "01"], S.empty, S.Not_integer, "trim validates stop on missing"] in
  let* errors = fold (fun (tag, args, before, fault, name) ->
    let* () = require (execute tag args before = Error (S.message fault)) (name ^ " stops client") in
    let* reply, after = execute ~expose:true tag args before in
    require (reply = I.Status (S.message fault) && same before after) (name ^ " typed err preserves state"))
    (faults @ wrong @ invalid @ precedence) in
  let* binary = fold (fun value ->
    let* status, before = execute 25 [signed "-1"; bytes value] (list ["old"]) in
    let* reply, after = execute 24 [signed "0"] before in
    require (status = I.Status "OK" && reply = I.Bulk value && same after (list [value])) "binary access")
    [""; "\000"; "\255"; "\239\187\191hello\000\n\n"; "01"] in
  let malformed_args = [24, [bytes "0"]; 25, [signed "0"; signed "1"]; 26, [signed "0"; bytes "1"];
    3, [signed "1"]; 19, [signed "1"]] in
  let* shapes = fold (fun (tag, args) ->
    require (execute tag args (list values) = Error "STORE-SCRIPT-COMMAND") "operand shape") malformed_args in
  let total = cases + errors + binary + shapes in
  let* () = require (total = 83) (Printf.sprintf "expected 83 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS LIST-ACCESS-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
