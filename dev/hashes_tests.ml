module S = Tether_store.Store
module I = Tether_store.Interp
module E = Kanon_kernel.Eterm
let ( let* ) = Result.bind
let require condition reason = if condition then Ok () else Error ("HASHES-UNIT " ^ reason)
let fold f xs = List.fold_left (fun acc x -> let* n = acc in let* () = f x in Ok (n + 1)) (Ok 0) xs
let hash fields = S.put "k" (S.Hash fields) S.empty
let integer_cases = ["0", "1", "1"; "-1", "1", "0"; "99", "-100", "-1";
  "9007199254740992", "1", "9007199254740993";
  "9007199254740994", "-1", "9007199254740993";
  "0", "9223372036854775807", "9223372036854775807";
  "0", "-9223372036854775808", "-9223372036854775808";
  "9223372036854775807", "-9223372036854775808", "-1";
  "-9223372036854775808", "9223372036854775807", "-1"]
let overflow_cases = ["9223372036854775807", "1"; "-9223372036854775808", "-1";
  "-1", "-9223372036854775808"; "1", "9223372036854775807"]
let invalid = [""; "01"; "+1"; "-0"; "0x10"; "1_0"; " 1"; "9223372036854775808"]
let wrong_types = [S.Str "old"; S.List []; S.Set []; S.ZSet []; S.Stream []]
let rec term = function
  | I.Data (tid, tag, xs) -> E.KTag (tid, tag, List.map term xs)
  | I.Literal l -> E.KLit l
  | I.Fields _ | I.Closure _ | I.Erased -> E.KErased
let bytes s = term (I.bytes s)
let signed s = E.KTag (E.Tid "mu<Signed64>", 0, [bytes s])
let execute tag args before =
  let key = E.KTag (E.Tid "mu<Key>", 0, [bytes "k"]) in
  let script = E.KTag (E.Tid "mu<Script>", tag, key :: args @ [E.KClos (E.Fid "pure", 1, [])]) in
  let client = E.KTag (E.Tid "mu<Client>", 1, [script; E.KClos (E.Fid "done", 1, [])]) in
  let fn name ps body = E.KFun (E.Fid name, ps, E.RI31, body) in
  let rows = ["main", Kanon_kernel.Erase.Code [fn "main" [] client;
    fn "pure" [E.RI31] (E.KTag (E.Tid "mu<Script>", 0, [E.KVar 0]));
    fn "done" [E.RI31] (E.KTag (E.Tid "mu<Client>", 0, [E.KVar 0]))]] in
  I.run ~budget:(Kanon_kernel.Budget.of_poll (fun () -> false)) rows ~entry:"main" before
let run () =
  let* arithmetic = fold (fun (initial, amount, expected) ->
    let before = hash ["f", initial; "other", "kept"] in
    let* actual, after = S.hincrby "k" "f" amount before |> Result.map_error S.message in
    require (actual = expected && S.hget "k" "f" after = Ok (Some expected)
      && S.hget "k" "f" before = Ok (Some initial)
      && S.hget "k" "other" after = Ok (Some "kept")) "arithmetic") integer_cases in
  let* overflow = fold (fun (initial, amount) ->
    require (S.hincrby "k" "f" amount (hash ["f", initial]) = Error S.Overflow) "overflow") overflow_cases in
  let* decimals = fold (fun value ->
    require (S.hincrby "k" "f" value S.empty = Error S.Not_integer
      && S.hincrby "k" "f" "1" (hash ["f", value]) = Error S.Hash_not_integer)
      "invalid decimal") invalid in
  let operations = ["hget", (fun s -> Result.map (fun _ -> ()) (S.hget "k" "f" s));
    "hset", (fun s -> Result.map (fun _ -> ()) (S.hset "k" "f" "v" s));
    "hdel", (fun s -> Result.map (fun _ -> ()) (S.hdel "k" "f" s));
    "hexists", (fun s -> Result.map (fun _ -> ()) (S.hexists "k" "f" s));
    "hlen", (fun s -> Result.map (fun _ -> ()) (S.hlen "k" s));
    "hincrby", (fun s -> Result.map (fun _ -> ()) (S.hincrby "k" "f" "1" s))] in
  let* wrong = fold (fun (name, operation, value) ->
    require (operation (S.put "k" value S.empty) = Error S.Wrong_type) ("wrong type " ^ name))
    (List.concat_map (fun (name, f) -> List.map (fun v -> name, f, v) wrong_types) operations) in
  let* basic = fold (fun (ok, name) -> require ok name) [
    S.hget "k" "f" S.empty = Ok None, "missing read";
    S.hexists "k" "f" S.empty = Ok "0", "missing exists";
    S.hlen "k" S.empty = Ok "0", "missing length";
    S.hdel "k" "f" S.empty = Ok ("0", S.empty), "missing delete";
    S.hdel "k" "f" (hash ["f", "v"]) = Ok ("1", S.empty), "delete last field";
    S.hdel "k" "missing" (hash ["f", "v"]) = Ok ("0", hash ["f", "v"]), "delete absent field";
    S.hincrby "k" "f" "-1" S.empty = Ok ("-1", hash ["f", "-1"]), "missing increment"] in
  let samples = [
    9, [bytes "f"; bytes "new"], hash ["f", "old"], I.Int "0", hash ["f", "new"], "overwrite count";
    9, [bytes "\000\255"; bytes "\255\000"], S.empty, I.Int "1", hash ["\000\255", "\255\000"], "binary fields";
    9, [bytes ""; bytes ""], S.empty, I.Int "1", hash ["", ""], "empty fields";
    10, [bytes "f"], S.empty, I.Nil, S.empty, "nil reply";
    10, [bytes "f"], hash ["f", ""], I.Bulk "", hash ["f", ""], "empty bulk reply";
    10, [bytes "\000\255"], hash ["\000\255", "\255\000"], I.Bulk "\255\000", hash ["\000\255", "\255\000"], "binary read";
    11, [bytes "f"], hash ["f", "v"], I.Int "1", S.empty, "interpreter deletes key";
    11, [bytes "f"], hash ["f", "v"; "other", "kept"], I.Int "1", hash ["other", "kept"], "preserve sibling";
    12, [bytes "f"], hash ["f", ""], I.Int "1", hash ["f", ""], "empty field exists";
    13, [], hash ["a", "1"; "b", "2"], I.Int "2", hash ["a", "1"; "b", "2"], "field count";
    14, [bytes "f"; signed "1"], hash ["f", "9007199254740992"], I.Int "9007199254740993",
      hash ["f", "9007199254740993"], "interpreter increment"] in
  let* interpreted = fold (fun (tag, args, before, expected, after, name) ->
    let* reply, actual = execute tag args before in
    require (reply = expected && S.Keys.bindings actual = S.Keys.bindings after) name) samples in
  (* Every fault leaves the interpreter as an err reply that stops the Client. *)
  let faults = [
    9, [bytes "f"; bytes "v"], S.put "k" (S.Str "old") S.empty, S.Wrong_type, "hset wrong type stops client";
    10, [bytes "f"], S.put "k" (S.List []) S.empty, S.Wrong_type, "hget wrong type stops client";
    11, [bytes "f"], S.put "k" (S.Set []) S.empty, S.Wrong_type, "hdel wrong type stops client";
    12, [bytes "f"], S.put "k" (S.ZSet []) S.empty, S.Wrong_type, "hexists wrong type stops client";
    13, [], S.put "k" (S.Stream []) S.empty, S.Wrong_type, "hlen wrong type stops client";
    14, [bytes "f"; signed "1"], S.put "k" (S.Str "old") S.empty, S.Wrong_type,
      "hincrby wrong type stops client";
    14, [bytes "f"; signed "1"], hash ["f", "0x10"], S.Hash_not_integer, "invalid decimal stops client";
    14, [bytes "f"; signed "1"], hash ["f", "9223372036854775807"], S.Overflow, "overflow stops client"] in
  let* stopped = fold (fun (tag, args, before, fault, name) ->
    require (execute tag args before = Error (S.message fault)) name) faults in
  Ok (arithmetic + overflow + decimals + wrong + basic + interpreted + stopped)
let () = run () |> Result.fold
  ~ok:(fun count -> Printf.printf "PASS HASHES-UNIT cases=%d\n" count)
  ~error:(fun e -> prerr_endline ("FAIL " ^ e); exit 1)
