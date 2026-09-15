module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("SET-STORE-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let same a b = S.Keys.bindings a = S.Keys.bindings b
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let key s = E.KTag (E.Tid "mu<Key>", 0, [bytes s])
let execute ?(expose=false) ?(destination="destination") tag args before =
  let script = E.KTag (E.Tid "mu<Script>", tag, key destination :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let destinations = ["destination"; "left"; "right"]
let wrong = [S.Str "old"; S.Hash ["f", "v"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream ["entry", "v"]]
let initial = S.empty |> S.put "other" (S.Str "kept") |> S.put "destination" (S.Hash ["stale", "value"])
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
      [""; "\000"; "a"; "a\000"; "aa"], ["a"], [""; "a\000"], "prefix bytes";
    Some ["10"; "2"], Some ["01"; "2"], ["01"; "10"; "2"], ["2"], ["10"], "decimal bytes";
    Some (List.rev octets), Some [""; "\255"], "" :: octets, ["\255"],
      List.filter (fun s -> s <> "\255") octets, "all bytes";
    Some (List.rev (numbered 0 129)), Some (numbered 0 65), numbered 0 129,
      numbered 0 65, numbered 65 64, "complete set"] in
  let* total = List.fold_left (fun acc tag -> let* total = acc in
    let check destination args before expected name =
      let* answer, after = execute ~destination tag args before in
      let wanted = if expected = [] then S.Keys.remove destination before else S.put destination (S.Set expected) before in
      require (answer = I.Int (string_of_int (List.length expected)) && same after wanted) name in
    let fixtures = List.concat_map (fun row -> List.map (fun d -> d, row) destinations) cases in
    let* values = fold (fun (destination, (left, right, union, inter, diff, name)) ->
      let put k value st = Option.fold ~none:st ~some:(fun xs -> S.put k (S.Set xs) st) value in
      let before = initial |> put "left" left |> put "right" right in
      check destination [key "left"; key "right"] before
        (if tag = 35 then union else if tag = 36 then inter else diff) name) fixtures in
    let* replaced = fold (fun old ->
      let before = Option.fold ~none:(S.Keys.remove "destination" initial) ~some:(fun d -> S.put "destination" d initial) old
        |> S.put "left" (S.Set ["a"; "b"]) |> S.put "right" (S.Set ["b"; "c"]) in
      check "destination" [key "left"; key "right"] before
        (if tag = 35 then ["a"; "b"; "c"] else if tag = 36 then ["b"] else ["a"]) "overwrite destination")
      (None :: List.map Option.some (S.Set ["old"] :: wrong)) in
    let errors = List.concat_map (fun bad -> List.concat_map (fun side -> List.concat_map (fun present ->
      List.map (fun d -> bad, side, present, d) destinations) [false; true]) ["left"; "right"]) wrong in
    let* errors = fold (fun (bad, side, present, destination) ->
      let other = if side = "left" then "right" else "left" in
      let before = S.put side bad initial in
      let before = if present then S.put other (S.Set ["a"]) before else before in
      let args = [key "left"; key "right"] in
      let* () = require (execute ~destination tag args before = Error (S.message S.Wrong_type)) "error stops client" in
      let* answer, after = execute ~expose:true ~destination tag args before in
      require (answer = I.Status (S.message S.Wrong_type) && same before after) "error preserves destination") errors in
    let* identical = fold (fun destination ->
      let before = S.put "left" (S.Set ["b"; "a"]) initial in
      check destination [key "left"; key "left"] before (if tag = 37 then [] else ["a"; "b"]) "same source") destinations in
    let signed = E.KTag (E.Tid "mu<Signed64>", 0, [bytes "0"]) in
    let* shapes = fold (fun args -> require (execute tag args initial = Error "STORE-SCRIPT-COMMAND") "operand shape")
      [[]; [key "left"]; [bytes "left"; key "right"]; [key "left"; bytes "right"];
       [signed; key "right"]; [key "left"; signed]; [key "left"; key "right"; key "other"]] in
    Ok (total + values + replaced + errors + identical + shapes)) (Ok 0) [35; 36; 37] in
  let* () = require (execute 39 [key "left"; key "right"] initial = Error "STORE-SCRIPT-COMMAND") "unknown command" in
  let total = total + 1 in
  let* () = require (total = 322) (Printf.sprintf "expected 322 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS SET-STORE-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
