module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("LIST-REMOVE-UNIT " ^ reason)
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
let execute ?(expose=false) args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", 65, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let answer = if expose then E.KCase (E.Tid "mu<Reply>", E.KVar 0,
    [{E.tag=4; arity=1; body=E.KTag (E.Tid "mu<Reply>", 3, [E.KVar 0])}]) else E.KVar 0 in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [answer]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run () =
  let values = ["a"; "b"; "a"; "c"; "a"] in
  let binary = String.init 256 Char.chr in
  let text = "\239\187\191hello\000\n\n" in
  let samples = [
    "1", "a", values, "1", ["b"; "a"; "c"; "a"];
    "2", "a", values, "2", ["b"; "c"; "a"];
    "-1", "a", values, "1", ["a"; "b"; "a"; "c"];
    "-2", "a", values, "2", ["a"; "b"; "c"];
    "0", "a", values, "3", ["b"; "c"];
    "100", "a", values, "3", ["b"; "c"];
    "-100", "a", values, "3", ["b"; "c"];
    "9223372036854775807", "a", values, "3", ["b"; "c"];
    "-9223372036854775807", "a", values, "3", ["b"; "c"];
    "9007199254740993", "a", values, "3", ["b"; "c"];
    "-9007199254740993", "a", values, "3", ["b"; "c"];
    "1", "z", values, "0", values;
    "0", "a", ["a"], "1", [];
    "0", "a", ["a"; "a"; "a"], "3", [];
    "1", "a", [], "0", [];
    "-1", "a", [], "0", [];
    "0", "a", [], "0", [];
    "-1", "", [""; "a"; ""], "1", [""; "a"];
    "1", binary, [binary; "a"; binary], "1", ["a"; binary];
    "0", "01", ["1"; "01"; "01"], "2", ["1"];
    "-1", text, [text; "a"; text], "1", [text; "a"]] in
  let* successes = fold (fun (count, value, before, expected, after) ->
    let* reply, actual = S.lrem "k" count value (list before) |> Result.map_error S.message in
    let* () = require (reply = expected && same actual (list after)) "store count, order and complete state" in
    let* reply, actual = execute [signed count; bytes value] (list before) in
    require (reply = I.Int expected && same actual (list after)) "interpreter count, order and complete state") samples in
  let wrong = List.map stored [S.Str "old"; S.Hash ["f", "v"]; S.Set ["m"]; S.ZSet ["m", "1"]; S.Stream ["1-0", "v"]] in
  let malformed = [""; "01"; "-0"; "+1"; "1.0"; " 1"; "1 "; "1\000"; "0x1";
    "9223372036854775808"; "-9223372036854775809"; "\255"] in
  let faults = List.concat_map (fun count -> List.map (fun before -> count, before, S.Not_integer)
      (base :: list values :: wrong)) malformed
    @ List.concat_map (fun before -> List.map (fun count -> count, before, S.Wrong_type)
      ["1"; "0"; "-9223372036854775807"]) wrong
    @ List.map (fun before -> "-9223372036854775808", before, S.Remove_range) (base :: list values :: wrong) in
  let* errors = fold (fun (count, before, fault) ->
    let* () = require (S.lrem "k" count "a" before = Error fault) "store error precedence" in
    let args = [signed count; bytes "a"] in
    let* () = require (execute args before = Error (S.message fault)) "unhandled error stops client" in
    let* reply, after = execute ~expose:true args before in
    require (reply = I.Status (S.message fault) && same before after) "typed error preserves complete state") faults in
  let* shapes = fold (fun args -> require (execute args (list values) = Error "STORE-SCRIPT-COMMAND") "operand shape")
    [[bytes "1"; bytes "a"]; [signed "1"; signed "1"]; [signed "1"]; []; [signed "1"; bytes "a"; bytes "extra"]] in
  let* expired = fold (fun count ->
    let* before = S.advance "4001" (list values) |> Result.map_error S.message in
    let* reply, after = execute [signed count; bytes "a"] before in
    require (reply = I.Int "0" && same before after && S.exists "k" after = "0") "expired list stays absent") ["1"; "0"; "-1"] in
  let total = successes + errors + shapes + expired in
  let* () = require (total = 135) (Printf.sprintf "expected 135 cases, counted %d" total) in Ok total
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS LIST-REMOVE-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
