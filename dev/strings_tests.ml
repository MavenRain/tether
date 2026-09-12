module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error reason
let integer_cases = [
  "0", "0", "0"; "0", "-1", "-1"; "-1", "1", "0";
  "99", "1", "100"; "100", "-101", "-1"; "-99", "-1", "-100";
  "9007199254740992", "1", "9007199254740993";
  "9007199254740994", "-1", "9007199254740993";
  "0", "9223372036854775807", "9223372036854775807";
  "0", "-9223372036854775808", "-9223372036854775808";
  "9223372036854775807", "-9223372036854775808", "-1";
  "-9223372036854775808", "9223372036854775807", "-1"]
let overflow_cases = ["9223372036854775807", "1";
  "-9223372036854775808", "-1"; "-1", "-9223372036854775808";
  "1", "9223372036854775807"]
let wrong_types = [S.Hash []; S.List []; S.Set []; S.ZSet []; S.Stream []]
let invalid = [""; "01"; "+1"; "-0"; "0x10"; "1_0"; " 1"; "9223372036854775808"]
let fold f xs = List.fold_left (fun acc x -> let* () = acc in f x) (Ok ()) xs
let run () =
  let* () = fold (fun (initial, amount, expected) ->
    let before = S.put "k" (S.Str initial) S.empty in
    let* actual, after = S.incrby "k" amount before |> Result.map_error S.message in
    require (actual = expected && S.get "k" after = Ok (Some expected)
      && S.get "k" before = Ok (Some initial)) "STRINGS-UNIT arithmetic") integer_cases in
  let* () = fold (fun (initial, amount) ->
    require (S.incrby "k" amount (S.put "k" (S.Str initial) S.empty) = Error S.Overflow)
      "STRINGS-UNIT overflow") overflow_cases in
  let* () = fold (fun initial ->
    let before = S.put "k" initial S.empty in
    require (S.incrby "k" "1" before = Error S.Wrong_type && S.decr "k" before = Error S.Wrong_type)
      "STRINGS-UNIT wrong type") wrong_types in
  let* () = fold (fun initial ->
    let before = S.put "k" initial S.empty in
    let status, after = S.set "k" "\000\255" before in
    require (status = "OK" && S.get "k" after = Ok (Some "\000\255"))
      "STRINGS-UNIT set replaces") wrong_types in
  let* () = fold (fun initial ->
    let before = S.put "k" initial S.empty in
    let count, removed = S.del "k" before in
    require (S.exists "k" before = "1" && count = "1" && S.exists "k" removed = "0")
      "STRINGS-UNIT delete") wrong_types in
  let* () = fold (fun value -> require
    (S.incrby "k" value S.empty = Error S.Not_integer
      && S.incrby "k" "1" (S.put "k" (S.Str value) S.empty) = Error S.Not_integer)
    "STRINGS-UNIT invalid decimal") invalid in
  let* n, after = S.decr "k" S.empty |> Result.map_error S.message in
  let* () = require (n = "-1" && S.get "k" after = Ok (Some "-1")
    && S.del "k" S.empty = ("0", S.empty)) "STRINGS-UNIT missing" in
  (* Run real erased command nodes and check the returned store independently. *)
  let rec term = function
    | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
    | I.Literal l -> E.KLit l
    | I.Fields _ | I.Closure _ | I.Erased -> E.KErased in
  let bytes s = term (I.bytes s) in
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let signed s = E.KTag (E.Tid "mu<Signed64>", 0, [bytes s]) in
  let samples = [3, [bytes "binary"], "binary", I.Status "OK";
    4, [signed "9007199254740993"], "9007199254740993", I.Status "OK";
    5, [signed "-2"], "3", I.Int "3"; 6, [], "4", I.Int "4";
    7, [], "@missing", I.Int "1"; 8, [], "5", I.Int "1"] in
  let* () = fold (fun (tag, args, expected, answer) ->
    let script = E.KTag (E.Tid "mu<Script>", tag,
      key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
    let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
    let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
    let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
      fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [E.KVar 0]));
      fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
    let budget = Kanon_kernel.Budget.of_poll (fun () -> false) in
    let* actual, store = I.run ~budget rows ~entry:"main" (S.put "k" (S.Str "5") S.empty) in
    require (actual = answer && S.get "k" store = Ok (if expected = "@missing" then None else Some expected))
      "STRINGS-UNIT interpreter effect") samples in
  Ok (List.length integer_cases + List.length overflow_cases + (3 * List.length wrong_types)
    + List.length invalid + 1 + List.length samples)
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS STRINGS-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
