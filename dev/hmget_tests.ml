module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let store result = Result.map_error S.message result
let require condition reason = if condition then Ok () else Error ("HMGET-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let fields first rest =
  let rec make first = function
    | [] -> E.KTag (E.Tid "mu<BulkArgs>", 0, [bytes first])
    | next :: rest -> E.KTag (E.Tid "mu<BulkArgs>", 1, [bytes first; make next rest]) in
  make first rest
let execute ?(expose=false) args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", 52, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
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
  let cases = [
    None, "missing", [], [None];
    None, "a", ["b"; "a"], [None; None; None];
    Some [], "", [""], [None; None];
    Some ["z", "first"; "a", "second"], "z", ["a"; "z"], [Some "first"; Some "second"; Some "first"];
    Some ["a", "value"], "absent", ["a"; "absent"; "a"; "absent"], [None; Some "value"; None; Some "value"; None];
    Some ["", ""; "a", ""], "", ["a"; "no"], [Some ""; Some ""; None];
    Some [I.octets, I.octets], I.octets, ["no"; I.octets], [Some I.octets; None; Some I.octets];
    Some ["large", "9007199254740993"], "large", [], [Some "9007199254740993"];
    Some (List.map (fun b -> b, b) octets), "absent", octets, None :: List.map Option.some octets;
    Some ["a", "value"], "a", List.init 129 (fun _ -> "a"), List.init 130 (fun _ -> Some "value")]
  in
  let* values = fold (fun (initial, first, rest, expected) ->
    let before = S.put "other" (S.Str "kept") S.empty in
    let before = Option.fold ~none:before ~some:(fun fs -> S.put "k" (S.Hash fs) before) initial in
    let* _, before = store (S.expire ~seconds:false "k" "5000" before) in
    let* actual = store (S.hmget "k" first rest before) in
    let* () = require (actual = expected) "store preserves order, nils and duplicates" in
    let* reply, after = execute [fields first rest] before in
    require (reply = I.Array (List.map (Option.fold ~none:I.Nil ~some:(fun s -> I.Bulk s)) expected)
      && after = before) "interpreter reply and complete state") cases in
  let* errors = fold (fun value ->
    let before = S.put "k" value (S.put "other" (S.Str "kept") S.empty) in
    let* _, before = store (S.expire ~seconds:false "k" "5000" before) in
    let* () = require (S.hmget "k" "a" [] before = Error S.Wrong_type) "store wrong type" in
    let* () = require (execute [fields "a" []] before = Error (S.message S.Wrong_type)) "error stops client" in
    let* reply, after = execute ~expose:true [fields "a" []] before in
    require (reply = I.Status (S.message S.Wrong_type) && after = before) "error preserves complete state")
    [S.Str "old"; S.Set ["m"]; S.List ["m"]; S.ZSet ["m", "1"]; S.Stream []] in
  let bad tag xs = E.KTag (E.Tid "mu<BulkArgs>", tag, xs) in
  let* shapes = fold (fun (args, expected) ->
    require (execute args S.empty = Error expected) "malformed operand refusal") [
      [], "STORE-SCRIPT-COMMAND"; [bytes "a"], "STORE-SCRIPT-COMMAND";
      [fields "a" []; fields "b" []], "STORE-SCRIPT-COMMAND";
      [bad 0 []], "STORE-BULK-ARGS"; [bad 0 [bytes "a"; bytes "b"]], "STORE-BULK-ARGS";
      [bad 1 [bytes "a"]], "STORE-BULK-ARGS"; [bad 2 [bytes "a"]], "STORE-BULK-ARGS";
      [bad 1 [bytes "a"; bytes "b"]], "STORE-BULK-ARGS";
      [bad 0 [E.KErased]], "STORE-BYTES";
      [bad 1 [E.KErased; fields "a" []]], "STORE-BYTES"] in
  let before = S.put "k" (S.Hash ["a", "value"]) S.empty in
  let* _, expiring = store (S.expire ~seconds:false "k" "1" before) in
  let* expired = store (S.advance "2" expiring) in
  let* reply, after = execute [fields "a" ["a"]] expired in
  let* () = require (reply = I.Array [I.Nil; I.Nil] && after = expired) "expired Hash is missing" in
  let count = values + errors + shapes + 1 in
  let* () = require (count = 26) "case inventory" in Ok count
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS HMGET-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
