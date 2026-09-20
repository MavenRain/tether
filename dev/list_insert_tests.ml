module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("LIST-INSERT-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let same a b = S.bindings a = S.bindings b && S.Keys.bindings a.S.deadlines = S.Keys.bindings b.S.deadlines && a.S.now = b.S.now
let base = { (S.put "other" (S.Str "kept") S.empty) with now = 1000L; deadlines = S.Keys.singleton "other" 9000L }
let stored value = { (S.put "k" value base) with deadlines = S.Keys.add "k" 5000L base.S.deadlines }
let list = function [] -> base | values -> stored (S.List values)
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
let tag = function S.Left -> 66 | S.Right -> 67
let run () =
  let values = ["a"; "b"; "a"; "c"; "a"] in
  let binary = I.octets in
  let reversed = String.of_seq (List.to_seq (List.rev (List.of_seq (String.to_seq binary)))) in
  let text = "\239\187\191hello\000\n\n" in
  let samples = [
    S.Left, "a", "x", values, "6", ["x"; "a"; "b"; "a"; "c"; "a"];
    S.Right, "a", "x", values, "6", ["a"; "x"; "b"; "a"; "c"; "a"];
    S.Left, "c", "x", values, "6", ["a"; "b"; "a"; "x"; "c"; "a"];
    S.Right, "c", "x", values, "6", ["a"; "b"; "a"; "c"; "x"; "a"];
    S.Left, "end", "x", ["first"; "second"; "end"], "4", ["first"; "second"; "x"; "end"];
    S.Right, "end", "x", ["first"; "second"; "end"], "4", ["first"; "second"; "end"; "x"];
    S.Left, "a", "x", ["a"], "2", ["x"; "a"];
    S.Right, "a", "x", ["a"], "2", ["a"; "x"];
    S.Left, "a", "x", [], "0", []; S.Right, "a", "x", [], "0", [];
    S.Left, "z", "x", values, "-1", values; S.Right, "z", "x", values, "-1", values;
    S.Left, "", "x", [""; "a"; ""], "4", ["x"; ""; "a"; ""];
    S.Right, "", "x", [""; "a"; ""], "4", [""; "x"; "a"; ""];
    S.Left, "a", "", ["a"], "2", [""; "a"]; S.Right, "a", "", ["a"], "2", ["a"; ""];
    S.Left, binary, reversed, [binary; "a"; binary], "4", [reversed; binary; "a"; binary];
    S.Right, binary, reversed, [binary; "a"; binary], "4", [binary; reversed; "a"; binary];
    S.Left, "a", "a", ["a"; "a"], "3", ["a"; "a"; "a"]; S.Right, "a", "a", ["a"; "a"], "3", ["a"; "a"; "a"];
    S.Left, "01", "x", ["1"; "01"; "01"], "4", ["1"; "x"; "01"; "01"];
    S.Right, "01", "x", ["1"; "01"; "01"], "4", ["1"; "01"; "x"; "01"];
    S.Left, text, "x", ["a"; text; "c"], "4", ["a"; "x"; text; "c"];
    S.Right, text, "x", ["a"; text; "c"], "4", ["a"; text; "x"; "c"]] in
  let* successes = fold (fun (side, pivot, value, before, expected, after) ->
    let* reply, actual = S.linsert side "k" pivot value (list before) |> Result.map_error S.message in
    let* () = require (reply = expected && same actual (list after)) "store length, order and complete state" in
    let* reply, actual = execute (tag side) [bytes pivot; bytes value] (list before) in
    require (reply = I.Int expected && same actual (list after)) "interpreter length, order and complete state") samples in
  let wrong = List.map stored [S.Str "old"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream ["1-0", "v"]] in
  let* errors = fold (fun (side, before) ->
    let* () = require (S.linsert side "k" "a" "x" before = Error S.Wrong_type) "store wrong type" in
    let args = [bytes "a"; bytes "x"] in
    let* () = require (execute (tag side) args before = Error (S.message S.Wrong_type)) "unhandled error stops client" in
    let* reply, after = execute ~expose:true (tag side) args before in
    require (reply = I.Status (S.message S.Wrong_type) && same before after) "typed error preserves complete state")
    (List.concat_map (fun side -> List.map (fun before -> side, before) wrong) [S.Left; S.Right]) in
  let* shapes = fold (fun (side, args) -> require (execute (tag side) args (list values) = Error "STORE-SCRIPT-COMMAND") "operand shape")
    (List.concat_map (fun side -> List.map (fun args -> side, args)
      [[signed "1"; bytes "x"]; [bytes "a"; signed "1"]; [bytes "a"]; []; [bytes "a"; bytes "x"; bytes "extra"]]) [S.Left; S.Right]) in
  let* expired = fold (fun (side, before) ->
    let* before = S.advance "4001" before |> Result.map_error S.message in
    let* reply, after = execute (tag side) [bytes "a"; bytes "x"] before in
    require (reply = I.Int "0" && same before after && S.exists "k" after = "0") "expired key stays absent")
    (List.concat_map (fun side -> List.map (fun before -> side, before) [list values; stored (S.Str "wrong")]) [S.Left; S.Right]) in
  let prefix = List.init 10000 (fun _ -> "a") in
  let* long = fold (fun side ->
    let* reply, after = S.linsert side "k" "pivot" "x" (list (prefix @ ["pivot"])) |> Result.map_error S.message in
    let expected = prefix @ (match side with S.Left -> ["x"; "pivot"] | S.Right -> ["pivot"; "x"]) in
    require (reply = "10002" && same after (list expected)) "long prefix keeps order and expiry") [S.Left; S.Right] in
  let total = successes + errors + shapes + expired + long in
  let* () = require (total = 50) (Printf.sprintf "expected 50 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS LIST-INSERT-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
