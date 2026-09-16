module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("HASH-PROJECTIONS-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
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
  let octets = List.of_seq (String.to_seq I.octets) |> List.map (String.make 1) in
  let many = List.init 129 (fun i -> Printf.sprintf "f%03d" i, Printf.sprintf "v%03d" (128 - i)) in
  let cases = [
    None, [], [], "missing"; Some [], [], [], "empty";
    Some ["z", "A"; "a", "old"; "a", "Z"], ["a"; "z"], ["A"; "Z"], "projection";
    Some ["a\000", "4"; "aa", "5"; "a", "3"; "\000a", "2"; "\000", "1"; "", "0"],
      [""; "\000"; "\000a"; "a"; "a\000"; "aa"], ["0"; "1"; "2"; "3"; "4"; "5"], "prefix order";
    Some ["10", "z"; "2", "a"; "01", "1"], ["01"; "10"; "2"], ["1"; "a"; "z"], "decimal order";
    Some (List.map (fun f -> f, f) (List.rev octets)), octets, octets, "byte order";
    Some ["raw", I.octets], ["raw"], [I.octets], "binary value";
    Some [I.octets, "raw"], [I.octets], ["raw"], "binary field";
    Some ["z", "x"; "a", "x"; "b", "y"], ["a"; "b"; "z"], ["x"; "x"; "y"], "duplicates";
    Some (List.rev many), List.map fst many, List.rev (List.map snd many), "complete array"] in
  let* totals = List.fold_left (fun acc tag -> let* total = acc in
    let* values = fold (fun (initial, keys, values, name) ->
      let before = S.put "other" (S.Str "kept") S.empty in
      let before = Option.fold ~none:before ~some:(fun fs -> S.put "k" (S.Hash fs) before) initial in
      let* reply, after = execute tag [] before in
      let expected = if tag = 30 then keys else values in
      require (reply = I.Array (List.map (fun s -> I.Bulk s) expected) && same before after) name) cases in
    let* errors = fold (fun value ->
      let before = S.put "k" value (S.put "other" (S.Str "kept") S.empty) in
      let* () = require (execute tag [] before = Error (S.message S.Wrong_type)) "error stops client" in
      let* reply, after = execute ~expose:true tag [] before in
      require (reply = I.Status (S.message S.Wrong_type) && same before after) "typed error preserves state")
      [S.Str "old"; S.Set ["m"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
    let* shapes = fold (fun args ->
      require (execute tag args S.empty = Error "STORE-SCRIPT-COMMAND") "operand shape")
      [[bytes "extra"]; [E.KTag (E.Tid "mu<Signed64>", 0, [bytes "0"])]; [bytes "a"; bytes "b"]] in
    Ok (total + values + errors + shapes)) (Ok 0) [30; 31] in
  let* () = require (totals = 36) (Printf.sprintf "expected 36 cases, counted %d" totals) in Ok totals
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS HASH-PROJECTIONS-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
