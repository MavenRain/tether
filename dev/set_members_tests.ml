module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("SET-MEMBERS-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let same a b = S.Keys.bindings a = S.Keys.bindings b
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let execute ?(expose=false) args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", 28, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run () =
  let many = List.init 129 (Printf.sprintf "m%03d") in
  let octets = List.of_seq (String.to_seq I.octets) |> List.map (String.make 1) in
  let cases = [
    None, [], "missing"; Some [], [], "empty";
    Some ["z"; "a"; "a"], ["a"; "z"], "unique order";
    Some ["a\000"; "aa"; "a"; "\000a"; "\000"; ""],
      [""; "\000"; "\000a"; "a"; "a\000"; "aa"], "prefix order";
    Some (List.rev octets), octets, "byte order";
    Some (List.rev many), many, "complete array"] in
  let* values = fold (fun (initial, expected, name) ->
    let before = S.put "other" (S.Str "kept") S.empty in
    let before = Option.fold ~none:before ~some:(fun ss -> S.put "k" (S.Set ss) before) initial in
    let* reply, after = execute [] before in
    require (reply = I.Array (List.map (fun s -> I.Bulk s) expected) && same before after) name) cases in
  let* errors = fold (fun value ->
    let before = S.put "k" value (S.put "other" (S.Str "kept") S.empty) in
    let* () = require (execute [] before = Error (S.message S.Wrong_type)) "error stops client" in
    let* reply, after = execute ~expose:true [] before in
    require (reply = I.Status (S.message S.Wrong_type) && same before after) "typed error preserves state")
    [S.Str "old"; S.Hash ["f", "v"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let* shapes = fold (fun args ->
    require (execute args S.empty = Error "STORE-SCRIPT-COMMAND") "operand shape")
    [[bytes "extra"]; [E.KTag (E.Tid "mu<Signed64>", 0, [bytes "0"])]; [bytes "a"; bytes "b"]] in
  let total = values + errors + shapes in
  let* () = require (total = 14) (Printf.sprintf "expected 14 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS SET-MEMBERS-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
