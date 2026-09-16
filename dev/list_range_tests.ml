module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("LIST-RANGE-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let list values = S.put "k" (S.List values) S.empty
let same a b = S.bindings a = S.bindings b
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let signed s = E.KTag (E.Tid "mu<Signed64>", 0, [bytes s])
let execute ?(expose=false) args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", 27, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
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
  let minimum, maximum = "-9223372036854775808", "9223372036854775807" in
  let ranges = [
    "0", "-1", values, "all"; "1", "1", ["b"], "inclusive";
    "-2", "-1", ["b"; "c"], "negative"; "-3", "-1", values, "negative boundary";
    "-4", "-1", values, "clamp start"; "0", "0", ["a"], "head";
    "0", "-4", [], "before start"; "0", "99", values, "clamp stop";
    "3", "99", [], "outside"; "2", "0", [], "reversed";
    minimum, maximum, values, "extremes"; minimum, minimum, [], "minimum stop";
    maximum, maximum, [], "maximum start"; "-1", maximum, ["c"], "tail"] in
  let range_cases = List.concat_map (fun (first, last, expected, name) ->
    List.map (fun (before, selected) -> first, last, name, before, selected)
      [list values, expected; S.empty, []]) ranges in
  let* ranges = fold (fun (first, last, name, before, expected) ->
    let before = S.put "other" (S.Str "kept") before in
    let* reply, after = execute [signed first; signed last] before in
    require (reply = I.Array (List.map (fun s -> I.Bulk s) expected) && same before after) ("range " ^ name))
    range_cases in
  let* payloads = fold (fun values ->
    let before = list values in let* reply, after = execute [signed "0"; signed "-1"] before in
    require (reply = I.Array (List.map (fun s -> I.Bulk s) values) && same before after) "bulk elements and order")
    [[""; "\000"; "\255"; "\239\187\191hello\000\n\n"; "01"];
     List.init 129 (fun i -> string_of_int i)] in
  let wrong_types = [S.Str "old"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let wrong = List.map (fun value -> [signed "0"; signed "-1"], S.put "k" value S.empty, S.Wrong_type) wrong_types in
  let malformed = [""; "01"; "-0"; "+1"; "1.0"; " 1"; "1\000"; "0x1";
    "9223372036854775808"; "-9223372036854775809"] in
  let invalid = List.concat_map (fun index -> List.concat_map (fun before ->
    List.map (fun args -> args, before, S.Not_integer)
      [[signed index; signed "-1"]; [signed "0"; signed index]])
      [S.empty; list values; S.put "k" (S.Str "old") S.empty]) malformed in
  let* errors = fold (fun (args, before, fault) ->
    let* () = require (execute args before = Error (S.message fault)) "error stops client" in
    let* reply, after = execute ~expose:true args before in
    require (reply = I.Status (S.message fault) && same before after) "typed error preserves state") (wrong @ invalid) in
  let malformed_args = [ []; [signed "0"]; [signed "0"; signed "-1"; bytes "extra"];
    [bytes "0"; signed "-1"]; [signed "0"; bytes "-1"]; [bytes "0"; bytes "-1"]] in
  let* shapes = fold (fun args -> require (execute args (list values) = Error "STORE-SCRIPT-COMMAND") "operand shape") malformed_args in
  let total = ranges + payloads + errors + shapes in
  let* () = require (total = 101) (Printf.sprintf "expected 101 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS LIST-RANGE-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
