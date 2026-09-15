module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("SET-ALGEBRA-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let same a b = S.Keys.bindings a = S.Keys.bindings b
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let key s = E.KTag (E.Tid "mu<Key>", 0, [bytes s])
let execute ?(expose=false) tag args before =
  let script = E.KTag (E.Tid "mu<Script>", tag, key "left" :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run () =
  let octets = List.of_seq (String.to_seq I.octets) |> List.map (String.make 1) in
  let numbered first count = List.init count (fun i -> Printf.sprintf "m%03d" (first + i)) in
  let cases = [
    None, None, [], [], [], "missing";
    Some ["b"; "a"], None, ["a"; "b"], [], ["a"; "b"], "left only";
    None, Some ["b"; "a"], ["a"; "b"], [], [], "right only";
    Some ["c"; "a"], Some ["c"; "b"], ["a"; "b"; "c"], ["c"], ["a"], "overlap";
    Some ["b"], Some ["a"], ["a"; "b"], [], ["b"], "disjoint";
    Some ["b"; "a"; "a"], Some ["b"; "b"], ["a"; "b"], ["b"], ["a"], "duplicates";
    Some ["a\000"; "a"; ""], Some ["aa"; "a"; "\000"],
      [""; "\000"; "a"; "a\000"; "aa"], ["a"], [""; "a\000"], "prefix order";
    Some ["10"; "2"], Some ["01"; "2"], ["01"; "10"; "2"], ["2"], ["10"], "decimal order";
    Some (List.rev octets), Some [""; "\255"], "" :: octets, ["\255"],
      List.filter (fun s -> s <> "\255") octets, "byte order";
    Some (List.rev (numbered 0 129)), Some (numbered 0 65), numbered 0 129,
      numbered 0 65, numbered 65 64, "complete array"] in
  let* total = List.fold_left (fun acc tag -> let* total = acc in
    let* values = fold (fun (left, right, union, inter, diff, name) ->
      let put k value st = Option.fold ~none:st ~some:(fun xs -> S.put k (S.Set xs) st) value in
      let before = S.empty |> S.put "other" (S.Str "kept") |> put "left" left |> put "right" right in
      let* answer, after = execute tag [key "right"] before in
      let expected = if tag = 32 then union else if tag = 33 then inter else diff in
      require (answer = I.Array (List.map (fun s -> I.Bulk s) expected) && same before after) name) cases in
    let before = S.empty |> S.put "left" (S.Set ["b"; "a"]) |> S.put "other" (S.Str "kept") in
    let* answer, after = execute tag [key "left"] before in
    let* () = require (answer = I.Array (if tag = 34 then [] else [I.Bulk "a"; I.Bulk "b"])
      && same before after) "same key" in
    let errors = List.concat_map (fun bad -> List.concat_map (fun bad_key ->
      List.map (fun present -> bad, bad_key, present) [false; true]) ["left"; "right"])
      [S.Str "old"; S.Hash ["f", "v"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream ["entry", "v"]] in
    let* errors = fold (fun (bad, bad_key, present) ->
      let other_key = if bad_key = "left" then "right" else "left" in
      let before = S.put bad_key bad (S.put "other" (S.Str "kept") S.empty) in
      let before = if present then S.put other_key (S.Set ["a"]) before else before in
      let* () = require (execute tag [key "right"] before = Error (S.message S.Wrong_type)) "error stops client" in
      let* answer, after = execute ~expose:true tag [key "right"] before in
      require (answer = I.Status (S.message S.Wrong_type) && same before after) "typed error preserves state") errors in
    let* shapes = fold (fun args ->
      require (execute tag args S.empty = Error "STORE-SCRIPT-COMMAND") "operand shape")
      [[]; [bytes "right"]; [E.KTag (E.Tid "mu<Signed64>", 0, [bytes "0"])]; [key "right"; key "left"]] in
    Ok (total + values + 1 + errors + shapes)) (Ok 0) [32; 33; 34] in
  let* () = require (execute 15 [key "right"] S.empty = Error "STORE-SCRIPT-COMMAND") "key operand is not a command shape" in
  let total = total + 1 in
  let* () = require (total = 106) (Printf.sprintf "expected 106 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS SET-ALGEBRA-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
